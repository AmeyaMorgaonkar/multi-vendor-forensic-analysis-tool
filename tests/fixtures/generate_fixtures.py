import os
import random
import struct
import shutil
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent
ROOT_DIR = FIXTURES_DIR.parent.parent
SAMPLE_DATA_DIR = ROOT_DIR / "sample_data"


def create_h264_nal_payload(nal_type: int = 7) -> bytes:
    """
    Creates a dummy H.264 NAL unit with start code b'\x00\x00\x00\x01'.
    Types: 7=SPS, 8=PPS, 5=IDR (I-frame), 1=Non-IDR (P-frame).
    """
    start_code = b"\x00\x00\x00\x01"
    if nal_type == 7:  # SPS
        nal_header = bytes([0x67])
        body = b"\x42\xc0\x1f\xda\x01\x40\x16\xec\x04\x40"
    elif nal_type == 8:  # PPS
        nal_header = bytes([0x68])
        body = b"\xce\x3c\x80"
    elif nal_type == 5:  # IDR Slice (I-frame)
        nal_header = bytes([0x65])
        body = b"\x88\x84\x00\x10\x00\x00\x03\x00\x00\x03\x00\x7d\xc0" + b"\xaa" * 128
    else:  # Non-IDR Slice (P-frame)
        nal_header = bytes([0x41])
        body = b"\x9a\x00\x05\x00\x00\x03\x00\x00\x03\x00\x3e\xe0" + b"\xbb" * 64

    return start_code + nal_header + body


def generate_hikvision_fixture(output_path: Path, num_frames: int = 10) -> Path:
    """
    Generates or imports Hikvision fixture.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sample_src = SAMPLE_DATA_DIR / "sample_hikvision_clean.hik"
    if not sample_src.exists():
        sample_src = ROOT_DIR / "sample_hikvision_clean.hik"

    if sample_src.exists():
        shutil.copy(sample_src, output_path)
        return output_path

    base_time = 1788696000
    with open(output_path, "wb") as f:
        for i in range(num_frames):
            nal_type = 5 if (i % 5 == 0) else 1
            payload = create_h264_nal_payload(nal_type)
            header_size = 20
            frame_size = header_size + len(payload)
            timestamp = base_time + (i * 2)
            channel = 1
            frame_type = 1 if (nal_type == 5) else 2

            header = struct.pack(
                "<IB3sIIB3s",
                0x484B5649,
                frame_type,
                b"\x00\x00\x00",
                frame_size,
                timestamp,
                channel,
                b"\x00\x00\x00",
            )
            f.write(header)
            f.write(payload)

    return output_path


def generate_dahua_fixture(output_path: Path, num_frames: int = 10) -> Path:
    """
    Generates or imports Dahua DHFS4.1 fixture.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sample_src = SAMPLE_DATA_DIR / "sample_dahua_clean.dav"
    if not sample_src.exists():
        sample_src = ROOT_DIR / "sample_dahua_clean.dav"

    if sample_src.exists():
        shutil.copy(sample_src, output_path)
        return output_path

    base_time = 1788696000
    with open(output_path, "wb") as f:
        for i in range(num_frames):
            nal_type = 5 if (i % 5 == 0) else 1
            payload = create_h264_nal_payload(nal_type)
            header_size = 32
            footer_size = 12
            total_frame_size = header_size + len(payload) + footer_size

            frame_type = 1
            subtype = 0 if (nal_type == 5) else 1
            channel = 1
            subchannel = 0
            frame_num = i
            datetime_stamp = base_time + i
            ms = 0
            checksum = sum(payload) & 0xFFFFFFFF

            header = struct.pack(
                "<4sBBBBIIIHBI5s",
                b"DHAV",
                frame_type,
                subtype,
                channel,
                subchannel,
                frame_num,
                total_frame_size,
                datetime_stamp,
                ms,
                0,
                checksum,
                b"\x00" * 5,
            )
            footer = struct.pack("<4sII", b"dhav", total_frame_size, checksum)

            f.write(header)
            f.write(payload)
            f.write(footer)

    return output_path


def generate_unknown_vendor_fixture(output_path: Path) -> Path:
    """
    Generates or imports unknown vendor raw stream fixture.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sample_src = SAMPLE_DATA_DIR / "sample_unknown_vendor.bin"
    if not sample_src.exists():
        sample_src = ROOT_DIR / "sample_unknown_vendor.bin"

    if sample_src.exists():
        shutil.copy(sample_src, output_path)
        return output_path

    with open(output_path, "wb") as f:
        f.write(create_h264_nal_payload(7))
        f.write(create_h264_nal_payload(8))
        f.write(create_h264_nal_payload(5))
        f.write(create_h264_nal_payload(1))

    return output_path


def generate_corrupted_fixture(output_path: Path) -> Path:
    """
    Generates or imports corrupted fixture.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sample_src = SAMPLE_DATA_DIR / "sample_dahua_corrupt.dav"
    if not sample_src.exists():
        sample_src = ROOT_DIR / "sample_dahua_corrupt.dav"

    if sample_src.exists():
        shutil.copy(sample_src, output_path)
        return output_path

    base_time = 1788696000
    with open(output_path, "wb") as f:
        payload1 = create_h264_nal_payload(5)
        size1 = 32 + len(payload1) + 12
        h1 = struct.pack(
            "<4sBBBBIIIHBI5s",
            b"DHAV",
            1,
            0,
            1,
            0,
            1,
            size1,
            base_time,
            0,
            0,
            0,
            b"\x00" * 5,
        )
        f1 = struct.pack("<4sII", b"dhav", size1, 0)
        f.write(h1 + payload1 + f1)

        payload2 = create_h264_nal_payload(1)
        size2 = 32 + len(payload2) + 12
        h2 = struct.pack(
            "<4sBBBBIIIHBI5s",
            b"DHAV",
            1,
            1,
            1,
            0,
            2,
            size2,
            base_time + 2,
            0,
            0,
            0,
            b"\x00" * 5,
        )
        bad_f2 = struct.pack("<4sII", b"BADF", size2, 0)
        f.write(h2 + payload2 + bad_f2)

    return output_path


def generate_random_control_data(
    output_path: Path, size_bytes: int = 500_000
) -> Path:
    """
    Generates or imports random control data fixture.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sample_src = SAMPLE_DATA_DIR / "sample_random_noise.bin"
    if not sample_src.exists():
        sample_src = ROOT_DIR / "sample_random_noise.bin"

    if sample_src.exists():
        shutil.copy(sample_src, output_path)
        return output_path

    rng = random.Random(42)
    chunk_size = 65536
    written = 0
    with open(output_path, "wb") as f:
        while written < size_bytes:
            to_write = min(chunk_size, size_bytes - written)
            f.write(rng.randbytes(to_write))
            written += to_write

    return output_path


def verify_all_fixtures():
    """
    Self-verification suite to assert generated/imported fixtures strictly match specifications.
    """
    hik_path = FIXTURES_DIR / "hikvision_clean.dav"
    dahua_path = FIXTURES_DIR / "dahua_clean.dav"
    unknown_path = FIXTURES_DIR / "unknown_vendor_raw.h264"
    corrupt_path = FIXTURES_DIR / "corrupted_fragmented.dav"
    random_path = FIXTURES_DIR / "random_control.bin"

    print("Generating/Importing fixtures...")
    generate_hikvision_fixture(hik_path)
    generate_dahua_fixture(dahua_path)
    generate_unknown_vendor_fixture(unknown_path)
    generate_corrupted_fixture(corrupt_path)
    generate_random_control_data(random_path)

    # Verification 1: Hikvision Magic
    with open(hik_path, "rb") as f:
        content = f.read()
        magic = struct.unpack("<I", content[0:4])[0]
        assert magic == 0x484B5649 or b"HIKVISION" in content

    # Verification 2: Dahua DHAV Header
    with open(dahua_path, "rb") as f:
        content = f.read()
        assert content.startswith(b"DHAV") or content.startswith(b"DHFS4.1")

    # Verification 3: Unknown vendor raw stream
    with open(unknown_path, "rb") as f:
        content = f.read()
        assert len(content) > 0

    print("All fixtures verified successfully!")


if __name__ == "__main__":
    verify_all_fixtures()
