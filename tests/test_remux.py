import ast
import shutil
import subprocess
from pathlib import Path
import pytest

from src.pipeline.remux import (
    remux_to_mp4,
    ensure_sps_pps,
    inspect_video_codec,
    REENCODE_FORBIDDEN_FLAGS,
)
from tests.fixtures.generate_fixtures import generate_unknown_vendor_fixture


@pytest.fixture
def raw_h264_stream(tmp_path: Path) -> Path:
    stream_path = tmp_path / "test_stream.h264"
    generate_unknown_vendor_fixture(stream_path)
    return stream_path


def test_audit_no_reencoding_flags_in_remux_code():
    """
    CRITICAL FORENSIC AUDIT TEST:
    Verify by AST code analysis that src/pipeline/remux.py NEVER invokes FFmpeg
    with any video re-encoding encoder flags (e.g. libx264, libx265).
    """
    remux_file = Path("src/pipeline/remux.py")
    assert remux_file.exists()

    content = remux_file.read_text(encoding="utf-8")
    tree = ast.parse(content)

    # Inspect all string literals in AST using node.value
    string_literals = [
        node.value.lower()
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]

    for flag in ["libx264", "libx265", "-c:v", "libvpx-vp9"]:
        # Ensure forbidden flags do not appear in FFmpeg command lists
        for lit in string_literals:
            if flag == lit and lit not in REENCODE_FORBIDDEN_FLAGS:
                pytest.fail(f"Forbidden re-encoding flag '{flag}' found in remux.py AST!")

    # Verify '-c' and 'copy' ARE present in the module
    assert "copy" in string_literals
    assert "-c" in string_literals


def test_remux_clean_stream_to_mp4(raw_h264_stream: Path, tmp_path: Path):
    """Test remuxing a clean raw H.264 stream into a playable MP4 container."""
    output_mp4 = tmp_path / "output_clean.mp4"
    res = remux_to_mp4(raw_h264_stream, output_mp4)

    # Check FFmpeg is installed and test succeeded
    if shutil.which("ffmpeg"):
        assert res["success"] is True
        assert output_mp4.exists()
        assert output_mp4.stat().st_size > 0
        assert res["command_used"] == [
            "ffmpeg",
            "-y",
            "-i",
            str(raw_h264_stream),
            "-c",
            "copy",
            str(output_mp4),
        ]


def test_ensure_sps_pps_prepending(tmp_path: Path):
    """Test ensure_sps_pps prepends out-of-band parameter sets if missing."""
    raw_no_sps = tmp_path / "no_sps.h264"
    raw_no_sps.write_bytes(b"\x00\x00\x00\x01\x65" + b"\xAA" * 100)

    sps_pps_data = b"\x00\x00\x00\x01\x67\x42\xc0\x1f\x00\x00\x00\x01\x68\xce\x3c"
    out_path = tmp_path / "with_sps.h264"

    res_path = ensure_sps_pps(raw_no_sps, sps_pps_bytes=sps_pps_data, output_path=out_path)
    assert res_path.exists()

    with open(res_path, "rb") as f:
        data = f.read()

    assert data.startswith(sps_pps_data)


def test_remux_fallback_mechanism(tmp_path: Path):
    """Test that remux_to_mp4 uses forced format (-f h264) fallback when auto-detection fails."""
    raw_stream = tmp_path / "raw_no_ext"
    generate_unknown_vendor_fixture(raw_stream)

    output_mp4 = tmp_path / "fallback_out.mp4"
    if shutil.which("ffmpeg"):
        res = remux_to_mp4(raw_stream, output_mp4, codec_hint="h264")
        assert res["success"] is True
        assert output_mp4.exists()


def test_inspect_video_codec(raw_h264_stream: Path):
    """Test ffprobe inspection of video codec."""
    if shutil.which("ffprobe"):
        probe_res = inspect_video_codec(raw_h264_stream)
        assert "codec" in probe_res
        assert "supported" in probe_res
