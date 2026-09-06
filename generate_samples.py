"""
Synthetic DVR/NVR sample file generator.

Wraps a REAL H.264 elementary stream (generated via FFmpeg) inside synthetic
container headers matching the byte layouts documented in:
Rzayeva et al., "Automated Forensic Recovery Methodology for Video Evidence
from Hikvision and Dahua DVR/NVR Systems", Information (MDPI), Nov 2025.

This is what you use to test: vendor identification, Tier 1 parsers,
Tier 2 carving, and deleted-file recovery -- all against real, spec-accurate
byte structures, without needing physical vendor hardware.
"""
import struct
import time
import os
import random

RAW_H264 = "raw_video.h264"
OUT_DIR = "output"
os.makedirs(OUT_DIR, exist_ok=True)

with open(RAW_H264, "rb") as f:
    H264_PAYLOAD = f.read()

NAL_START = b'\x00\x00\x00\x01'


def split_into_nal_units(data: bytes):
    """Split a raw H.264 elementary stream into individual NAL units."""
    positions = [m for m in range(len(data)) if data[m:m+4] == NAL_START]
    positions.append(len(data))
    units = []
    for i in range(len(positions) - 1):
        start = positions[i]
        end = positions[i + 1]
        if end > start:
            units.append(data[start:end])
    return units


def simple_checksum(data: bytes) -> int:
    """Our OWN simplified checksum for the synthetic generator/parser pair.
    The paper doesn't publish the vendor's real checksum algorithm, so we
    define a consistent one here -- document this in your validation report
    as a simplification, not a claim of matching real vendor checksums."""
    return sum(data) & 0xFFFFFFFF


# ---------------------------------------------------------------------------
# HIKVISION FORMAT
# Offset 0:  magic 0x484B5649 (4B)      Offset 4:  frame type (1B)
# Offset 8:  frame size uint32 LE (4B)   Offset 12: timestamp uint32 LE (4B)
# Offset 16: channel id (1B)             Offset 20: payload start
# payload length = frame_size - 24
# ---------------------------------------------------------------------------
HIK_MAGIC = 0x484B5649

def build_hikvision_frame(payload: bytes, frame_type: int, channel: int, timestamp: int) -> bytes:
    frame_size = len(payload) + 24
    header = struct.pack('<I', HIK_MAGIC)          # offset 0
    header += struct.pack('<B', frame_type)          # offset 4
    header += b'\x00\x00\x00'                        # padding to offset 8
    header += struct.pack('<I', frame_size)           # offset 8
    header += struct.pack('<I', timestamp)            # offset 12
    header += struct.pack('<B', channel)               # offset 16
    header += b'\x00\x00\x00'                          # padding to offset 20
    return header + payload  # offset 20: payload


def generate_hikvision_file(path: str, corrupt: bool = False):
    nal_units = split_into_nal_units(H264_PAYLOAD)
    out = bytearray()
    base_ts = int(time.time())
    for i, nal in enumerate(nal_units):
        frame = build_hikvision_frame(nal, frame_type=1, channel=1, timestamp=base_ts + i)
        out += frame
    data = bytes(out)
    if corrupt:
        # simulate partial overwrite / fragmentation for recovery testing
        mid = len(data) // 2
        data = data[:mid] + bytes([0xFF] * 200) + data[mid + 200:]
    with open(path, 'wb') as f:
        f.write(data)
    print(f"Wrote {path} ({len(data)} bytes, {len(nal_units)} frames, corrupt={corrupt})")


# ---------------------------------------------------------------------------
# DAHUA DHFS4.1 FORMAT
# Header: "DHAV"(4B) + type(1B) + subtype(1B) + channel(1B) + subchannel(1B)
#         + frame_number uint32 LE(4B) + frame_size uint32 LE(4B)
#         + datetime uint32 LE(4B) + milliseconds uint16 LE(2B)
#         + extended flag(1B) + checksum uint32 LE(4B)   [total header = 32B]
# Payload: H.264 data, length = frame_size - 32
# Footer: "dhav"(4B) + size uint32 LE(4B) + checksum uint32 LE(4B)
# ---------------------------------------------------------------------------
DHAV_HEADER_MAGIC = b'DHAV'
DHAV_FOOTER_MAGIC = b'dhav'

def build_dahua_frame(payload: bytes, frame_number: int, channel: int, timestamp: int) -> bytes:
    frame_size = len(payload) + 32  # header overhead
    checksum = simple_checksum(payload)

    header = DHAV_HEADER_MAGIC
    header += struct.pack('<B', 1)              # type
    header += struct.pack('<B', 0)              # subtype
    header += struct.pack('<B', channel)         # channel
    header += struct.pack('<B', 0)              # subchannel
    header += struct.pack('<I', frame_number)    # frame number
    header += struct.pack('<I', frame_size)      # frame size
    header += struct.pack('<I', timestamp)       # datetime stamp
    header += struct.pack('<H', 0)              # milliseconds
    header += struct.pack('<B', 0)              # extended header flag
    header += struct.pack('<I', checksum)        # checksum
    assert len(header) == 27, f"header is {len(header)} bytes, expected 27"
    header += b'\x00' * (32 - len(header))  # pad to exactly 32 bytes total header

    footer = DHAV_FOOTER_MAGIC
    footer += struct.pack('<I', frame_size)
    footer += struct.pack('<I', checksum)

    return header + payload + footer


def generate_dahua_file(path: str, corrupt: bool = False):
    nal_units = split_into_nal_units(H264_PAYLOAD)
    out = bytearray()
    base_ts = int(time.time())
    for i, nal in enumerate(nal_units):
        frame = build_dahua_frame(nal, frame_number=i, channel=1, timestamp=base_ts + i)
        out += frame
    data = bytes(out)
    if corrupt:
        mid = len(data) // 2
        data = data[:mid] + bytes([0xAA] * 300) + data[mid + 300:]
    with open(path, 'wb') as f:
        f.write(data)
    print(f"Wrote {path} ({len(data)} bytes, {len(nal_units)} frames, corrupt={corrupt})")


# ---------------------------------------------------------------------------
# VENDOR-ID TEST HELPERS
# ---------------------------------------------------------------------------
def embed_signature_at_offsets(path_in: str, path_out: str, signature: bytes):
    """Wrap an already-built vendor file so its manufacturer string sits at
    one of the offsets your Vendor ID module checks (512/1024/2048), the way
    a real disk image would have it in a superblock/label area."""
    with open(path_in, 'rb') as f:
        payload = f.read()
    disk = bytearray(b'\x00' * 4096)  # simulate a small disk region
    disk[1024:1024 + len(signature)] = signature
    disk[4096 - len(payload) - 100 : 4096 - 100] = b'\x00' * len(payload)  # reserve space (simplified)
    full = bytes(disk) + payload
    with open(path_out, 'wb') as f:
        f.write(full)
    print(f"Wrote {path_out} ({len(full)} bytes) with signature at offset 1024")


def generate_unknown_vendor_file(path: str):
    """A file with NO recognizable vendor signature, but real H.264 content --
    this is exactly what should fall through to Tier 2 universal carving."""
    nal_units = split_into_nal_units(H264_PAYLOAD)
    # Just concatenate raw NAL units with some random junk bytes interspersed,
    # simulating an unknown/proprietary wrapper Tier 1 can't parse.
    out = bytearray()
    for nal in nal_units:
        out += bytes([random.randint(0, 255) for _ in range(16)])  # fake unknown header
        out += nal
    with open(path, 'wb') as f:
        f.write(bytes(out))
    print(f"Wrote {path} ({len(out)} bytes) -- unknown wrapper, real H.264 inside")


def generate_random_noise_file(path: str, size_bytes: int = 500_000):
    """Pure random bytes -- use this as your false-positive control test for
    Tier 2 signature carving. A correct dual-signature scanner should find
    ~zero valid frames here."""
    with open(path, 'wb') as f:
        f.write(bytes([random.randint(0, 255) for _ in range(size_bytes)]))
    print(f"Wrote {path} ({size_bytes} bytes of random noise)")


def generate_mixed_disk_image(path: str, hik_path: str, dahua_path: str):
    """Simulates a small 'disk image' containing both a Hikvision and a
    Dahua file with padding/random bytes between them, like unallocated
    space on a real drive. Good for an end-to-end demo of vendor ID +
    carving across a single blob instead of separate clean files."""
    with open(hik_path, 'rb') as f:
        hik_data = f.read()
    with open(dahua_path, 'rb') as f:
        dahua_data = f.read()

    padding1 = bytes([0x00] * 2048)
    padding2 = bytes([random.randint(0, 255) for _ in range(4096)])  # simulated "unallocated space" noise

    disk = padding1 + hik_data + padding2 + dahua_data + padding1
    with open(path, 'wb') as f:
        f.write(disk)
    print(f"Wrote {path} ({len(disk)} bytes) -- combined disk image with both vendors + noise gaps")


if __name__ == "__main__":
    # Clean files -- for vendor ID + Tier 1 parser happy-path testing
    generate_hikvision_file(f"{OUT_DIR}/sample_hikvision_clean.hik")
    generate_dahua_file(f"{OUT_DIR}/sample_dahua_clean.dav")

    # Corrupted/fragmented -- for deleted-footage / partial-recovery testing
    generate_hikvision_file(f"{OUT_DIR}/sample_hikvision_corrupt.hik", corrupt=True)
    generate_dahua_file(f"{OUT_DIR}/sample_dahua_corrupt.dav", corrupt=True)

    # Unknown vendor -- for Tier 2 universal carving fallback testing
    generate_unknown_vendor_file(f"{OUT_DIR}/sample_unknown_vendor.bin")

    # Pure noise -- false-positive control test for Tier 2
    generate_random_noise_file(f"{OUT_DIR}/sample_random_noise.bin")

    # Combined "disk image" -- end-to-end demo file with both vendors + gaps
    generate_mixed_disk_image(
        f"{OUT_DIR}/sample_combined_disk.img",
        f"{OUT_DIR}/sample_hikvision_clean.hik",
        f"{OUT_DIR}/sample_dahua_clean.dav",
    )

    print("\nDone. All files in ./output/")
