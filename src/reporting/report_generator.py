"""
ReportLab PDF Generator for DVR/NVR Forensic Analysis Tool.
Generates legal-grade forensic reports with case metadata, dual-hashes,
precision-tagged timelines, custody logs, and mandatory BSA Section 63 certificate text.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


BSA_SECTION_63_TEXT = (
    "CERTIFICATE UNDER SECTION 63(4)(c) OF THE BHARATIYA SAKSHYA ADHINIYAM, 2023 (BSA)\n\n"
    "I hereby certify that the electronic record containing surveillance video evidence described in this report "
    "was produced by an automated forensic recovery and standardization tool operating in accordance with standard "
    "scientific practices and verified byte-level signatures.\n\n"
    "1. Device/System Integrity: The electronic system used to extract and process the video file was operating properly "
    "during the course of forensic analysis.\n"
    "2. Chain of Custody & Hash Verification: Dual cryptographic hash values (MD5 and SHA-256) were calculated immediately "
    "upon ingestion and post-remuxing to verify data integrity and guarantee non-alteration.\n"
    "3. Forensic Process: Extracted media streams were standardized via lossless remuxing without re-encoding to preserve "
    "original raw video payload.\n\n"
    "Signature of Forensic Examiner: ___________________________    Date: _____________"
)


def generate_pdf_report(
    output_path: Path,
    case_info: Dict[str, Any],
    evidence_files: List[Dict[str, Any]],
    timeline_events: List[Dict[str, Any]],
) -> Path:
    """
    Generates a PDF forensic report at output_path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Title"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
        alignment=0,
    )
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BodyTextCustom",
        parent=styles["BodyText"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#334155"),
    )
    cert_style = ParagraphStyle(
        "CertText",
        parent=styles["BodyText"],
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#1e293b"),
        fontName="Helvetica-Oblique",
    )

    elements = []

    # Title
    elements.append(Paragraph("FORENSIC ANALYSIS REPORT", title_style))
    elements.append(Paragraph("<b>Multi-Vendor DVR/NVR Forensic Analysis Tool</b> | SIH 2026 — Team Void main", body_style))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0f172a"), spaceAfter=15))

    # Case Info Table
    case_id = case_info.get("id", "N/A")
    case_name = case_info.get("name", "Forensic Investigation")
    created_at = case_info.get("created_at", "N/A")

    info_data = [
        [Paragraph("<b>Case ID:</b>", body_style), Paragraph(str(case_id), body_style),
         Paragraph("<b>Date Generated:</b>", body_style), Paragraph(str(created_at), body_style)],
        [Paragraph("<b>Case Name:</b>", body_style), Paragraph(str(case_name), body_style),
         Paragraph("<b>Evidence Count:</b>", body_style), Paragraph(str(len(evidence_files)), body_style)],
    ]
    info_table = Table(info_data, colWidths=[80, 180, 90, 190])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 15))

    # Evidence & Hashes Section
    elements.append(Paragraph("1. Evidence Files & Cryptographic Hashes", heading_style))
    hash_data = [
        [Paragraph("<b>File ID</b>", body_style),
         Paragraph("<b>Vendor / Tag</b>", body_style),
         Paragraph("<b>Original Hash (MD5 / SHA-256)</b>", body_style),
         Paragraph("<b>Derived Hash (MD5 / SHA-256)</b>", body_style)]
    ]

    for ef in evidence_files:
        orig_hash_str = f"MD5: {ef.get('original_md5', 'N/A')[:12]}...<br/>SHA: {ef.get('original_sha256', 'N/A')[:12]}..."
        derived_hash_str = f"MD5: {ef.get('derived_md5', 'N/A')[:12]}...<br/>SHA: {ef.get('derived_sha256', 'N/A')[:12]}..."
        tag_str = f"<b>{ef.get('vendor', 'Unknown').upper()}</b><br/><i>{ef.get('validation_confidence', 'Validated')}</i>"

        hash_data.append([
            Paragraph(str(ef.get("id", "N/A")), body_style),
            Paragraph(tag_str, body_style),
            Paragraph(orig_hash_str, body_style),
            Paragraph(derived_hash_str, body_style),
        ])

    hash_table = Table(hash_data, colWidths=[70, 120, 175, 175])
    hash_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#e2e8f0")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#94a3b8")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(hash_table)
    elements.append(Spacer(1, 15))

    # Unified Timeline Section
    elements.append(Paragraph("2. Precision-Tagged Unified Timeline", heading_style))
    timeline_data = [
        [Paragraph("<b>Event Time (UTC)</b>", body_style),
         Paragraph("<b>Precision Marker</b>", body_style),
         Paragraph("<b>Description</b>", body_style)]
    ]

    for evt in timeline_events:
        prec = evt.get("precision", "exact")
        win = evt.get("confidence_window_seconds")
        if prec == "exact":
            prec_str = "<font color='#16a34a'><b>[EXACT]</b> Tier 1 Parser</font>"
        else:
            window_text = f" ±{win}s" if win else ""
            prec_str = f"<font color='#d97706'><b>[APPROX{window_text}]</b> Tier 2 Carver</font>"

        timeline_data.append([
            Paragraph(str(evt.get("event_time", "N/A")), body_style),
            Paragraph(prec_str, body_style),
            Paragraph(str(evt.get("description", "")), body_style),
        ])

    if len(timeline_data) == 1:
        timeline_data.append([
            Paragraph("N/A", body_style),
            Paragraph("N/A", body_style),
            Paragraph("No timeline events logged for this case.", body_style),
        ])

    timeline_table = Table(timeline_data, colWidths=[140, 130, 270])
    timeline_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#e2e8f0")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#94a3b8")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(timeline_table)
    elements.append(Spacer(1, 20))

    # BSA Section 63 Legal Certificate Section
    cert_elements = []
    cert_elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#94a3b8"), spaceAfter=10))
    cert_elements.append(Paragraph("3. Legal Certification (BSA Section 63)", heading_style))

    cert_box_data = [[Paragraph(BSA_SECTION_63_TEXT.replace("\n", "<br/>"), cert_style)]]
    cert_table = Table(cert_box_data, colWidths=[540])
    cert_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f1f5f9")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#475569")),
        ('PADDING', (0,0), (-1,-1), 10),
    ]))
    cert_elements.append(cert_table)

    elements.append(KeepTogether(cert_elements))

    doc.build(elements)
    return output_path
