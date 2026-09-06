from typing import Optional, Tuple

# Citation: Rzayeva et al., MDPI Information, 13 Nov 2025
# Dual-signature carving target FP benchmark: ~2.4% vs ~12.7% header-only baseline.
VALID_H264_NAL_TYPES: set[int] = {1, 5, 7, 8, 6, 9}  # Slice, IDR, SPS, PPS, SEI, AUD
VALID_H265_NAL_TYPES: set[int] = {1, 19, 20, 32, 33, 34}  # Trail, IDR, CRA, VPS, SPS, PPS


def header_only_baseline_validator(buf: bytes, offset: int) -> bool:
    """
    Header-only baseline validator (for comparison/benchmarking tests).
    Checks only for NAL start code presence, ignoring boundary and consistency gates.
    Yields ~12.7% false-positive rate on random noise data.
    """
    if len(buf) - offset < 4:
        return False
    start_3 = buf[offset : offset + 3] == b"\x00\x00\x01"
    start_4 = buf[offset : offset + 4] == b"\x00\x00\x00\x01"
    return start_3 or start_4


def validate_carved_frame(
    buf: bytes, offset: int, frame_size: int, nal_type: int
) -> Tuple[bool, Optional[str]]:
    """
    Mandatory Dual-Signature & Consistency Validator for Tier 2 Carved Frames.
    Enforces 3 forensic validation gates:
      Gate 1: Header signature (NAL start code)
      Gate 2: Boundary/Footer signature (valid boundary at offset + frame_size)
      Gate 3: Codec payload consistency check (forbidden zero bit + NAL type)

    Target false-positive rate ~2.4% per Rzayeva et al., MDPI Information, 2025.

    :param buf: Buffer containing mapped stream data.
    :param offset: Start byte offset of candidate frame.
    :param frame_size: Calculated frame size up to next boundary.
    :param nal_type: Extracted NAL unit type byte.
    :return: Tuple (is_valid: bool, rejection_reason: Optional[str]).
    """
    file_len = len(buf)
    if offset >= file_len or frame_size <= 0:
        return False, "Invalid offset or frame_size"

    # --- GATE 1: Header Signature Check ---
    start_code_len = 0
    if offset + 4 <= file_len and buf[offset : offset + 4] == b"\x00\x00\x00\x01":
        start_code_len = 4
    elif offset + 3 <= file_len and buf[offset : offset + 3] == b"\x00\x00\x01":
        start_code_len = 3
    else:
        return False, "Gate 1 Failed: NAL start code signature missing"

    nal_header_offset = offset + start_code_len
    if nal_header_offset >= file_len:
        return False, "Gate 1 Failed: Buffer ends immediately after start code"

    # --- GATE 3: Codec Payload Consistency Check ---
    nal_header_byte = buf[nal_header_offset]
    forbidden_zero_bit = (nal_header_byte & 0x80) >> 7
    if forbidden_zero_bit != 0:
        return False, f"Gate 3 Failed: Forbidden zero bit is set (0x{nal_header_byte:02X})"

    h264_type = nal_header_byte & 0x1F
    h265_type = (nal_header_byte & 0x7E) >> 1

    if h264_type not in VALID_H264_NAL_TYPES and h265_type not in VALID_H265_NAL_TYPES:
        return False, f"Gate 3 Failed: Invalid NAL type h264={h264_type}, h265={h265_type}"

    # Minimum payload byte check
    if frame_size < start_code_len + 2:
        return False, "Gate 3 Failed: Frame payload too small"

    # --- GATE 2: Boundary / Footer Signature Check ---
    end_offset = offset + frame_size

    # Boundary is valid if it lands at EOF, next NAL start code, or container magic
    if end_offset == file_len:
        # Valid boundary: EOF
        return True, None

    if end_offset + 3 <= file_len:
        next_bytes_3 = buf[end_offset : end_offset + 3]
        next_bytes_4 = buf[end_offset : end_offset + 4] if end_offset + 4 <= file_len else b""

        # Check next start code
        if next_bytes_3 == b"\x00\x00\x01" or next_bytes_4 == b"\x00\x00\x00\x01":
            return True, None

        # Check vendor container magics (DHAV, dhav, IVKH)
        if next_bytes_4 in (b"DHAV", b"dhav", b"IVKH"):
            return True, None

    # Gate 2 REJECTION: Header match alone without valid boundary is explicitly REJECTED
    return (
        False,
        f"Gate 2 Failed: Boundary signature missing at offset {end_offset} (got {buf[end_offset:end_offset+4]!r})",
    )
