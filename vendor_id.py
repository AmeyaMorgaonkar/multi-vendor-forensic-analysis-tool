"""
Root module bridge re-exporting detect_vendor from src.pipeline.vendor_id.
"""
from src.pipeline.vendor_id import detect_vendor, HIKVISION_SIGNATURE, DAHUA_SIGNATURE

__all__ = ["detect_vendor", "HIKVISION_SIGNATURE", "DAHUA_SIGNATURE"]
