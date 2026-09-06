import os
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional, Union

from src.db.models import create_evidence_file
from src.pipeline.hashing import compute_hashes
from src.pipeline.vendor_id import detect_vendor

EVIDENCE_STORE_ROOT = Path("evidence_store")


def ingest_file(
    source_path: Union[str, Path],
    case_id: str,
    db_conn: Optional[sqlite3.Connection] = None,
    validation_confidence: str = "Validated: Real Device",
    vendor_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Forensically ingests an evidence video file:
      1. Validates source file integrity.
      2. Copies file to evidence_store/case_<case_id>/raw_images/ (never modifies source).
      3. Computes original MD5 and SHA-256 hashes immediately.
      4. Detects vendor via signature scanning.
      5. Registers evidence file record in SQLite database if db_conn is provided.

    :param source_path: Path to original source evidence file.
    :param case_id: Case identifier.
    :param db_conn: Optional open SQLite database connection.
    :param validation_confidence: One of 'Validated: Real Device', 'Validated: Synthetic Reference Data', 'Stub: Awaiting Hardware'.
    :param vendor_override: Optional manual vendor override string.
    :return: Evidence record dictionary.
    """
    src_path = Path(source_path)
    if not src_path.exists() or not src_path.is_file():
        raise FileNotFoundError(f"Source evidence file does not exist: {src_path}")

    file_size = src_path.stat().st_size
    if file_size == 0:
        raise ValueError(f"Source evidence file is empty: {src_path}")

    # Prepare evidence_store directory structure per constitution
    raw_images_dir = EVIDENCE_STORE_ROOT / f"case_{case_id}" / "raw_images"
    raw_images_dir.mkdir(parents=True, exist_ok=True)

    dest_path = raw_images_dir / src_path.name
    # Copy file to raw_images (never modify original source file)
    shutil.copy2(src_path, dest_path)

    # Compute original dual hashes immediately upon copy
    original_hashes = compute_hashes(dest_path)

    # Detect vendor on ingested copy
    vendor = detect_vendor(dest_path, vendor_override=vendor_override)
    file_type = src_path.suffix.lstrip(".").upper() or "BIN"

    evidence_record = {
        "case_id": case_id,
        "path": str(dest_path.resolve()),
        "original_md5": original_hashes["md5"],
        "original_sha256": original_hashes["sha256"],
        "size_bytes": file_size,
        "file_type": file_type,
        "vendor": vendor,
        "validation_confidence": validation_confidence,
        "status": "ingested",
    }

    if db_conn is not None:
        db_record = create_evidence_file(
            conn=db_conn,
            case_id=case_id,
            path=str(dest_path.resolve()),
            original_md5=original_hashes["md5"],
            original_sha256=original_hashes["sha256"],
            size_bytes=file_size,
            file_type=file_type,
            vendor=vendor,
            validation_confidence=validation_confidence,
            status="ingested",
        )
        evidence_record["id"] = db_record["id"]

    return evidence_record
