from dataclasses import dataclass
from typing import Optional


@dataclass
class FrameHeader:
    """
    Extracted forensic metadata for a single DVR/NVR container frame.
    Citation provenance: Rzayeva et al., MDPI Information, 13 Nov 2025.
    """

    vendor: str  # 'hikvision' or 'dahua'
    offset: int  # Start byte offset of frame in stream
    frame_type: int  # Raw frame type identifier
    frame_size: int  # Total byte length of frame (header + payload + footer)
    timestamp: int  # Epoch timestamp (seconds)
    timestamp_ms: int = 0  # Milliseconds offset (0-999)
    channel: int = 1  # DVR camera channel ID
    subchannel: int = 0  # Sub-stream channel ID
    frame_number: Optional[int] = None  # Sequential frame number
    payload_offset: int = 0  # Byte offset where video payload begins
    payload_size: int = 0  # Byte length of video payload
    is_keyframe: bool = False  # True for I-frame/IDR keyframe
    checksum_valid: Optional[bool] = None  # Checksum validation result


__all__ = ["FrameHeader"]
