from pathlib import Path
import pytest

from src.tier2.carver import scan_nal_units
from src.tier2.validator import validate_carved_frame, header_only_baseline_validator
from tests.fixtures.generate_fixtures import (
    FIXTURES_DIR,
    generate_unknown_vendor_fixture,
    generate_random_control_data,
    generate_corrupted_fixture,
)


@pytest.fixture(scope="module")
def unknown_vendor_sample(tmp_path_factory) -> Path:
    """Fixture providing raw H.264 stream without vendor wrappers."""
    tmp_dir = tmp_path_factory.mktemp("tier2_test")
    sample_file = tmp_dir / "unknown.h264"
    generate_unknown_vendor_fixture(sample_file)
    return sample_file


@pytest.fixture(scope="module")
def random_control_sample(tmp_path_factory) -> Path:
    """Fixture providing random noise control binary."""
    tmp_dir = tmp_path_factory.mktemp("tier2_test")
    sample_file = tmp_dir / "random.bin"
    generate_random_control_data(sample_file, size_bytes=200_000)
    return sample_file


def test_scan_unknown_vendor_raw_h264(unknown_vendor_sample: Path):
    """Test carving valid H.264 NAL units from an unknown vendor file."""
    frames = scan_nal_units(unknown_vendor_sample)
    assert len(frames) > 0
    for frame in frames:
        assert frame.dual_signature_passed is True
        assert frame.validation_confidence == "approximate"
        assert frame.codec == "H264"


def test_dual_signature_vs_header_only_false_positive_benchmark():
    """
    CRITICAL FORENSIC INTEGRITY TEST:
    Compare Dual-Signature validation vs Header-Only baseline validation on candidate streams.
    Assert that Dual-Signature validation rejects false-positive header matches where boundaries/footers fail.
    """
    # Stream with valid NAL headers but corrupted boundaries (noise at end offsets)
    fake_stream = (
        b"\x00\x00\x00\x01\x67" + b"\x11" * 60 + b"\xFF\xFF\xFF\xFF" +
        b"\x00\x00\x00\x01\x68" + b"\x22" * 60 + b"\xEE\xEE\xEE\xEE" +
        b"\x00\x00\x00\x01\x65" + b"\x33" * 60 + b"\xDD\xDD\xDD\xDD"
    )

    header_only_matches = 0
    dual_signature_matches = 0

    chunk_size = 69
    for idx in range(3):
        offset = idx * chunk_size
        if header_only_baseline_validator(fake_stream, offset):
            header_only_matches += 1

        h264_type = fake_stream[offset + 4] & 0x1F
        is_valid, _ = validate_carved_frame(fake_stream, offset, 65, h264_type)
        if is_valid:
            dual_signature_matches += 1

    # Header-only baseline accepts all 3 header candidates
    assert header_only_matches == 3
    # Dual-signature validator rejects candidates whose boundary signatures fail
    assert dual_signature_matches < header_only_matches
    assert dual_signature_matches == 0


def test_header_only_match_rejected_if_boundary_corrupted():
    """
    Verify that a NAL start code header match with a corrupted boundary is REJECTED by Gate 2.
    """
    fake_frame = b"\x00\x00\x00\x01\x67" + b"\xFF" * 100
    is_valid, reason = validate_carved_frame(fake_frame, 0, 50, 7)

    assert is_valid is False
    assert reason is not None
    assert "Gate 2 Failed" in reason or "Gate 3 Failed" in reason


def test_carver_corrupted_fixture(tmp_path: Path):
    """Verify scan_nal_units does not crash on corrupted streams."""
    corrupt_path = tmp_path / "corrupt.dav"
    generate_corrupted_fixture(corrupt_path)

    frames = scan_nal_units(corrupt_path)
    assert len(frames) >= 0


def test_carver_user_sample_files():
    """Verify carver on user sample files in sample_data/ or root."""
    user_unknown = Path("sample_unknown_vendor.bin")
    if not user_unknown.exists():
        user_unknown = Path("sample_data/sample_unknown_vendor.bin")

    if user_unknown.exists():
        frames = scan_nal_units(user_unknown)
        assert len(frames) > 0
        for f in frames:
            assert f.dual_signature_passed is True
