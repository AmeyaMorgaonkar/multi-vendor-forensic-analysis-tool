import os
from pathlib import Path
import pytest

from tests.fixtures.generate_fixtures import (
    FIXTURES_DIR,
    verify_all_fixtures,
    generate_hikvision_fixture,
    generate_dahua_fixture,
    generate_unknown_vendor_fixture,
    generate_corrupted_fixture,
    generate_random_control_data,
)


def test_fixture_generation_and_verification(tmp_path: Path):
    """Test that all fixture generator functions produce valid files in a temporary directory."""
    hik_path = tmp_path / "hik.dav"
    dahua_path = tmp_path / "dahua.dav"
    unknown_path = tmp_path / "unknown.h264"
    corrupt_path = tmp_path / "corrupt.dav"
    random_path = tmp_path / "random.bin"

    generate_hikvision_fixture(hik_path, num_frames=5)
    generate_dahua_fixture(dahua_path, num_frames=5)
    generate_unknown_vendor_fixture(unknown_path)
    generate_corrupted_fixture(corrupt_path)
    generate_random_control_data(random_path, size_bytes=1000)

    assert hik_path.exists() and hik_path.stat().st_size > 512
    assert dahua_path.exists() and dahua_path.stat().st_size > 512
    assert unknown_path.exists() and unknown_path.stat().st_size > 0
    assert corrupt_path.exists() and corrupt_path.stat().st_size > 512
    assert random_path.exists() and random_path.stat().st_size > 0


def test_verify_all_fixtures_script():
    """Verify that verify_all_fixtures succeeds without assertion errors."""
    verify_all_fixtures()
    assert (FIXTURES_DIR / "hikvision_clean.dav").exists()
    assert (FIXTURES_DIR / "dahua_clean.dav").exists()
    assert (FIXTURES_DIR / "unknown_vendor_raw.h264").exists()
    assert (FIXTURES_DIR / "corrupted_fragmented.dav").exists()
    assert (FIXTURES_DIR / "random_control.bin").exists()
