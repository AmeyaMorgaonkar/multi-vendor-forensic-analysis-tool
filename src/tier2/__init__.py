from dataclasses import dataclass
from typing import Optional


@dataclass
class CarvedFrame:
    """
    Extracted metadata for a single Tier 2 carved H.264/H.265 video frame.
    Citation provenance: Rzayeva et al., MDPI Information, 13 Nov 2025.
    """

    offset: int  # Start byte offset of NAL unit / frame
    size: int  # Byte length of carved frame
    nal_unit_type: int  # NAL unit header type ID
    is_keyframe: bool  # True for IDR/I-frame keyframe
    codec: str = "H264"  # Codec identifier ('H264' or 'H265')
    validation_confidence: str = "approximate"  # Tier 2 frames have approximate timestamps
    confidence_window_seconds: int = 5  # Confidence window in seconds (±5s)
    dual_signature_passed: bool = True  # True if header AND boundary/footer AND consistency passed
    rejection_reason: Optional[str] = None  # Rejection diagnostic string if failed


__all__ = ["CarvedFrame"]
