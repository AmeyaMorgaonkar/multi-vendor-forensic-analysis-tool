import sqlite3
from pathlib import Path
import pytest

from src.db.connection import get_connection
from src.db.models import create_case, create_evidence_file
from src.pipeline.timeline import (
    record_tier1_events,
    record_tier2_events,
    get_unified_timeline,
)
from src.tier1 import FrameHeader
from src.tier2 import CarvedFrame


@pytest.fixture
def db_conn(tmp_path: Path):
    db_file = tmp_path / "test_timeline.db"
    conn = get_connection(db_file)
    yield conn
    conn.close()


def test_record_tier1_exact_events(db_conn: sqlite3.Connection):
    """
    Verify Tier 1 events are always recorded with precision='exact'
    and confidence_window_seconds=None.
    """
    case = create_case(db_conn, "Tier 1 Timeline Case")
    ev = create_evidence_file(
        db_conn,
        case_id=case["id"],
        path="/path/to/hik.dav",
        original_md5="md5_1",
        original_sha256="sha256_1",
        size_bytes=1024,
        file_type="DAV",
        vendor="hikvision",
        validation_confidence="Validated: Real Device",
    )

    frames = [
        FrameHeader(
            vendor="hikvision",
            offset=0,
            frame_type=1,
            frame_size=100,
            timestamp=1788696000,
            channel=1,
            is_keyframe=True,
        ),
        FrameHeader(
            vendor="hikvision",
            offset=100,
            frame_type=2,
            frame_size=100,
            timestamp=1788696002,
            channel=1,
            is_keyframe=False,
        ),
    ]

    count = record_tier1_events(db_conn, ev["id"], frames)
    assert count == 2

    timeline = get_unified_timeline(db_conn, case["id"])
    assert len(timeline) == 2
    for evt in timeline:
        assert evt["precision"] == "exact"
        assert evt["confidence_window_seconds"] is None
        assert evt["vendor"] == "hikvision"


def test_record_tier2_approximate_events(db_conn: sqlite3.Connection):
    """
    Verify Tier 2 events are always recorded with precision='approximate'
    and a non-null confidence_window_seconds.
    """
    case = create_case(db_conn, "Tier 2 Timeline Case")
    ev = create_evidence_file(
        db_conn,
        case_id=case["id"],
        path="/path/to/carved.bin",
        original_md5="md5_2",
        original_sha256="sha256_2",
        size_bytes=2048,
        file_type="BIN",
        vendor="unknown",
        validation_confidence="Validated: Synthetic Reference Data",
    )

    carved_frames = [
        CarvedFrame(
            offset=0,
            size=150,
            nal_unit_type=7,
            is_keyframe=True,
            validation_confidence="approximate",
        ),
        CarvedFrame(
            offset=150,
            size=200,
            nal_unit_type=1,
            is_keyframe=False,
            validation_confidence="approximate",
        ),
    ]

    count = record_tier2_events(
        db_conn, ev["id"], carved_frames, confidence_window_seconds=5
    )
    assert count == 2

    timeline = get_unified_timeline(db_conn, case["id"])
    assert len(timeline) == 2
    for evt in timeline:
        assert evt["precision"] == "approximate"
        assert evt["confidence_window_seconds"] == 5
        assert evt["vendor"] == "unknown"


def test_unified_timeline_chronological_sorting(db_conn: sqlite3.Connection):
    """
    Verify get_unified_timeline merges Tier 1 and Tier 2 events, sorts them
    chronologically by event_time, and preserves precision tags.
    """
    case = create_case(db_conn, "Mixed Timeline Case")
    ev_t1 = create_evidence_file(
        db_conn,
        case_id=case["id"],
        path="/path/to/t1.dav",
        original_md5="md5_t1",
        original_sha256="sha256_t1",
        size_bytes=500,
        file_type="DAV",
        vendor="dahua",
        validation_confidence="Validated: Real Device",
    )
    ev_t2 = create_evidence_file(
        db_conn,
        case_id=case["id"],
        path="/path/to/t2.bin",
        original_md5="md5_t2",
        original_sha256="sha256_t2",
        size_bytes=500,
        file_type="BIN",
        vendor="unknown",
        validation_confidence="Validated: Synthetic Reference Data",
    )

    # Insert Tier 1 frame at t=1788696010
    record_tier1_events(
        db_conn,
        ev_t1["id"],
        [
            FrameHeader(
                vendor="dahua",
                offset=0,
                frame_type=1,
                frame_size=100,
                timestamp=1788696010,
                channel=1,
                is_keyframe=True,
            )
        ],
    )

    # Insert Tier 2 frame at t=1788696000 (earlier than Tier 1)
    record_tier2_events(
        db_conn,
        ev_t2["id"],
        [
            CarvedFrame(
                offset=0,
                size=100,
                nal_unit_type=5,
                is_keyframe=True,
            )
        ],
        base_timestamp=1788696000,
        confidence_window_seconds=5,
    )

    timeline = get_unified_timeline(db_conn, case["id"])
    assert len(timeline) == 2

    # Chronological sort check: t2 event (1788696000) must appear before t1 event (1788696010)
    assert timeline[0]["precision"] == "approximate"
    assert timeline[0]["confidence_window_seconds"] == 5

    assert timeline[1]["precision"] == "exact"
    assert timeline[1]["confidence_window_seconds"] is None
