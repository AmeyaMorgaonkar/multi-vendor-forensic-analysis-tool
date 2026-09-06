import os
import sqlite3
from pathlib import Path
import pytest

from src.db.connection import get_connection
from src.db.models import create_case, get_evidence_files_for_case
from src.pipeline.hashing import compute_hashes, compute_bytes_hashes
from src.pipeline.ingest import ingest_file
from src.pipeline.dispatch import dispatch_pipeline
from tests.fixtures.generate_fixtures import generate_dahua_fixture


@pytest.fixture
def db_conn(tmp_path: Path):
    db_file = tmp_path / "test_forensics.db"
    conn = get_connection(db_file)
    yield conn
    conn.close()


@pytest.fixture
def source_sample_file(tmp_path: Path) -> Path:
    sample_file = tmp_path / "source_evidence.dav"
    generate_dahua_fixture(sample_file, num_frames=5)
    return sample_file


def test_compute_hashes_stability(source_sample_file: Path):
    """Verify compute_hashes returns identical deterministic hashes across repeated calls."""
    hashes1 = compute_hashes(source_sample_file)
    hashes2 = compute_hashes(source_sample_file)

    assert hashes1["md5"] == hashes2["md5"]
    assert hashes1["sha256"] == hashes2["sha256"]
    assert len(hashes1["md5"]) == 32
    assert len(hashes1["sha256"]) == 64


def test_source_file_immutability(tmp_path: Path, source_sample_file: Path):
    """
    CRITICAL FORENSIC INTEGRITY TEST:
    Verify that ingestion copies the file to evidence_store/ raw_images/ and leaves the
    original source file 100% untouched (same timestamp and MD5/SHA-256 hash).
    """
    original_mtime = source_sample_file.stat().st_mtime
    original_hashes = compute_hashes(source_sample_file)

    ingest_record = ingest_file(
        source_path=source_sample_file,
        case_id="case_immutability_test",
        validation_confidence="Validated: Synthetic Reference Data",
    )

    # Source file MUST be untouched
    assert source_sample_file.stat().st_mtime == original_mtime
    assert compute_hashes(source_sample_file) == original_hashes

    # Copied file MUST exist in evidence store
    dest_path = Path(ingest_record["path"])
    assert dest_path.exists()
    assert dest_path != source_sample_file
    assert compute_hashes(dest_path) == original_hashes


def test_streaming_chunked_hash_computation(source_sample_file: Path):
    """Verify compute_hashes with small chunk size produces identical hashes to standard read."""
    small_chunk_hashes = compute_hashes(source_sample_file, chunk_size=128)
    standard_hashes = compute_hashes(source_sample_file, chunk_size=65536)

    assert small_chunk_hashes["md5"] == standard_hashes["md5"]
    assert small_chunk_hashes["sha256"] == standard_hashes["sha256"]


def test_database_registration_on_ingest(db_conn: sqlite3.Connection, source_sample_file: Path):
    """Verify ingest_file registers evidence file metadata and hashes in SQLite."""
    case = create_case(db_conn, "Ingestion Test Case")
    ingest_record = ingest_file(
        source_path=source_sample_file,
        case_id=case["id"],
        db_conn=db_conn,
        validation_confidence="Validated: Real Device",
    )

    db_files = get_evidence_files_for_case(db_conn, case["id"])
    assert len(db_files) == 1
    assert db_files[0]["id"] == ingest_record["id"]
    assert db_files[0]["original_md5"] == ingest_record["original_md5"]
    assert db_files[0]["original_sha256"] == ingest_record["original_sha256"]
    assert db_files[0]["status"] == "ingested"


def test_dispatch_pipeline_end_to_end(db_conn: sqlite3.Connection, source_sample_file: Path):
    """Test full dispatch pipeline: Ingest -> Hash -> Parse -> Derive Hash -> Update DB."""
    case = create_case(db_conn, "End-to-End Pipeline Case")
    res = dispatch_pipeline(
        file_path=source_sample_file,
        case_id=case["id"],
        db_conn=db_conn,
        validation_confidence="Validated: Real Device",
    )

    assert res["status"] == "processed"
    assert res["vendor"] == "dahua"
    assert res["recovery_tier"] == "tier1"
    assert len(res["original_md5"]) == 32
    assert len(res["derived_md5"]) == 32
    assert res["frame_count"] > 0
    assert res["extracted_bytes_count"] > 0

    # Verify DB updated derived hashes
    db_files = get_evidence_files_for_case(db_conn, case["id"])
    assert len(db_files) == 1
    assert db_files[0]["derived_md5"] == res["derived_md5"]
    assert db_files[0]["derived_sha256"] == res["derived_sha256"]
    assert db_files[0]["status"] == "processed"
