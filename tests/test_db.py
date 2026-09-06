import inspect
import sqlite3
import pytest
from pathlib import Path
from src.db.connection import get_connection
from src.db.models import (
    create_case,
    get_case,
    create_evidence_file,
    get_evidence_files_for_case,
    update_evidence_file_derived_hashes,
    create_timeline_event,
    get_timeline_for_case,
)


@pytest.fixture
def db_conn(tmp_path: Path):
    db_file = tmp_path / "test_forensics.db"
    conn = get_connection(db_file)
    yield conn
    conn.close()


def test_wal_mode_and_foreign_keys(db_conn: sqlite3.Connection):
    """Verify that journal_mode is WAL and foreign keys are enabled."""
    cursor = db_conn.cursor()

    cursor.execute("PRAGMA journal_mode;")
    mode = cursor.fetchone()[0]
    assert mode.lower() == "wal"

    cursor.execute("PRAGMA foreign_keys;")
    fk_enabled = cursor.fetchone()[0]
    assert fk_enabled == 1


def test_validation_confidence_check_constraint(db_conn: sqlite3.Connection):
    """Verify that invalid validation_confidence values are rejected by schema CHECK constraint."""
    case = create_case(db_conn, "Invalid Confidence Test Case")

    # Valid values should succeed
    valid_confidences = [
        "Validated: Real Device",
        "Validated: Synthetic Reference Data",
        "Stub: Awaiting Hardware",
    ]
    for idx, conf in enumerate(valid_confidences):
        create_evidence_file(
            db_conn,
            case_id=case["id"],
            path=f"/path/to/file_{idx}.dav",
            original_md5="d41d8cd98f00b204e9800998ecf8427e",
            original_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            size_bytes=1024,
            file_type="DAV",
            vendor="Dahua",
            validation_confidence=conf,
        )

    # Invalid value must raise sqlite3.IntegrityError
    with pytest.raises(sqlite3.IntegrityError):
        create_evidence_file(
            db_conn,
            case_id=case["id"],
            path="/path/to/invalid.dav",
            original_md5="d41d8cd98f00b204e9800998ecf8427e",
            original_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            size_bytes=1024,
            file_type="DAV",
            vendor="Dahua",
            validation_confidence="Invalid: Fake Confidence Tag",
        )


def test_precision_check_constraint(db_conn: sqlite3.Connection):
    """Verify that invalid timeline precision values are rejected by schema CHECK constraint."""
    case = create_case(db_conn, "Precision Test Case")
    ev = create_evidence_file(
        db_conn,
        case_id=case["id"],
        path="/path/to/file.mp4",
        original_md5="d41d8cd98f00b204e9800998ecf8427e",
        original_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        size_bytes=2048,
        file_type="MP4",
        vendor="Hikvision",
        validation_confidence="Validated: Real Device",
    )

    # Valid precisions
    create_timeline_event(
        db_conn, ev["id"], "2026-09-06T12:00:00Z", "exact", channel=1
    )
    create_timeline_event(
        db_conn,
        ev["id"],
        "2026-09-06T12:05:00Z",
        "approximate",
        confidence_window_seconds=10,
    )

    # Invalid precision must fail
    with pytest.raises(sqlite3.IntegrityError):
        create_timeline_event(
            db_conn, ev["id"], "2026-09-06T12:10:00Z", "guesswork"
        )


def test_no_raw_video_bytes_stored_constraint():
    """Assert by construction: create_evidence_file signature accepts no binary video blob parameter."""
    sig = inspect.signature(create_evidence_file)
    param_names = list(sig.parameters.keys())
    assert "video_bytes" not in param_names
    assert "data" not in param_names
    assert "blob" not in param_names
    assert "content" not in param_names


def test_crud_round_trip(db_conn: sqlite3.Connection):
    """Test full CRUD cycle for case -> evidence file -> timeline event."""
    # 1. Create Case
    case = create_case(db_conn, "Case #2026-001")
    assert case["name"] == "Case #2026-001"

    fetched_case = get_case(db_conn, case["id"])
    assert fetched_case is not None
    assert fetched_case["name"] == "Case #2026-001"

    # 2. Add Evidence File
    ev = create_evidence_file(
        db_conn,
        case_id=case["id"],
        path="/evidence_store/case_001/raw_images/dahua_01.dav",
        original_md5="abc123md5",
        original_sha256="def456sha256",
        size_bytes=52428800,
        file_type="DAV",
        vendor="Dahua",
        captured_at="2026-09-01T08:30:00Z",
        validation_confidence="Validated: Real Device",
    )
    assert ev["case_id"] == case["id"]
    assert ev["status"] == "ingested"

    ev_files = get_evidence_files_for_case(db_conn, case["id"])
    assert len(ev_files) == 1
    assert ev_files[0]["id"] == ev["id"]

    # 3. Update Derived Hashes
    update_evidence_file_derived_hashes(
        db_conn,
        evidence_file_id=ev["id"],
        derived_md5="newmd5_789",
        derived_sha256="newsha256_012",
        status="processed",
    )
    updated_files = get_evidence_files_for_case(db_conn, case["id"])
    assert updated_files[0]["derived_md5"] == "newmd5_789"
    assert updated_files[0]["derived_sha256"] == "newsha256_012"
    assert updated_files[0]["status"] == "processed"

    # 4. Create Timeline Events
    evt1 = create_timeline_event(
        db_conn,
        evidence_file_id=ev["id"],
        event_time="2026-09-01T08:30:00Z",
        precision="exact",
        channel=1,
        description="Camera 1 recording start",
    )
    evt2 = create_timeline_event(
        db_conn,
        evidence_file_id=ev["id"],
        event_time="2026-09-01T08:35:00Z",
        precision="approximate",
        confidence_window_seconds=5,
        description="Carved H.264 frame sequence",
    )

    timeline = get_timeline_for_case(db_conn, case["id"])
    assert len(timeline) == 2
    assert timeline[0]["id"] == evt1["id"]
    assert timeline[0]["precision"] == "exact"
    assert timeline[1]["id"] == evt2["id"]
    assert timeline[1]["precision"] == "approximate"
    assert timeline[1]["confidence_window_seconds"] == 5
