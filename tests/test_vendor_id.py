from pathlib import Path
import pytest

from src.pipeline.vendor_id import (
    detect_vendor,
    HIKVISION_SIGNATURE,
    DAHUA_SIGNATURE,
)
from src.pipeline.dispatch import dispatch_pipeline
from tests.fixtures.generate_fixtures import (
    FIXTURES_DIR,
    generate_hikvision_fixture,
    generate_dahua_fixture,
    generate_unknown_vendor_fixture,
)


@pytest.fixture(scope="module")
def fixtures_dir():
    """Ensure test fixtures exist before running vendor ID tests."""
    hik_path = FIXTURES_DIR / "hikvision_clean.dav"
    dahua_path = FIXTURES_DIR / "dahua_clean.dav"
    unknown_path = FIXTURES_DIR / "unknown_vendor_raw.h264"

    if not hik_path.exists():
        generate_hikvision_fixture(hik_path)
    if not dahua_path.exists():
        generate_dahua_fixture(dahua_path)
    if not unknown_path.exists():
        generate_unknown_vendor_fixture(unknown_path)

    return FIXTURES_DIR


def test_detect_hikvision_from_fixture(fixtures_dir: Path):
    """Test Hikvision detection on clean synthetic fixture."""
    hik_path = fixtures_dir / "hikvision_clean.dav"
    vendor = detect_vendor(hik_path)
    assert vendor == "hikvision"


def test_detect_dahua_from_fixture(fixtures_dir: Path):
    """Test Dahua detection on clean synthetic fixture."""
    dahua_path = fixtures_dir / "dahua_clean.dav"
    vendor = detect_vendor(dahua_path)
    assert vendor == "dahua"


def test_detect_unknown_vendor_from_fixture(fixtures_dir: Path):
    """Test unknown vendor fallback on raw H.264 stream."""
    unknown_path = fixtures_dir / "unknown_vendor_raw.h264"
    vendor = detect_vendor(unknown_path)
    assert vendor == "unknown"


def test_detect_vendor_at_specific_offsets(tmp_path: Path):
    """Test signature detection explicitly at offsets 0, 512, 1024, and 2048."""
    offsets = [0, 512, 1024, 2048]

    # Test Hikvision at each offset
    for off in offsets:
        file_path = tmp_path / f"hik_off_{off}.bin"
        with open(file_path, "wb") as f:
            f.write(b"\x00" * off)
            f.write(HIKVISION_SIGNATURE)
            f.write(b"\x00" * 100)
        assert detect_vendor(file_path) == "hikvision"

    # Test Dahua at each offset
    for off in offsets:
        file_path = tmp_path / f"dahua_off_{off}.bin"
        with open(file_path, "wb") as f:
            f.write(b"\x00" * off)
            f.write(DAHUA_SIGNATURE)
            f.write(b"\x00" * 100)
        assert detect_vendor(file_path) == "dahua"


def test_detect_vendor_empty_and_short_files(tmp_path: Path):
    """Test empty, small (< 512 bytes), and non-existent files return 'unknown' gracefully without crashing."""
    # Non-existent file
    assert detect_vendor(tmp_path / "non_existent.dav") == "unknown"

    # Empty file
    empty_path = tmp_path / "empty.dav"
    empty_path.write_bytes(b"")
    assert detect_vendor(empty_path) == "unknown"

    # Small random file
    small_path = tmp_path / "small.dav"
    small_path.write_bytes(b"\x01\x02\x03\x04" * 10)
    assert detect_vendor(small_path) == "unknown"


def test_detect_vendor_override(fixtures_dir: Path):
    """Test manual vendor override precedence."""
    unknown_path = fixtures_dir / "unknown_vendor_raw.h264"
    assert (
        detect_vendor(unknown_path, vendor_override="hikvision") == "hikvision"
    )
    assert detect_vendor(unknown_path, vendor_override="dahua") == "dahua"


def test_dispatch_pipeline_routing(fixtures_dir: Path):
    """Test pipeline dispatcher routes to Tier 1 for known vendors and Tier 2 for unknown vendors."""
    hik_path = fixtures_dir / "hikvision_clean.dav"
    dahua_path = fixtures_dir / "dahua_clean.dav"
    unknown_path = fixtures_dir / "unknown_vendor_raw.h264"

    res_hik = dispatch_pipeline(hik_path, case_id="case_001")
    assert res_hik["vendor"] == "hikvision"
    assert res_hik["recovery_tier"] == "tier1"
    assert res_hik["target_parser"] == "src.tier1.hikvision"

    res_dahua = dispatch_pipeline(dahua_path, case_id="case_001")
    assert res_dahua["vendor"] == "dahua"
    assert res_dahua["recovery_tier"] == "tier1"
    assert res_dahua["target_parser"] == "src.tier1.dahua"

    res_unknown = dispatch_pipeline(unknown_path, case_id="case_001")
    assert res_unknown["vendor"] == "unknown"
    assert res_unknown["recovery_tier"] == "tier2"
    assert res_unknown["target_parser"] == "src.tier2.carver"
