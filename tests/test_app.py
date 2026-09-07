"""
Unit and Integration Tests for Flask Web Server (Milestone 11 - app.py).
Verifies upload API endpoints, background execution status, timeline precision markers,
dual-hash verification, and host binding compliance.
"""
import pytest
from pathlib import Path
from app import app, get_db_connection
from src.db.models import create_case, create_evidence_file, create_timeline_event


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Flask test client fixture using isolated test DB."""
    test_db = tmp_path / "test_forensic.db"
    monkeypatch.setattr("app.DEFAULT_DB_PATH", test_db)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client



@pytest.fixture
def temp_sample_file(tmp_path):
    """Creates a dummy video file for upload testing."""
    sample_file = tmp_path / "sample_dahua.dav"
    sample_file.write_bytes(b"DHAV\x01\x00\x00\x00Dummy Dahua Header Content Payload Bytes 12345")
    return sample_file


def test_upload_missing_file(client):
    """Test that uploading without a file returns HTTP 400 Bad Request."""
    response = client.post("/api/upload", data={})
    assert response.status_code == 400
    json_data = response.get_json()
    assert "error" in json_data


def test_upload_valid_file(client, temp_sample_file):
    """Test that uploading a valid evidence file returns HTTP 200 OK and evidence_file_id."""
    with open(temp_sample_file, "rb") as f:
        response = client.post(
            "/api/upload",
            data={
                "file": (f, temp_sample_file.name),
                "case_name": "Test Case Upload",
                "vendor_override": "dahua",
                "validation_confidence": "Validated: Synthetic Reference Data",
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "queued"
    assert "evidence_file_id" in json_data
    assert "case_id" in json_data


def test_status_endpoint(client, temp_sample_file):
    """Test that GET /api/status/<evidence_file_id> returns valid status information."""
    with open(temp_sample_file, "rb") as f:
        res = client.post(
            "/api/upload",
            data={"file": (f, temp_sample_file.name)},
            content_type="multipart/form-data",
        )
    evidence_id = res.get_json()["evidence_file_id"]

    status_res = client.get(f"/api/status/{evidence_id}")
    assert status_res.status_code == 200
    status_json = status_res.get_json()
    assert "status" in status_json
    assert "progress" in status_json


def test_timeline_precision_tags(client):
    """Test that GET /api/timeline/<case_id> includes precision marker on every event."""
    conn = get_db_connection()
    try:
        c = create_case(conn, "Test Precision Case")
        case_id = c["id"]
        ef = create_evidence_file(
            conn=conn,
            case_id=case_id,
            path="evidence_store/test.raw",
            original_md5="d41d8cd98f00b204e9800998ecf8427e",
            original_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            size_bytes=100,
            file_type="raw",
            vendor="hikvision",
            validation_confidence="Validated: Synthetic Reference Data",
        )
        create_timeline_event(
            conn=conn,
            evidence_file_id=ef["id"],
            event_time="2026-09-07T12:00:00Z",
            precision="exact",
            description="Tier 1 exact event",
        )
        create_timeline_event(
            conn=conn,
            evidence_file_id=ef["id"],
            event_time="2026-09-07T12:05:00Z",
            precision="approximate",
            confidence_window_seconds=5,
            description="Tier 2 approximate carved event",
        )
    finally:
        conn.close()

    response = client.get(f"/api/timeline/{case_id}")
    assert response.status_code == 200
    json_data = response.get_json()
    assert "events" in json_data
    events = json_data["events"]
    assert len(events) == 2

    for evt in events:
        assert "precision" in evt
        assert evt["precision"] in ["exact", "approximate"]


def test_default_host_binding():
    """Verify that app.py host binding is strictly 127.0.0.1 (not 0.0.0.0)."""
    app_py_content = Path("app.py").read_text()
    assert 'app.run(host="127.0.0.1"' in app_py_content
    assert 'host="0.0.0.0"' not in app_py_content


def test_hashes_endpoint(client, temp_sample_file):
    """Test GET /api/hashes/<evidence_file_id> returns original and derived MD5/SHA256 hashes."""
    with open(temp_sample_file, "rb") as f:
        res = client.post(
            "/api/upload",
            data={"file": (f, temp_sample_file.name)},
            content_type="multipart/form-data",
        )
    evidence_id = res.get_json()["evidence_file_id"]

    hashes_res = client.get(f"/api/hashes/{evidence_id}")
    assert hashes_res.status_code == 200
    hashes_data = hashes_res.get_json()
    assert "original_md5" in hashes_data
    assert "original_sha256" in hashes_data
    assert "match" in hashes_data


def test_hashes_not_found(client):
    """Test GET /api/hashes/<invalid_id> returns HTTP 404."""
    res = client.get("/api/hashes/non_existent_id")
    assert res.status_code == 404


def test_video_not_found(client):
    """Test GET /api/video/<invalid_id> returns HTTP 404."""
    res = client.get("/api/video/non_existent_id")
    assert res.status_code == 404


def test_report_endpoint_fallback(client):
    """Test GET /api/report/<case_id> returns report download with graceful fallback."""
    res = client.get("/api/report/test_report_case_123")
    assert res.status_code == 200
    assert res.content_type in ["application/pdf", "text/plain"]


def test_stats_endpoint(client):
    """Test GET /api/stats returns real aggregate system metrics."""
    res = client.get("/api/stats")
    assert res.status_code == 200
    json_data = res.get_json()
    assert "total_cases" in json_data
    assert "total_evidence_files" in json_data
    assert "converted_files" in json_data
    assert "timeline_events_reviewed" in json_data
    assert "total_bytes_processed" in json_data


def test_cases_crud_and_status(client):
    """Test GET /api/cases, POST /api/cases, and POST /api/cases/<case_id>/status."""
    import uuid
    test_case_id = f"test_case_{uuid.uuid4().hex[:8]}"

    # Create new case
    post_res = client.post("/api/cases", json={"name": "Test Dynamic Case", "case_id": test_case_id})
    assert post_res.status_code == 201

    # List cases
    get_res = client.get("/api/cases")
    assert get_res.status_code == 200
    cases = get_res.get_json()["cases"]
    assert any(c["id"] == test_case_id for c in cases)

    # Update status to CLOSED
    status_res = client.post(f"/api/cases/{test_case_id}/status", json={"status": "CLOSED"})
    assert status_res.status_code == 200
    assert status_res.get_json()["new_status"] == "CLOSED"



def test_case_details_endpoint(client):
    """Test GET /api/case/<case_id>/details returns full case package."""
    res = client.get("/api/case/test_case_999/details")
    assert res.status_code == 200
    data = res.get_json()
    assert "case" in data
    assert "evidence_files" in data
    assert "timeline_events" in data


def test_thumbnail_endpoint(client, temp_sample_file):
    """Test GET /api/thumbnail/<evidence_file_id> serves thumbnail or SVG fallback."""
    with open(temp_sample_file, "rb") as f:
        upload_res = client.post(
            "/api/upload",
            data={"file": (f, temp_sample_file.name)},
            content_type="multipart/form-data",
        )
    evidence_id = upload_res.get_json()["evidence_file_id"]

    thumb_res = client.get(f"/api/thumbnail/{evidence_id}")
    assert thumb_res.status_code == 200
    assert thumb_res.content_type in ["image/jpeg", "image/svg+xml"]


