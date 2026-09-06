import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.db.models import update_evidence_file_derived_hashes
from src.pipeline.hashing import compute_bytes_hashes, compute_hashes
from src.pipeline.ingest import ingest_file
from src.pipeline.remux import ensure_sps_pps, remux_to_mp4
from src.pipeline.timeline import record_tier1_events, record_tier2_events
from src.tier1.dahua import parse_dahua_file
from src.tier1.hikvision import parse_hikvision_file
from src.tier2.carver import scan_nal_units

EVIDENCE_STORE_ROOT = Path("evidence_store")


def dispatch_pipeline(
    file_path: Union[str, Path],
    case_id: str,
    db_conn: Optional[sqlite3.Connection] = None,
    vendor_override: Optional[str] = None,
    validation_confidence: str = "Validated: Real Device",
) -> Dict[str, Any]:
    """
    Full Forensic Execution Pipeline:
      1. Ingestion copy to evidence_store/case_<case_id>/raw_images/
      2. Original dual-hashing (MD5 + SHA-256)
      3. Vendor ID signature detection
      4. Tier 1 deep container parsing OR Tier 2 universal carving
      5. Video stream extraction to extracted/ or recovered/
      6. Lossless FFmpeg remux (-c copy) to standardized MP4
      7. Timeline event recording (Tier 1 exact vs Tier 2 approximate)
      8. Derived dual-hashing post-remux
      9. Database record update with derived hashes

    :param file_path: Source evidence video file path.
    :param case_id: Case identifier.
    :param db_conn: Optional SQLite database connection.
    :param vendor_override: Optional manual vendor override string.
    :param validation_confidence: Validation tag string.
    :return: Pipeline execution result dictionary.
    """
    # Step 1 & 2: Ingest file and compute original hashes
    ingest_record = ingest_file(
        source_path=file_path,
        case_id=case_id,
        db_conn=db_conn,
        validation_confidence=validation_confidence,
        vendor_override=vendor_override,
    )

    ingested_path = Path(ingest_record["path"])
    vendor = ingest_record["vendor"]
    evidence_id = ingest_record.get("id")

    extracted_video_bytes = bytearray()
    parsed_frames: List[Any] = []

    # Step 3 & 4: Execute Tier 1 or Tier 2 parsing/carving
    with open(ingested_path, "rb") as f:
        raw_data = f.read()

    case_dir = EVIDENCE_STORE_ROOT / f"case_{case_id}"

    if vendor == "hikvision":
        recovery_tier = "tier1"
        target_parser = "src.tier1.hikvision"
        parsed_frames = parse_hikvision_file(ingested_path)
        for frame in parsed_frames:
            extracted_video_bytes += raw_data[
                frame.payload_offset : frame.payload_offset + frame.payload_size
            ]
        target_subfolder = case_dir / "extracted"
    elif vendor == "dahua":
        recovery_tier = "tier1"
        target_parser = "src.tier1.dahua"
        parsed_frames = parse_dahua_file(ingested_path)
        for frame in parsed_frames:
            extracted_video_bytes += raw_data[
                frame.payload_offset : frame.payload_offset + frame.payload_size
            ]
        target_subfolder = case_dir / "extracted"
    else:
        recovery_tier = "tier2"
        target_parser = "src.tier2.carver"
        carved_frames = scan_nal_units(ingested_path)
        parsed_frames = carved_frames
        for frame in carved_frames:
            extracted_video_bytes += raw_data[
                frame.offset : frame.offset + frame.size
            ]
        target_subfolder = case_dir / "recovered"

    target_subfolder.mkdir(parents=True, exist_ok=True)
    base_name = ingested_path.stem
    raw_h264_path = target_subfolder / f"{base_name}_extracted.h264"

    with open(raw_h264_path, "wb") as f:
        f.write(extracted_video_bytes)

    # Step 5: Prepend SPS/PPS if missing and Remux to MP4 using -c copy
    prep_stream_path = ensure_sps_pps(raw_h264_path)
    final_mp4_path = target_subfolder / f"{base_name}_standardized.mp4"

    remux_res = remux_to_mp4(prep_stream_path, final_mp4_path)

    # Step 6: Record timeline events in database if DB connection is active
    timeline_events_recorded = 0
    if db_conn is not None and evidence_id:
        if recovery_tier == "tier1":
            timeline_events_recorded = record_tier1_events(
                conn=db_conn, evidence_file_id=evidence_id, frames=parsed_frames
            )
        else:
            timeline_events_recorded = record_tier2_events(
                conn=db_conn, evidence_file_id=evidence_id, carved_frames=parsed_frames
            )

    # Step 7: Compute derived hashes on output file or extracted bytes
    if remux_res["success"] and final_mp4_path.exists():
        derived_hashes = compute_hashes(final_mp4_path)
        derived_output_path = str(final_mp4_path.resolve())
    else:
        derived_hashes = compute_bytes_hashes(bytes(extracted_video_bytes))
        derived_output_path = str(raw_h264_path.resolve())

    # Step 8: Update database record
    if db_conn is not None and evidence_id:
        update_evidence_file_derived_hashes(
            conn=db_conn,
            evidence_file_id=evidence_id,
            derived_md5=derived_hashes["md5"],
            derived_sha256=derived_hashes["sha256"],
            status="processed",
        )

    return {
        "evidence_id": evidence_id,
        "case_id": case_id,
        "source_path": str(file_path),
        "ingested_path": str(ingested_path),
        "derived_output_path": derived_output_path,
        "vendor": vendor,
        "recovery_tier": recovery_tier,
        "target_parser": target_parser,
        "original_md5": ingest_record["original_md5"],
        "original_sha256": ingest_record["original_sha256"],
        "derived_md5": derived_hashes["md5"],
        "derived_sha256": derived_hashes["sha256"],
        "frame_count": len(parsed_frames),
        "extracted_bytes_count": len(extracted_video_bytes),
        "timeline_events_recorded": timeline_events_recorded,
        "remux_success": remux_res["success"],
        "status": "processed",
    }
