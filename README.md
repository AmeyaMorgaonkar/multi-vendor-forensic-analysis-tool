# Multi-Vendor DVR/NVR Forensic Analysis Tool

SIH 2026 · PS ID 26150 · Team Void main (6A6870)

See `PROJECT_CONSTITUTION.md` for full scope, stack, and forbidden patterns. This repo is driven by Google Antigravity — everything below is a slash command typed into the agent, not a script you run manually.

## Setup
1. Install Python 3.11+, FFmpeg (on PATH), and Ganache (CLI or desktop) for the blockchain milestone.
2. `pip install -r requirements.txt` (created by `/init`).
3. Run `/init` first if `PROJECT_CONSTITUTION.md` and folder scaffold aren't present yet (they're pre-filled in this package — `/init` will just confirm and scaffold folders/`.gitignore`/`requirements.txt`).

## Workflows
| Command | Purpose |
|---|---|
| `/init` | Bootstrap folders, `.gitignore`, `requirements.txt`, initial commit |
| `/plan` | PRD + implementation plan before any new feature |
| `/build` | Implement the current approved plan, incrementally |
| `/review` | Structured review of a diff against project rules |
| `/test` | Generate/run tests, report coverage |
| `/security` | Security audit before deploy |
| `/deploy` | Final checks + deploy (local demo packaging, in this project's case) |
| `/hotfix` | Fast, minimal-scope production fix |
| `/docs` | Update README/docstrings/CHANGELOG after a change |
| `/retrospective` | Capture learnings, generate instinct files |
| `/milestone-vendor-id` | Build A1 signature-based vendor detection |
| `/milestone-tier1-parser` | Build A2 Dahua + Hikvision deep parsers |
| `/milestone-tier2-recovery` | Build A3 universal H.264/H.265 carving |
| `/milestone-acquisition-hashing` | Build A4 ingestion + MD5/SHA-256 hashing |
| `/milestone-remux` | Build A5 lossless FFmpeg remux pipeline |
| `/milestone-database` | Build A6 SQLite schema + WAL |
| `/milestone-timeline` | Build A7 unified precision-tagged timeline |
| `/milestone-custody-blockchain` | Build A8 hash-chain + Ganache anchoring |
| `/milestone-reporting` | Build A9 ReportLab PDF + BSA §63 certificate |
| `/milestone-ui` | Build A10 plain HTML/CSS/JS frontend |
| `/milestone-test-data` | Build A12 synthetic Dahua/Hikvision files + corrupted sample + real-sample pull attempt |

**Not built by design:** A11 (AI analytics / YOLO / face detection) — lowest priority, explicitly first-to-cut. Ask for it only after every milestone above is done and green.

## Suggested build order
`/init` → `/milestone-database` → `/milestone-test-data` → `/milestone-vendor-id` → `/milestone-tier1-parser` → `/milestone-tier2-recovery` → `/milestone-acquisition-hashing` → `/milestone-remux` → `/milestone-timeline` → `/milestone-custody-blockchain` → `/milestone-reporting` → `/milestone-ui` → `/test` → `/security` → `/deploy`

(Database and test-data come early because every other milestone either writes to the DB or needs sample files to run against.)
