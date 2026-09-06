# PROJECT_CONSTITUTION.md

## Project
Multi-Vendor DVR/NVR Forensic Analysis Tool — SIH 2026, PS ID 26150 (Blockchain & Cybersecurity), Team "Void main" (Team ID 6A6870).

One unified, vendor-agnostic platform for **acquisition, recovery, analysis, validation, and reporting** of DVR/NVR surveillance evidence, so investigators don't need a separate tool per manufacturer (Dahua, Hikvision, CP Plus, Honeywell, TP-Link, Godrej, Uniview, Matrix).

## Core Architecture Decision: Two-Tier Recovery
- **Tier 1** — deep, metadata-aware parsing for vendors with a known container format (Dahua "DHFS4.1", Hikvision). Gives exact timestamps, channel IDs, deleted-clip recovery.
- **Tier 2** — vendor-agnostic H.264/H.265 NAL-unit signature carving on raw bytes. Works on any vendor using standard codecs, including the 6 we have no sample files for. Gives approximate timestamps only.
- This split is the project's stated differentiator — it must always be presented as "honestly tested end-to-end for every vendor at some depth," never as full 8-vendor native support.

## Tech Stack (locked — do not deviate without asking the user)
- **Backend:** Python. No FastAPI, no Django. A single minimal Flask app (`app.py`) serves JSON endpoints and the static frontend — this replaces the original Streamlit plan while keeping "one thin layer, no heavy framework."
- **Frontend:** Plain HTML/CSS/JS only. **No React, no Streamlit, no other framework.** Vanilla JS with `fetch()` calls to the Flask endpoints.
- **Database:** SQLite only (never Postgres for this build). `PRAGMA journal_mode=WAL;` must be set on every connection.
- **Video:** FFmpeg via subprocess, remux only (`-c copy`), never re-encode.
- **PDF:** ReportLab only (never WeasyPrint — avoids GTK/Cairo dependency pain on Windows).
- **Blockchain:** `web3.py` against a local Ganache instance for Merkle-root anchoring. No Solidity contract is required for the core build — anchor by sending a raw signed transaction with the Merkle root embedded in the `data` field. (Deploying a custody smart contract is optional/out of scope for this build — see Forbidden.)
- **Dev OS:** Windows. All commands/paths must be Windows-safe (no bare `chmod`/POSIX-only assumptions).
- **No Docker.**

## Module Map (each is a `/milestone-*` workflow)
| Milestone | PS Module | Priority |
|---|---|---|
| `/milestone-vendor-id` | A1 Device/Vendor Identification | Core |
| `/milestone-tier1-parser` | A2 Dahua + Hikvision deep parsing | Core |
| `/milestone-tier2-recovery` | A3 Universal codec-level recovery | Core |
| `/milestone-acquisition-hashing` | A4 Acquisition & Hashing | Core |
| `/milestone-remux` | A5 Video Standardization | Core |
| `/milestone-database` | A6 Storage/Database | Core |
| `/milestone-timeline` | A7 Timeline/Event Correlation | Core |
| `/milestone-custody-blockchain` | A8 Chain of Custody + Ganache anchor | Core |
| `/milestone-reporting` | A9 PDF Reporting + BSA §63 certificate | Core |
| `/milestone-ui` | A10 HTML/CSS/JS frontend | Core |
| `/milestone-test-data` | A12 Synthetic + real sample acquisition | Core |

**A11 (AI Analytics — YOLO object/face detection) has no milestone file.** It is explicitly the lowest-priority, first-to-cut item in the source plan. Do not build it unless the user explicitly asks after all core milestones are done and verified.

## Forbidden / Never Do
- Never touch a live physical DVR/NVR during a demo — ingestion is always from a pre-made disk image or file.
- Never re-encode video (always remux with `-c copy`); re-encoding is treated as evidence alteration.
- Never store raw video bytes in SQLite — DB stores paths, hashes, and metadata only.
- Never use Streamlit, React, or FastAPI in this build.
- Never use WeasyPrint or `pytsk3`.
- Never accept a carved Tier 2 frame on header match alone — header AND footer AND checksum are all required.
- Never render a timeline event without a visible `precision` marker (`exact` vs `approximate`, with `±Ns` confidence window).
- Never leave real, identifiable footage obtained during sample acquisition (see B6) in any recorded/shared demo — delete real video content after testing, keep only logs/results.
- Never deploy a Solidity custody contract as part of the core build (optional, explicitly out of scope unless requested).
- Never fabricate or paraphrase the BSA Section 63(4)(c) certificate text — it must be checked against indiacode.nic.in directly before being hardcoded into the report template.
- Never claim native Tier-1-grade support for a vendor we haven't parsed against the verified spec.

## Reference Spec (authoritative for all byte-layout work)
"Automated Forensic Recovery Methodology for Video Evidence from Hikvision and Dahua DVR/NVR Systems" (Rzayeva et al., *Information* journal, MDPI, 13 Nov 2025), validated against 27 real drives. This is the source of truth for Hikvision/Dahua byte offsets and the dual-signature (header+footer+checksum) validation approach (~2.4% FP rate vs. ~12.7% header-only). Any header/footer offset in code must match this spec exactly — if a milestone's data doesn't match, stop and flag it rather than guessing.

## Known, Disclosed Limitations (state these proactively in reports/UI, they are a strength not a gap)
- Tier 1 validated for 2 OEMs against the peer-reviewed spec + limited real samples; Tier 2 covers standard H.264/H.265 only.
- A real sample from one firmware/model validates that combination, not the vendor's entire product line.
- Encrypted/DRM exports, multi-TB scale, and multi-disk RAID are out of scope.
- Not an independently validated forensic tool (e.g. NIST CFTT-style) — demonstrates a standardized, hash-verified workflow.

## Validation-Confidence Tagging (must appear per file, everywhere it's shown)
Every evidence file carries exactly one of: `Validated: Real Device` / `Validated: Synthetic Reference Data` / `Stub: Awaiting Hardware`.

## Team
6-person team, "Void main." Roles are not rigidly fixed; default division for agent orchestration purposes: pipeline/parsing, database/custody, reporting/legal, frontend, test-data/sample-acquisition, integration/QA. One task per agent thread — no scope creep across milestones.

## Directory Layout
```
/evidence_store/case_<id>/
  raw_images/    ← original forensic disk image, hashed, never modified
  extracted/     ← Tier 1 vendor-parsed video
  recovered/     ← Tier 2 carved video
  reports/       ← generated PDF reports + legal certificates
```
