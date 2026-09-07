"""
Root module bridge for Hikvision Tier 1 parser.
Exposes extract_metadata and extract_video for test_tier1.py.
"""
from typing import Any, Dict
from src.tier1.hikvision import parse_hikvision_file


def extract_metadata(file_path: str) -> Dict[str, Any]:
    frames, _ = parse_hikvision_file(file_path)
    if not frames:
        return {"channel": 0, "frame_count": 0}
    return {
        "channel": frames[0].channel if frames else 1,
        "frame_count": len(frames),
    }


def extract_video(file_path: str) -> bytes:
    frames, _ = parse_hikvision_file(file_path)
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
