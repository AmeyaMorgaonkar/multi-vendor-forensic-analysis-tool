import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    return dict(row)


def create_case(
    conn: sqlite3.Connection, name: str, case_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Creates a new forensic case.
    """
    if not case_id:
        case_id = f"case_{uuid.uuid4().hex[:12]}"
    created_at = datetime.now(timezone.utc).isoformat()

    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO cases (id, name, created_at) VALUES (?, ?, ?)",
        (case_id, name, created_at),
    )
    conn.commit()

    return {"id": case_id, "name": name, "created_at": created_at}


def get_case(conn: sqlite3.Connection, case_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a case by ID.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
    row = cursor.fetchone()
    return _row_to_dict(row)


def create_evidence_file(
    conn: sqlite3.Connection,
    case_id: str,
    path: str,
    original_md5: str,
    original_sha256: str,
    size_bytes: int,
    file_type: str,
    vendor: str,
    validation_confidence: str,
    captured_at: Optional[str] = None,
    status: str = "ingested",
    derived_md5: Optional[str] = None,
    derived_sha256: Optional[str] = None,
    evidence_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Registers an evidence file for a case.
    Accepts file metadata, path, and hashes ONLY — strictly no raw video bytes.
    """
    if not evidence_id:
        evidence_id = f"ev_{uuid.uuid4().hex[:12]}"

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO evidence_files (
            id, case_id, path, original_md5, original_sha256,
            derived_md5, derived_sha256, size_bytes, file_type,
            vendor, captured_at, status, validation_confidence
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            evidence_id,
            case_id,
            path,
            original_md5,
            original_sha256,
            derived_md5,
            derived_sha256,
            size_bytes,
            file_type,
            vendor,
            captured_at,
            status,
            validation_confidence,
        ),
    )
    conn.commit()

    return {
        "id": evidence_id,
        "case_id": case_id,
        "path": path,
        "original_md5": original_md5,
        "original_sha256": original_sha256,
        "derived_md5": derived_md5,
        "derived_sha256": derived_sha256,
        "size_bytes": size_bytes,
        "file_type": file_type,
        "vendor": vendor,
        "captured_at": captured_at,
        "status": status,
        "validation_confidence": validation_confidence,
    }


def get_evidence_files_for_case(
    conn: sqlite3.Connection, case_id: str
) -> List[Dict[str, Any]]:
    """
    Retrieves all evidence files belonging to a specific case.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM evidence_files WHERE case_id = ?", (case_id,))
    rows = cursor.fetchall()
    return [dict(r) for r in rows]


def update_evidence_file_derived_hashes(
    conn: sqlite3.Connection,
    evidence_file_id: str,
    derived_md5: str,
    derived_sha256: str,
    status: str = "processed",
) -> None:
    """
    Updates the derived hashes and status of an evidence file post-processing/remux.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE evidence_files
        SET derived_md5 = ?, derived_sha256 = ?, status = ?
        WHERE id = ?
        """,
        (derived_md5, derived_sha256, status, evidence_file_id),
    )
    conn.commit()


def create_timeline_event(
    conn: sqlite3.Connection,
    evidence_file_id: str,
    event_time: str,
    precision: str,
    channel: Optional[int] = None,
    confidence_window_seconds: Optional[int] = None,
    description: Optional[str] = None,
    event_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a timeline event linked to an evidence file.
    Precision must be 'exact' or 'approximate'.
    """
    if not event_id:
        event_id = f"evt_{uuid.uuid4().hex[:12]}"

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO timeline_events (
            id, evidence_file_id, channel, event_time,
            precision, confidence_window_seconds, description
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            evidence_file_id,
            channel,
            event_time,
            precision,
            confidence_window_seconds,
            description,
        ),
    )
    conn.commit()

    return {
        "id": event_id,
        "evidence_file_id": evidence_file_id,
        "channel": channel,
        "event_time": event_time,
        "precision": precision,
        "confidence_window_seconds": confidence_window_seconds,
        "description": description,
    }


def get_timeline_for_case(
    conn: sqlite3.Connection, case_id: str
) -> List[Dict[str, Any]]:
    """
    Retrieves all timeline events associated with any evidence file in a given case,
    sorted chronologically by event_time.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT te.*, ef.vendor, ef.validation_confidence, ef.path
        FROM timeline_events te
        JOIN evidence_files ef ON te.evidence_file_id = ef.id
        WHERE ef.case_id = ?
        ORDER BY te.event_time ASC
        """,
        (case_id,),
    )
    rows = cursor.fetchall()
    return [dict(r) for r in rows]
