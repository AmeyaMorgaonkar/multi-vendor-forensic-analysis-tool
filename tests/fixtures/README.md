# Test Fixtures Directory (`tests/fixtures/`)

This directory contains synthetic and control binary test fixtures for the forensic analysis tool pipeline.

## Fixture Generation
All binary fixtures are generated programmatically via `generate_fixtures.py`.
To (re)generate all binary fixtures:

```bash
python tests/fixtures/generate_fixtures.py
```

## Fixtures & Test Mappings

| Fixture File | Specification & Features | Primary Target Tests / Milestones |
|---|---|---|
| `hikvision_clean.dav` | `b"HIKVISION@HANGZHOU"` signature at offset 512, 10 frames with `0x484B5649` magic, channel 1, valid timestamps, and H.264 NAL payloads. | `/milestone-3-vendor-id` (Hikvision signature detection), `/milestone-4-tier1-parser` (`test_tier1_hikvision.py`) |
| `dahua_clean.dav` | `b"DHFS4.1"` container signature at offset 0, 10 frames with 32-byte `DHAV` header, payload, and 8-byte `dhav` footer. | `/milestone-3-vendor-id` (Dahua signature detection), `/milestone-4-tier1-parser` (`test_tier1_dahua.py`) |
| `unknown_vendor_raw.h264` | Raw H.264 NAL stream (`\x00\x00\x00\x01` SPS, PPS, IDR, P-frames) with **no** vendor headers/signatures. | `/milestone-3-vendor-id` (fallback to Tier 2), `/milestone-5-tier2-recovery` (`test_tier2_carver.py`) |
| `corrupted_fragmented.dav` | Mixed fixture with valid frame 1, header-only frame 2 (missing `dhav` footer), and truncated frame 3. | `/milestone-4-tier1-parser` (graceful error handling), `/milestone-5-tier2-recovery` (dual-signature footer rejection) |
| `random_control.bin` | 1,000,000 pseudo-random bytes (fixed random seed). | `/milestone-5-tier2-recovery` (benchmarking false-positive rate < 2.5%) |

*Note: Synthetic binary fixtures are git-ignored. Keep generator scripts in git, not large binaries.*
