import os
from pathlib import Path
from typing import Optional, Union

# Signature byte constants based on vendor specifications
# Citation: Rzayeva et al., MDPI Information, 13 Nov 2025
HIKVISION_SIGNATURE: bytes = b"HIKVISION@HANGZHOU"
DAHUA_SIGNATURE: bytes = b"DHFS4.1"

# Frame magic bytes
HIKVISION_FRAME_MAGIC: bytes = b"IVKH"  # 0x484B5649 in Little-Endian
DAHUA_FRAME_MAGIC: bytes = b"DHAV"

# Standard offsets where vendor header signatures are embedded
OFFSETS_TO_CHECK: tuple[int, ...] = (0, 512, 1024, 2048)
READ_BUFFER_SIZE: int = 4096


def detect_vendor(
    file_path: Union[str, Path], vendor_override: Optional[str] = None
) -> str:
    """
    Detects the DVR/NVR vendor for a given evidence file by scanning container signatures
    and frame-level magics.

    :param file_path: Path to the evidence file.
    :param vendor_override: Optional manual vendor selection ('hikvision', 'dahua', etc.).
    :return: Vendor string ('hikvision', 'dahua', or 'unknown').
    """
    if vendor_override and vendor_override.strip():
        override_clean = vendor_override.strip().lower()
        if override_clean in ("hikvision", "dahua"):
            return override_clean

    path = Path(file_path)
    if not path.exists() or not path.is_file():
        return "unknown"

    file_size = path.stat().st_size
    if file_size == 0:
        return "unknown"

    try:
        with open(path, "rb") as f:
            header_bytes = f.read(READ_BUFFER_SIZE)
    except OSError:
        return "unknown"

    if len(header_bytes) < 4:
        return "unknown"

    # 1. Check direct frame magic at offset 0 (typical for raw frame streams)
    if header_bytes.startswith(HIKVISION_FRAME_MAGIC):
        return "hikvision"
    if header_bytes.startswith(DAHUA_FRAME_MAGIC):
        return "dahua"

    # 2. Container signature check at exact predefined offsets
    for offset in OFFSETS_TO_CHECK:
        if offset + len(HIKVISION_SIGNATURE) <= len(header_bytes):
            if (
                header_bytes[offset : offset + len(HIKVISION_SIGNATURE)]
                == HIKVISION_SIGNATURE
            ):
                return "hikvision"

        if offset + len(DAHUA_SIGNATURE) <= len(header_bytes):
            if (
                header_bytes[offset : offset + len(DAHUA_SIGNATURE)]
                == DAHUA_SIGNATURE
            ):
                return "dahua"

    # 3. General substring fallback within first 4KB header block
    if HIKVISION_SIGNATURE in header_bytes:
        return "hikvision"
    if DAHUA_SIGNATURE in header_bytes:
        return "dahua"

    return "unknown"
