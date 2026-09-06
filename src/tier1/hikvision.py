import struct
from pathlib import Path
from typing import List, Optional, Union

from src.tier1 import FrameHeader

# Offset provenance: Rzayeva et al., MDPI Information, 13 Nov 2025
HIKVISION_MAGIC: int = 0x484B5649  # ASCII 'HKVI', Little-Endian bytes b'IVKH'
HIKVISION_MAGIC_BYTES: bytes = b"IVKH"


def parse_hikvision_frame(buf: bytes, offset: int = 0) -> FrameHeader:
    """
    Parses a single Hikvision frame header from `buf` starting at `offset`.
    Citation: Rzayeva et al., MDPI Information, 13 Nov 2025.

    :param buf: Bytes buffer containing the video stream.
    :param offset: Start byte offset of the frame.
    :return: Extracted FrameHeader object.
    :raises ValueError: If buffer is too small or magic number does not match.
    """
    if len(buf) - offset < 20:
        raise ValueError(
            f"Buffer too short for Hikvision frame at offset {offset} (len={len(buf)})"
        )

    magic = struct.unpack("<I", buf[offset : offset + 4])[0]
    if magic != HIKVISION_MAGIC:
        raise ValueError(
            f"Invalid Hikvision magic 0x{magic:08X} at offset {offset} (expected 0x{HIKVISION_MAGIC:08X})"
        )

    frame_type = buf[offset + 4]
    raw_frame_size = struct.unpack("<I", buf[offset + 8 : offset + 12])[0]
    timestamp = struct.unpack("<I", buf[offset + 12 : offset + 16])[0]
    channel = buf[offset + 16]

    if raw_frame_size < 20 or raw_frame_size > len(buf) - offset + 24:
        raise ValueError(
            f"Invalid Hikvision frame size {raw_frame_size} at offset {offset}"
        )

    # Determine header size (20 vs 24 bytes) based on payload start code alignment
    header_size = 20
    if (
        len(buf) - offset >= 28
        and buf[offset + 24 : offset + 28] == b"\x00\x00\x00\x01"
    ):
        header_size = 24

    payload_offset = offset + header_size

    # raw_frame_size header field stores (payload_size + 24) per spec
    if raw_frame_size >= 24:
        payload_size = raw_frame_size - 24
    else:
        payload_size = max(0, raw_frame_size - header_size)

    # Total frame size on disk = header_size + payload_size
    on_disk_frame_size = header_size + payload_size

    # Frame type 1 or 5 typically represents Keyframe (I-frame/IDR)
    is_keyframe = frame_type in (1, 5)

    return FrameHeader(
        vendor="hikvision",
        offset=offset,
        frame_type=frame_type,
        frame_size=on_disk_frame_size,
        timestamp=timestamp,
        timestamp_ms=0,
        channel=channel,
        payload_offset=payload_offset,
        payload_size=payload_size,
        is_keyframe=is_keyframe,
    )


def parse_hikvision_file(file_path: Union[str, Path]) -> List[FrameHeader]:
    """
    Walks a Hikvision video container file frame-by-frame, extracting all valid frame headers.

    :param file_path: Path to Hikvision video file.
    :return: List of valid FrameHeader objects extracted chronologically.
    """
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        return []

    with open(path, "rb") as f:
        data = f.read()

    frames: List[FrameHeader] = []
    offset = 0
    file_len = len(data)

    # Skip container header block (e.g. 512 or 1024 bytes) if HIKVISION signature sits at offset 512
    if data.find(b"HIKVISION") == 512 and not data.startswith(HIKVISION_MAGIC_BYTES):
        offset = 1024

    while offset < file_len:
        if offset + 20 > file_len:
            break

        try:
            frame = parse_hikvision_frame(data, offset)
            frames.append(frame)
            step = max(1, frame.frame_size)
            offset += step
        except ValueError:
            next_offset = data.find(HIKVISION_MAGIC_BYTES, offset + 1)
            if next_offset == -1:
                break
            offset = next_offset

    return frames
