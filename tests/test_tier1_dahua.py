import struct
from pathlib import Path
import pytest

from src.tier1.dahua import parse_dahua_frame, parse_dahua_file
from tests.fixtures.generate_fixtures import (
    generate_dahua_fixture,
    generate_corrupted_fixture,
)


@pytest.fixture(scope="module")
def dahua_sample_path(tmp_path_factory) -> Path:
    """Fixture providing clean synthetic Dahua file."""
    tmp_dir = tmp_path_factory.mktemp("dahua_test")
    sample_file = tmp_dir / "test_dahua.dav"
    generate_dahua_fixture(sample_file, num_frames=5)
    return sample_file


def test_parse_dahua_frame_valid(dahua_sample_path: Path):
    """Verify correct extraction of Dahua frame header fields with valid dual-signature."""
    with open(dahua_sample_path, "rb") as f:
        data = f.read()

    offset = data.find(b"DHAV")
    assert offset != -1

    frame = parse_dahua_frame(data, offset)
    assert frame.vendor == "dahua"
    assert frame.offset == offset
    assert frame.frame_size > 32
    assert frame.channel == 1
    assert frame.timestamp > 0


def test_dahua_dual_signature_footer_rejection():
    """
    CRITICAL FORENSIC INTEGRITY TEST:
    Verify that a Dahua frame with a valid 'DHAV' header magic but a corrupted/missing
    'dhav' footer magic is explicitly REJECTED by dual-signature validation.
    """
    # Construct a frame with DHAV header but corrupted footer 'BADF'
    payload = b"TEST_PAYLOAD_BYTES"
    header_size = 32
    footer_size = 8
    frame_size = header_size + len(payload) + footer_size

    header = struct.pack(
        "<4sBBBBIIIH10s",
        b"DHAV",
        1,  # type
        0,  # subtype
        1,  # channel
        0,  # subchannel
        1,  # frame_num
        frame_size,
        1788696000,
        0,
        b"\x00" * 10,
    )
    corrupted_footer = struct.pack("<4sI", b"BADF", frame_size)  # BAD FOOTER!
    buf = header + payload + corrupted_footer

    with pytest.raises(
        ValueError, match="Dual-signature validation failed for Dahua frame"
    ):
        parse_dahua_frame(buf, 0)


def test_parse_dahua_file_walker(dahua_sample_path: Path):
    """Verify parse_dahua_file extracts all valid dual-signature frames from file."""
    frames = parse_dahua_file(dahua_sample_path)
    assert len(frames) >= 5
    for f in frames:
        assert f.vendor == "dahua"
        assert f.channel == 1


def test_parse_dahua_corrupted_file_handling(tmp_path: Path):
    """Verify parser skips corrupted frames and recovers valid frames."""
    corrupt_path = tmp_path / "corrupt_dahua.dav"
    generate_corrupted_fixture(corrupt_path)

    frames = parse_dahua_file(corrupt_path)
    # Must recover valid frames without crashing
    assert len(frames) > 0


def test_parse_dahua_user_sample_file():
    """Verify parse_dahua_file on user root sample file if present."""
    root_sample = Path("sample_dahua_clean.dav")
    if not root_sample.exists():
        root_sample = Path("sample_data/sample_dahua_clean.dav")

    if root_sample.exists():
        frames = parse_dahua_file(root_sample)
        assert len(frames) > 0
        for f in frames:
            assert f.vendor == "dahua"
