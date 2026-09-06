import struct
from pathlib import Path
from typing import List, Optional, Union

from src.tier1 import FrameHeader

# Offset provenance: Rzayeva et al., MDPI Information, 13 Nov 2025
DAHUA_HEADER_MAGIC: bytes = b"DHAV"
DAHUA_FOOTER_MAGIC: bytes = b"dhav"


def parse_dahua_frame(buf: bytes, offset: int = 0) -> FrameHeader:
    """
    Parses a single Dahua DHFS4.1 frame with MANDATORY DUAL-SIGNATURE VALIDATION
    (verifying both 'DHAV' header magic and 'dhav' footer magic).
    Citation: Rzayeva et al., MDPI Information, 13 Nov 2025.

    :param buf: Bytes buffer containing the video stream.
    :param offset: Start byte offset of the frame.
    :return: Extracted FrameHeader object.
    :raises ValueError: If buffer is too small, header magic mismatches, or footer magic mismatches.
    """
    if len(buf) - offset < 32:
        raise ValueError(
            f"Buffer too short for Dahua frame header at offset {offset} (len={len(buf)})"
        )

    # 1. Validate DHAV Header Magic
    header_magic = buf[offset : offset + 4]
    if header_magic != DAHUA_HEADER_MAGIC:
        raise ValueError(
            f"Invalid Dahua header magic {header_magic} at offset {offset} (expected b'DHAV')"
        )

    frame_type = buf[offset + 4]
    subtype = buf[offset + 5]
    channel = buf[offset + 6]
    subchannel = buf[offset + 7]
    frame_number = struct.unpack("<I", buf[offset + 8 : offset + 12])[0]
    hdr_size_field = struct.unpack("<I", buf[offset + 12 : offset + 16])[0]
    timestamp = struct.unpack("<I", buf[offset + 16 : offset + 20])[0]
    timestamp_ms = struct.unpack("<H", buf[offset + 20 : offset + 22])[0]

    header_checksum = 0
    if len(buf) - offset >= 27:
        header_checksum = struct.unpack("<I", buf[offset + 23 : offset + 27])[0]

    header_size = 32

    # 2. MANDATORY DUAL-SIGNATURE VALIDATION: Check 'dhav' Footer Magic
    # Determine whether hdr_size_field is header+payload or total frame length including footer
    footer_offset = -1
    footer_size = 12

    # Case A: hdr_size_field is header + payload size (footer is at offset + hdr_size_field)
    if (
        offset + hdr_size_field + 4 <= len(buf)
        and buf[offset + hdr_size_field : offset + hdr_size_field + 4] == DAHUA_FOOTER_MAGIC
    ):
        footer_offset = offset + hdr_size_field
        footer_size = 12 if (offset + hdr_size_field + 12 <= len(buf)) else 8
        total_frame_size = hdr_size_field + footer_size
    # Case B: hdr_size_field includes footer length
    elif (
        offset + hdr_size_field - 12 >= offset + header_size
        and offset + hdr_size_field <= len(buf)
        and buf[offset + hdr_size_field - 12 : offset + hdr_size_field - 8] == DAHUA_FOOTER_MAGIC
    ):
        footer_offset = offset + hdr_size_field - 12
        footer_size = 12
        total_frame_size = hdr_size_field
    elif (
        offset + hdr_size_field - 8 >= offset + header_size
        and offset + hdr_size_field <= len(buf)
        and buf[offset + hdr_size_field - 8 : offset + hdr_size_field - 4] == DAHUA_FOOTER_MAGIC
    ):
        footer_offset = offset + hdr_size_field - 8
        footer_size = 8
        total_frame_size = hdr_size_field
    else:
        # DUAL-SIGNATURE REJECTION: Header match alone is NOT enough!
        raise ValueError(
            f"Dual-signature validation failed for Dahua frame at offset {offset}: "
            f"Header magic 'DHAV' present but 'dhav' footer magic missing/mismatched."
        )

    payload_offset = offset + header_size
    payload_size = max(0, footer_offset - payload_offset)

    # Validate checksum if header_checksum is provided
    checksum_valid = None
    if header_checksum != 0 and payload_size > 0:
        payload_bytes = buf[payload_offset : payload_offset + payload_size]
        computed_cs = sum(payload_bytes) & 0xFFFFFFFF
        checksum_valid = computed_cs == header_checksum

    is_keyframe = subtype in (0, 5)

    return FrameHeader(
        vendor="dahua",
        offset=offset,
        frame_type=frame_type,
        frame_size=total_frame_size,
        timestamp=timestamp,
        timestamp_ms=timestamp_ms,
        channel=channel,
        subchannel=subchannel,
        frame_number=frame_number,
        payload_offset=payload_offset,
        payload_size=payload_size,
        is_keyframe=is_keyframe,
        checksum_valid=checksum_valid,
    )


def parse_dahua_file(file_path: Union[str, Path]) -> List[FrameHeader]:
    """
    Walks a Dahua video container file frame-by-frame, extracting all valid dual-signature frames.

    :param file_path: Path to Dahua video file (.dav).
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

    # Check container label at offset 0 (skip 512 byte container header if present)
    if data.startswith(b"DHFS4.1"):
        offset = 512

    while offset < file_len:
        if offset + 32 > file_len:
            break

        try:
            frame = parse_dahua_frame(data, offset)
            frames.append(frame)
            step = max(1, frame.frame_size)
            offset += step
        except ValueError:
            # Dual-signature mismatch or corruption: resynchronize to next 'DHAV' header
            next_offset = data.find(DAHUA_HEADER_MAGIC, offset + 1)
            if next_offset == -1:
                break
            offset = next_offset

    return frames
