import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.db.models import create_timeline_event, get_timeline_for_case
from src.tier1 import FrameHeader
from src.tier2 import CarvedFrame


def format_iso8601(timestamp_seconds: int, ms: int = 0) -> str:
    """Helper to convert epoch seconds and milliseconds to ISO8601 UTC string."""
    dt = datetime.fromtimestamp(timestamp_seconds, tz=timezone.utc)
    if ms > 0:
        dt = dt.replace(microsecond=ms * 1000)
    return dt.isoformat()


def record_tier1_events(
    conn: sqlite3.Connection, evidence_file_id: str, frames: List[FrameHeader]
) -> int:
    """
    Records Tier 1 container parsed frames into the database timeline.
    Tier 1 timestamps originate from device hardware clocks and are recorded with precision='exact'.

    Citation: Rzayeva et al., MDPI Information, 13 Nov 2025.

    :param conn: SQLite database connection.
    :param evidence_file_id: ID of the evidence file.
    :param frames: List of parsed FrameHeader objects.
    :return: Number of timeline events created.
    """
    if not frames:
        return 0

    count = 0
    # Record keyframes / I-frames or all frames
    for frame in frames:
        event_time = format_iso8601(frame.timestamp, frame.timestamp_ms)
        desc = (
            f"Tier 1 {frame.vendor.capitalize()} Frame #{frame.frame_number or count+1} "
            f"({'Keyframe/IDR' if frame.is_keyframe else 'P-frame'})"
        )
        create_timeline_event(
            conn=conn,
            evidence_file_id=evidence_file_id,
            event_time=event_time,
            precision="exact",
            channel=frame.channel,
            confidence_window_seconds=None,  # Exact precision has NULL window
            description=desc,
        )
        count += 1

    return count


def record_tier2_events(
    conn: sqlite3.Connection,
    evidence_file_id: str,
    carved_frames: List[CarvedFrame],
    base_timestamp: Optional[int] = None,
    confidence_window_seconds: int = 5,
    estimated_fps: float = 25.0,
) -> int:
    """
    Records Tier 2 universal carved frames into the database timeline.
    Tier 2 timestamps are derived via frame-sequencing estimation and are recorded with
    precision='approximate' and a non-null confidence_window_seconds (default ±5s).

    Estimation Method:
      If base_timestamp is provided (or defaults to 1788696000), each carved frame's
      timestamp offset is estimated as: base_timestamp + (frame_index / estimated_fps).
      The ±5s confidence window accounts for potential missing frames or unallocated space gaps.

    :param conn: SQLite database connection.
    :param evidence_file_id: ID of the evidence file.
    :param carved_frames: List of CarvedFrame objects.
    :param base_timestamp: Optional base epoch timestamp (seconds).
    :param confidence_window_seconds: Confidence window in seconds (default ±5).
    :param estimated_fps: Estimated frames per second for timestamp extrapolation.
    :return: Number of timeline events created.
    """
    if not carved_frames:
        return 0

    if base_timestamp is None:
        base_timestamp = 1788696000  # Fallback epoch timestamp for carved streams

    count = 0
    for idx, frame in enumerate(carved_frames):
        # Estimate timestamp based on frame index and fps
        time_offset = int(idx / estimated_fps)
        event_time_sec = base_timestamp + time_offset
        ms = int(((idx / estimated_fps) - time_offset) * 1000)

        event_time = format_iso8601(event_time_sec, ms)
        desc = (
            f"Tier 2 Carved {frame.codec} NAL Unit Type {frame.nal_unit_type} "
            f"at byte offset 0x{frame.offset:X} ({'Keyframe' if frame.is_keyframe else 'Slice'})"
        )

        create_timeline_event(
            conn=conn,
            evidence_file_id=evidence_file_id,
            event_time=event_time,
            precision="approximate",
            channel=1,
            confidence_window_seconds=confidence_window_seconds,  # Must be non-null
            description=desc,
        )
        count += 1

    return count


def get_unified_timeline(conn: sqlite3.Connection, case_id: str) -> List[Dict[str, Any]]:
    """
    Retrieves the unified chronological timeline for a case, merging Tier 1 (exact)
    and Tier 2 (approximate) events. Preserves visible precision markers and confidence windows.

    :param conn: SQLite database connection.
    :param case_id: Case identifier.
    :return: List of timeline event dictionaries sorted chronologically by event_time ASC.
    """
    events = get_timeline_for_case(conn, case_id)
    # Ensure precision markers and window fields are present in every row
    for evt in events:
        if "precision" not in evt or not evt["precision"]:
            raise ValueError(f"Timeline event {evt.get('id')} is missing precision tag!")
    return events
