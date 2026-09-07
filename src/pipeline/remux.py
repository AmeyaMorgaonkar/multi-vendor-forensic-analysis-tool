import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# HARD MANDATORY FORENSIC RULE:
# Video streams must NEVER be re-encoded. Re-encoding alters pixel matrices
# and invalidates chain of custody. Always use '-c copy' for lossless container remuxing.
REENCODE_FORBIDDEN_FLAGS: list[str] = [
    "libx264",
    "libx265",
    "mpeg4",
    "libvpx",
    "libvpx-vp9",
    "libaom-av1",
]


def inspect_video_codec(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Uses FFprobe to inspect the video stream codec of a file.

    :param file_path: Path to video file.
    :return: Dictionary containing 'codec', 'supported', and raw probe info.
    """
    path = Path(file_path)
    if not path.exists():
        return {"codec": "unknown", "supported": False, "error": "File not found"}

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        codec = res.stdout.strip().lower() or "unknown"
        supported = codec in ("h264", "hevc", "h265")
        return {"codec": codec, "supported": supported, "error": res.stderr.strip()}
    except Exception as e:
        return {"codec": "unknown", "supported": False, "error": str(e)}


def ensure_sps_pps(
    raw_stream_path: Union[str, Path],
    sps_pps_bytes: Optional[bytes] = None,
    output_path: Optional[Union[str, Path]] = None,
) -> Path:
    """
    Ensures out-of-band SPS/PPS parameter set NAL units (0x67/0x68) are present
    in the raw stream prior to container remuxing.

    :param raw_stream_path: Source raw video stream.
    :param sps_pps_bytes: Optional out-of-band SPS/PPS parameter set bytes to prepend.
    :param output_path: Optional destination path.
    :return: Path to the prepared raw stream file with SPS/PPS.
    """
    src = Path(raw_stream_path)
    if not src.exists():
        raise FileNotFoundError(f"Raw stream file not found: {src}")

    with open(src, "rb") as f:
        data = f.read()

    # Check if SPS (0x67) is already inline in NAL start codes
    has_sps = b"\x00\x00\x00\x01\x67" in data or b"\x00\x00\x01\x67" in data

    if has_sps or not sps_pps_bytes:
        return src

    # Prepend out-of-band SPS/PPS parameter sets
    out = Path(output_path) if output_path else src.parent / f"sps_{src.name}"
    with open(out, "wb") as f:
        f.write(sps_pps_bytes)
        f.write(data)

    return out


def remux_to_mp4(
    raw_stream_path: Union[str, Path],
    output_path: Union[str, Path],
    codec_hint: str = "h264",
) -> Dict[str, Any]:
    """
    Losslessly remuxes an extracted H.264/H.265 video stream into a standardized MP4 container.
    STRICTLY ENFORCES '-c copy' (bitstream copy only, zero re-encoding).

    :param raw_stream_path: Input raw stream or container path.
    :param output_path: Output MP4 file path.
    :param codec_hint: Codec hint for fallback ('h264' or 'hevc').
    :return: Remux execution result dictionary.
    """
    raw_path = Path(raw_stream_path)
    out_path = Path(output_path)

    if not raw_path.exists():
        raise FileNotFoundError(f"Input stream for remuxing not found: {raw_path}")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Primary remux attempt using standard input auto-detection
    primary_cmd = ["ffmpeg", "-y", "-fflags", "+genpts", "-i", str(raw_path), "-c", "copy", str(out_path)]

    try:
        res = subprocess.run(primary_cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
            return {
                "success": True,
                "output_path": str(out_path),
                "command_used": primary_cmd,
                "fallback_attempted": False,
                "error": None,
            }
    except Exception as e:
        primary_err = str(e)

    # 2. Fallback attempt using forced format input flag (-f h264 / -f hevc)
    fallback_cmd = [
        "ffmpeg",
        "-y",
        "-f",
        codec_hint,
        "-i",
        str(raw_path),
        "-c",
        "copy",
        str(out_path),
    ]

    try:
        res_fb = subprocess.run(fallback_cmd, capture_output=True, text=True, check=False)
        if res_fb.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
            return {
                "success": True,
                "output_path": str(out_path),
                "command_used": fallback_cmd,
                "fallback_attempted": True,
                "error": None,
            }
        err_msg = res_fb.stderr.strip() or "FFmpeg remux returned non-zero exit code"
    except Exception as e:
        err_msg = str(e)

    return {
        "success": False,
        "output_path": str(out_path),
        "command_used": fallback_cmd,
        "fallback_attempted": True,
        "error": err_msg,
    }
