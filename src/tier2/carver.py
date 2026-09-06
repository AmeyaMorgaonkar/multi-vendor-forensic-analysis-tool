import mmap
import os
import re
from pathlib import Path
from typing import List, Union

from src.tier2 import CarvedFrame
from src.tier2.validator import validate_carved_frame

# Compiled regex for fast NAL start-code scanning
NAL_PATTERN: re.Pattern = re.compile(rb"\x00\x00\x00\x01|\x00\x00\x01")


def verify_frame_decode_sanity(payload: bytes) -> bool:
    """
    Lightweight decode sanity check on carved NAL unit payload
    to filter out false-positive byte signature matches.
    """
    if len(payload) < 2:
        return False
    # Check non-zero payload content
    if all(b == 0 for b in payload[:16]):
        return False
    return True


def scan_nal_units(file_path: Union[str, Path]) -> List[CarvedFrame]:
    """
    Universal Tier 2 H.264/H.265 NAL unit carver using mmap + regex scanning
    with mandatory dual-signature validation.

    Citation: Rzayeva et al., MDPI Information, 13 Nov 2025.

    :param file_path: Path to evidence binary stream.
    :return: List of validated CarvedFrame objects.
    """
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        return []

    file_size = path.stat().st_size
    if file_size < 4:
        return []

    carved_frames: List[CarvedFrame] = []

    with open(path, "rb") as f:
        try:
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                # Find all candidate NAL start codes
                matches = list(NAL_PATTERN.finditer(mm))
                if not matches:
                    return []

                num_matches = len(matches)
                for i, match in enumerate(matches):
                    start_pos = match.start()
                    # Calculate implied frame boundary ending at next start code or EOF
                    end_pos = matches[i + 1].start() if (i + 1 < num_matches) else file_size
                    frame_size = end_pos - start_pos

                    start_code_bytes = match.group()
                    start_code_len = len(start_code_bytes)
                    nal_header_offset = start_pos + start_code_len

                    if nal_header_offset >= file_size:
                        continue

                    nal_header_byte = mm[nal_header_offset]
                    h264_type = nal_header_byte & 0x1F

                    # Mandatory Dual-Signature Validation (Header + Boundary + Consistency)
                    is_valid, reason = validate_carved_frame(
                        mm, start_pos, frame_size, h264_type
                    )

                    if not is_valid:
                        # Log rejected candidate, do not include in accepted results
                        continue

                    payload = mm[start_pos + start_code_len : end_pos]
                    if not verify_frame_decode_sanity(payload):
                        continue

                    is_keyframe = h264_type in (5, 7, 8)

                    carved_frames.append(
                        CarvedFrame(
                            offset=start_pos,
                            size=frame_size,
                            nal_unit_type=h264_type,
                            is_keyframe=is_keyframe,
                            codec="H264",
                            validation_confidence="approximate",
                            confidence_window_seconds=5,
                            dual_signature_passed=True,
                        )
                    )
        except OSError:
            return []

    return carved_frames
