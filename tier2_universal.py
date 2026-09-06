"""
Root module bridge for Tier 2 universal carver.
Exposes carve_deleted for test_tier2.py.
"""
from typing import List
from src.tier2.carver import scan_nal_units


def carve_deleted(file_path: str) -> List[bytes]:
    frames = scan_nal_units(file_path)
    if not frames:
        return []
    with open(file_path, "rb") as f:
        data = f.read()
    fragments = []
    for frame in frames:
        frag = data[frame.offset : frame.offset + frame.size]
        fragments.append(frag)
    return fragments
