from pathlib import Path
import pytest

from src.tier1.hikvision import parse_hikvision_frame, parse_hikvision_file
from tests.fixtures.generate_fixtures import FIXTURES_DIR, generate_hikvision_fixture


@pytest.fixture(scope="module")
def hikvision_sample_path(tmp_path_factory) -> Path:
    """Fixture providing clean synthetic Hikvision file."""
    tmp_dir = tmp_path_factory.mktemp("hik_test")
    sample_file = tmp_dir / "test_hik.dav"
    generate_hikvision_fixture(sample_file, num_frames=5)
    return sample_file


def test_parse_hikvision_frame_valid(hikvision_sample_path: Path):
    """Verify correct extraction of Hikvision frame header fields."""
    with open(hikvision_sample_path, "rb") as f:
        data = f.read()

    # Find first frame magic
    offset = data.find(b"IVKH")
    assert offset != -1

    frame = parse_hikvision_frame(data, offset)
    assert frame.vendor == "hikvision"
    assert frame.offset == offset
    assert frame.frame_size > 20
    assert frame.channel == 1
    assert frame.timestamp > 0
    assert frame.payload_size == frame.frame_size - (frame.payload_offset - frame.offset)


def test_parse_hikvision_frame_invalid_magic():
    """Verify invalid magic raises ValueError."""
    bad_buf = b"\x00\x00\x00\x00" + b"\x00" * 30
    with pytest.raises(ValueError, match="Invalid Hikvision magic"):
        parse_hikvision_frame(bad_buf, 0)


def test_parse_hikvision_file_walker(hikvision_sample_path: Path):
    """Verify parse_hikvision_file extracts all frames from file."""
    frames = parse_hikvision_file(hikvision_sample_path)
    assert len(frames) >= 5
    for f in frames:
        assert f.vendor == "hikvision"
        assert f.channel == 1


def test_parse_hikvision_user_sample_file():
    """Verify parse_hikvision_file on user root sample file if present."""
    root_sample = Path("sample_hikvision_clean.hik")
    if not root_sample.exists():
        root_sample = Path("sample_data/sample_hikvision_clean.hik")

    if root_sample.exists():
        frames = parse_hikvision_file(root_sample)
        assert len(frames) > 0
        for f in frames:
            assert f.vendor == "hikvision"
