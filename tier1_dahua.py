"""
Root module bridge for Dahua Tier 1 parser.
Exposes extract_metadata and extract_video for test_tier1.py.
"""
from typing import Any, Dict
from src.tier1.dahua import parse_dahua_file


def extract_metadata(file_path: str) -> Dict[str, Any]:
    frames = parse_dahua_file(file_path)
    if not frames:
        return {"channel": 0, "frame_count": 0, "footer_validated_frame_count": 0}
    footer_valid_count = sum(1 for f in frames if f.checksum_valid is not False)
    return {
        "channel": frames[0].channel if frames else 1,
        "frame_count": len(frames),
        "footer_validated_frame_count": footer_valid_count,
    }


def extract_video(file_path: str) -> bytes:
    frames = parse_dahua_file(file_path)
    if not frames:
        return b""
    with open(file_path, "rb") as f:
        data = f.read()
    video_bytes = bytearray()
    for frame in frames:
        video_bytes += data[
            frame.payload_offset : frame.payload_offset + frame.payload_size
        ]
    return bytes(video_bytes)
