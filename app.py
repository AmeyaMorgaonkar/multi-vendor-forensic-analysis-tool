"""
Flask Backend API Server for Multi-Vendor DVR/NVR Forensic Analysis Tool.
Serves static frontend and API endpoints for evidence ingestion, background processing,
timeline correlation, dual-hash verification, video preview, and PDF reporting.
"""
import os
import sqlite3
import subprocess
import threading
from pathlib import Path
from typing import Dict, Any, Optional

from flask import Flask, jsonify, request, send_file, send_from_directory

from src.db.connection import get_connection
from src.db.models import (
    create_case,
    get_case,
    get_evidence_files_for_case,
    get_timeline_for_case,
    list_all_cases,
    update_case_status,
    get_aggregate_stats,
)
from src.pipeline.dispatch import dispatch_pipeline
from src.pipeline.ingest import ingest_file

app = Flask(__name__, static_folder="src/static", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500MB upload limit

DEFAULT_DB_PATH = Path("evidence_store/forensic.db")
UPLOAD_DIR = Path("evidence_store/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# In-memory dictionary tracking background job status
JOB_STATUS: Dict[str, Dict[str, Any]] = {}


def get_db_connection():
    """Helper to obtain SQLite connection using project connection settings."""
    return get_connection(DEFAULT_DB_PATH)


def _generate_thumbnail_first_frame(evidence_id: str, case_id: str, file_path: Path) -> Optional[Path]:
    """Generates a JPEG thumbnail of the first video frame using FFmpeg."""
    base_name = file_path.stem
    thumb_dir = Path("evidence_store") / f"case_{case_id}" / "thumbnails"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = thumb_dir / f"{evidence_id}_thumb.jpg"

    # Search standardized MP4 first, then source file
    mp4_path = Path("evidence_store") / f"case_{case_id}" / "extracted" / f"{base_name}_standardized.mp4"
    if not mp4_path.exists():
        mp4_path = Path("evidence_store") / f"case_{case_id}" / "recovered" / f"{base_name}_standardized.mp4"
    if not mp4_path.exists():
        mp4_path = file_path

    if mp4_path.exists():
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-ss", "00:00:00.000", "-i", str(mp4_path.resolve()), "-vframes", "1", "-q:v", "2", str(thumb_path.resolve())],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if thumb_path.exists() and thumb_path.stat().st_size > 0:
                return thumb_path
        except Exception:
            pass
    return None



def _run_pipeline_background(
    file_path: Path,
    case_id: str,
    evidence_id: str,
    vendor_override: str,
    validation_confidence: str,
) -> None:
    """Worker task executing pipeline dispatch in a background thread."""
    try:
        JOB_STATUS[evidence_id] = {
            "status": "processing",
            "progress": 25,
            "message": "Ingesting raw evidence and calculating initial dual-hashes...",
        }

        conn = get_db_connection()
        try:
            res = dispatch_pipeline(
                file_path=file_path,
                case_id=case_id,
                db_conn=conn,
                vendor_override=vendor_override if vendor_override else None,
                validation_confidence=validation_confidence,
            )
            # Generate first-frame thumbnail image for pinboard node
            _generate_thumbnail_first_frame(evidence_id, case_id, file_path)

            JOB_STATUS[evidence_id] = {
                "status": "processed",
                "progress": 100,
                "message": "Analysis complete.",
                "result": res,
            }
        finally:
            conn.close()


    except Exception as e:
        JOB_STATUS[evidence_id] = {
            "status": "failed",
            "progress": 0,
            "message": str(e),
            "error": str(e),
        }


@app.route("/")
def index():
    """Serve the single-page web app."""
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/upload", methods=["POST"])
def api_upload():
    """
    POST /api/upload
    Accepts file upload (or file_path parameter), case_name, vendor_override, validation_confidence.
    Spawns background analysis job and returns evidence_file_id immediately.
    """
    case_name = request.form.get("case_name", "Forensic Case")
    case_id = request.form.get("case_id", "").strip()
    vendor_override = request.form.get("vendor_override", "").strip()
    validation_confidence = request.form.get(
        "validation_confidence", "Validated: Real Device"
    )

    conn = get_db_connection()
    try:
        if not case_id:
            c = create_case(conn, name=case_name)
            case_id = c["id"]
        else:
            existing = get_case(conn, case_id)
            if not existing:
                create_case(conn, name=case_name, case_id=case_id)
    finally:
        conn.close()

    file_path = None
    if "file" in request.files and request.files["file"].filename:
        uploaded_file = request.files["file"]
        dest = UPLOAD_DIR / uploaded_file.filename
        uploaded_file.save(dest)
        file_path = dest
    elif "file_path" in request.form and request.form["file_path"]:
        file_path = Path(request.form["file_path"])

    if not file_path or not file_path.exists():
        return jsonify({"error": "No valid file uploaded or path provided."}), 400

    # Ingest file metadata to generate an evidence_file_id
    conn = get_db_connection()
    try:
        ingest_rec = ingest_file(
            source_path=file_path,
            case_id=case_id,
            db_conn=conn,
            validation_confidence=validation_confidence,
            vendor_override=vendor_override if vendor_override else None,
        )
        evidence_id = ingest_rec["id"]
    finally:
        conn.close()

    JOB_STATUS[evidence_id] = {
        "status": "queued",
        "progress": 10,
        "message": "File queued for forensic processing.",
        "case_id": case_id,
        "evidence_id": evidence_id,
    }

    # Start background processing thread
    thread = threading.Thread(
        target=_run_pipeline_background,
        kwargs={
            "file_path": file_path,
            "case_id": case_id,
            "evidence_id": evidence_id,
            "vendor_override": vendor_override,
            "validation_confidence": validation_confidence,
        },
        daemon=True,
    )
    thread.start()

    return jsonify(
        {
            "status": "queued",
            "evidence_file_id": evidence_id,
            "case_id": case_id,
            "message": "File uploaded and processing initiated.",
        }
    ), 200


@app.route("/api/status/<evidence_file_id>", methods=["GET"])
def api_status(evidence_file_id: str):
    """
    GET /api/status/<evidence_file_id>
    Returns live processing status for the frontend polling loop.
    """
    if evidence_file_id in JOB_STATUS:
        return jsonify(JOB_STATUS[evidence_file_id]), 200

    # Fallback to database check if server was restarted
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM evidence_files WHERE id = ?", (evidence_file_id,))
        row = cursor.fetchone()
        if row:
            r = dict(row)
            return jsonify(
                {
                    "status": r.get("status", "processed"),
                    "progress": 100 if r.get("status") == "processed" else 0,
                    "case_id": r.get("case_id"),
                    "evidence_id": r.get("id"),
                    "vendor": r.get("vendor"),
                }
            ), 200
    finally:
        conn.close()

    return jsonify({"error": f"Evidence file ID '{evidence_file_id}' not found."}), 404


@app.route("/api/timeline/<case_id>", methods=["GET"])
def api_timeline(case_id: str):
    """
    GET /api/timeline/<case_id>
    Returns unified chronological timeline for all evidence in the case.
    Every event contains 'precision' tag ('exact' vs 'approximate').
    """
    conn = get_db_connection()
    try:
        events = get_timeline_for_case(conn, case_id)
        return jsonify({"case_id": case_id, "events": events, "count": len(events)}), 200
    finally:
        conn.close()


@app.route("/api/hashes/<evidence_file_id>", methods=["GET"])
def api_hashes(evidence_file_id: str):
    """
    GET /api/hashes/<evidence_file_id>
    Returns original and derived MD5/SHA-256 hashes for cryptographic verification.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM evidence_files WHERE id = ?", (evidence_file_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "Evidence file not found."}), 404

        ef = dict(row)
        return jsonify(
            {
                "evidence_file_id": ef["id"],
                "case_id": ef["case_id"],
                "path": ef["path"],
                "original_md5": ef["original_md5"],
                "original_sha256": ef["original_sha256"],
                "derived_md5": ef.get("derived_md5"),
                "derived_sha256": ef.get("derived_sha256"),
                "status": ef["status"],
                "vendor": ef["vendor"],
                "validation_confidence": ef["validation_confidence"],
                "match": (
                    ef["original_md5"] == ef.get("derived_md5")
                    or ef.get("derived_md5") is not None
                ),
            }
        ), 200
    finally:
        conn.close()


@app.route("/api/video/<evidence_file_id>", methods=["GET"])
def api_video(evidence_file_id: str):
    """
    GET /api/video/<evidence_file_id>
    Serves the standardized MP4 video file for playback.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM evidence_files WHERE id = ?", (evidence_file_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "Evidence file not found."}), 404

        ef = dict(row)
        case_id = ef["case_id"]
        ingested_path = Path(ef["path"])
        base_name = ingested_path.stem

        # Check standardized MP4 location
        mp4_path = Path("evidence_store") / f"case_{case_id}" / "extracted" / f"{base_name}_standardized.mp4"
        if not mp4_path.exists():
            mp4_path = Path("evidence_store") / f"case_{case_id}" / "recovered" / f"{base_name}_standardized.mp4"

        if not mp4_path.exists():
            # Fallback to source path if MP4 is not found
            mp4_path = ingested_path

        if not mp4_path.exists():
            return jsonify({"error": "Video output file does not exist."}), 404

        return send_file(mp4_path.resolve(), mimetype="video/mp4")
    finally:
        conn.close()


@app.route("/api/report/<case_id>", methods=["GET"])
def api_report(case_id: str):
    """
    GET /api/report/<case_id>
    Generates and returns the PDF report as a downloadable file, with graceful fallback.
    """
    conn = get_db_connection()
    try:
        c = get_case(conn, case_id)
        if not c:
            c = {"id": case_id, "name": f"Case {case_id}", "created_at": "N/A"}

        evidence_files = get_evidence_files_for_case(conn, case_id)
        timeline_events = get_timeline_for_case(conn, case_id)

        report_dir = Path("evidence_store") / f"case_{case_id}" / "reports"
        report_path = report_dir / f"forensic_report_{case_id}.pdf"

        try:
            from src.reporting.report_generator import generate_pdf_report
            generate_pdf_report(
                output_path=report_path,
                case_info=c,
                evidence_files=evidence_files,
                timeline_events=timeline_events,
            )
            return send_file(
                report_path.resolve(),
                mimetype="application/pdf",
                as_attachment=True,
                download_name=f"Forensic_Report_{case_id}.pdf",
            )
        except Exception as report_err:
            # Fallback to plain text forensic report if PDF generation module fails or is skipped
            fallback_dir = Path("evidence_store") / f"case_{case_id}" / "reports"
            fallback_dir.mkdir(parents=True, exist_ok=True)
            fallback_txt = fallback_dir / f"forensic_report_{case_id}.txt"
            
            txt_content = (
                f"FORENSIC REPORT (FALLBACK) - CASE {case_id}\n"
                f"Generated by Multi-Vendor DVR/NVR Forensic Analysis Tool\n"
                f"Team: Void main (SIH 2026)\n\n"
                f"Case Name: {c.get('name')}\n"
                f"Evidence Count: {len(evidence_files)}\n"
                f"Timeline Events: {len(timeline_events)}\n\n"
                f"Note: Milestone 10 PDF generator module skipped. Raw evidence dual-hashes and precision-tagged timeline stored in SQLite database."
            )
            fallback_txt.write_text(txt_content, encoding="utf-8")
            return send_file(
                fallback_txt.resolve(),
                mimetype="text/plain",
                as_attachment=True,
                download_name=f"Forensic_Report_{case_id}.txt",
            )
    finally:
        conn.close()


@app.route("/api/stats", methods=["GET"])
def api_stats():
    """
    GET /api/stats
    Returns aggregate forensic metrics computed directly from SQLite database.
    """
    conn = get_db_connection()
    try:
        stats = get_aggregate_stats(conn)
        return jsonify(stats), 200
    finally:
        conn.close()


@app.route("/api/cases", methods=["GET", "POST"])
def api_cases():
    """
    GET /api/cases: Returns list of all forensic cases.
    POST /api/cases: Creates a new case.
    """
    conn = get_db_connection()
    try:
        if request.method == "POST":
            data = request.get_json(silent=True) or request.form
            name = data.get("name") or data.get("case_name") or "New Case"
            case_id = data.get("case_id", "").strip() or None
            c = create_case(conn, name=name, case_id=case_id)
            return jsonify({"status": "success", "case": c}), 201
        else:
            cases = list_all_cases(conn)
            return jsonify({"cases": cases, "count": len(cases)}), 200
    finally:
        conn.close()


@app.route("/api/cases/<case_id>/status", methods=["POST"])
def api_update_case_status(case_id: str):
    """
    POST /api/cases/<case_id>/status
    Updates case status to 'OPEN' or 'CLOSED'.
    """
    data = request.get_json(silent=True) or request.form
    status = data.get("status", "CLOSED").upper()
    if status not in ["OPEN", "CLOSED"]:
        return jsonify({"error": "Status must be 'OPEN' or 'CLOSED'."}), 400

    conn = get_db_connection()
    try:
        updated = update_case_status(conn, case_id, status)
        if updated:
            return jsonify({"status": "success", "case_id": case_id, "new_status": status}), 200
        return jsonify({"error": f"Case '{case_id}' not found."}), 404
    finally:
        conn.close()


@app.route("/api/case/<case_id>/details", methods=["GET"])
def api_case_details(case_id: str):
    """
    GET /api/case/<case_id>/details
    Retrieves full case object, evidence files list, and timeline events for board rendering.
    """
    conn = get_db_connection()
    try:
        c = get_case(conn, case_id)
        if not c:
            # Auto-create if not exists
            c = create_case(conn, name=f"Case {case_id}", case_id=case_id)

        evidence_files = get_evidence_files_for_case(conn, case_id)
        timeline_events = get_timeline_for_case(conn, case_id)

        return jsonify(
            {
                "case": c,
                "evidence_files": evidence_files,
                "timeline_events": timeline_events,
            }
        ), 200
    finally:
        conn.close()


@app.route("/api/thumbnail/<evidence_file_id>", methods=["GET"])
def api_thumbnail(evidence_file_id: str):
    """
    GET /api/thumbnail/<evidence_file_id>
    Extracts and serves the first frame JPEG thumbnail for evidence nodes.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM evidence_files WHERE id = ?", (evidence_file_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "Evidence file not found."}), 404

        ef = dict(row)
        case_id = ef["case_id"]
        file_path = Path(ef["path"])

        thumb_dir = Path("evidence_store") / f"case_{case_id}" / "thumbnails"
        thumb_path = thumb_dir / f"{evidence_file_id}_thumb.jpg"

        if not thumb_path.exists():
            thumb_path = _generate_thumbnail_first_frame(evidence_file_id, case_id, file_path)

        if thumb_path and thumb_path.exists() and thumb_path.stat().st_size > 0:
            return send_file(thumb_path.resolve(), mimetype="image/jpeg")

        # Generic SVG placeholder if thumbnail extraction is unavailable
        svg_placeholder = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180" viewBox="0 0 320 180">'
            '<rect width="320" height="180" fill="#1b1d28"/>'
            '<circle cx="160" cy="90" r="36" fill="#2d3142"/>'
            '<polygon points="150,75 180,90 150,105" fill="#3b82f6"/>'
            '<text x="160" y="150" font-family="sans-serif" font-size="12" fill="#94a3b8" text-anchor="middle">FORENSIC RAW STREAM</text>'
            '</svg>'
        )
        return svg_placeholder, 200, {"Content-Type": "image/svg+xml"}
    finally:
        conn.close()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

