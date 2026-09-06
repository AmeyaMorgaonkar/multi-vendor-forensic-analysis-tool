from pathlib import Path
from typing import Any, Dict, Optional, Union

from src.pipeline.vendor_id import detect_vendor


def dispatch_pipeline(
    file_path: Union[str, Path], case_id: str, vendor_override: Optional[str] = None
) -> Dict[str, Any]:
    """
    Dispatches evidence file processing to either Tier 1 (deep container parsing)
    or Tier 2 (universal H.264/H.265 NAL unit carving) based on signature vendor identification.

    :param file_path: Path to evidence video file.
    :param case_id: Case identifier.
    :param vendor_override: Optional manual vendor selection.
    :return: Pipeline dispatch directive dictionary.
    """
    path = Path(file_path)
    vendor = detect_vendor(path, vendor_override=vendor_override)

    if vendor in ("hikvision", "dahua"):
        recovery_tier = "tier1"
        target_parser = f"src.tier1.{vendor}"
    else:
        # Unknown vendor fallback strictly routes to Tier 2 carving
        recovery_tier = "tier2"
        target_parser = "src.tier2.carver"

    return {
        "case_id": case_id,
        "file_path": str(path),
        "vendor": vendor,
        "recovery_tier": recovery_tier,
        "target_parser": target_parser,
        "status": "dispatched",
    }
