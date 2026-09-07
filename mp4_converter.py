"""
Convert ANY mp4 into synthetic Hikvision/Dahua format, and back to mp4.
Now with optional corruption injection for building corrupt test fixtures.

Use case: instead of only testing your pipeline against the plain
FFmpeg test-pattern samples, wrap a real, visually convincing video
(something with actual movement/people/scenes) into vendor format --
better for demo purposes, and a genuine end-to-end round-trip test
of your whole extraction + remux pipeline.

Usage:
    python mp4_converter.py to_hikvision  input.mp4  output.hik
    python mp4_converter.py to_dahua      input.mp4  output.dav
    python mp4_converter.py to_mp4        output.hik  recovered.mp4   --format hikvision
    python mp4_converter.py to_mp4        output.dav  recovered.mp4   --format dahua

    # Corrupted variants -- add --corrupt <type> to either conversion:
    python mp4_converter.py to_hikvision  input.mp4  corrupt.hik  --corrupt bit_flip
    python mp4_converter.py to_dahua      input.mp4  corrupt.dav  --corrupt checksum_mismatch
    python mp4_converter.py to_dahua      input.mp4  corrupt.dav  --corrupt random_mix --seed 42

    Corruption types:
        bit_flip           -- flip a few random bits inside each frame's payload
        checksum_mismatch  -- write a checksum that doesn't match the payload
        corrupt_magic      -- scramble the header magic bytes on affected frames
        drop_footer        -- (Dahua only) omit the footer, simulating an
                               incomplete/interrupted write
        truncate_last      -- cut the final frame short, simulating a
                               power-loss / abrupt-stop scenario
        random_mix         -- pick a different corruption independently for
                               each frame (excludes truncate_last, which is
                               applied once at the end regardless)

    By default (random_mix, no --corrupt-rate given) every frame gets some
    corruption. Use --corrupt-rate to only corrupt a fraction of frames,
    e.g. --corrupt-rate 0.2 corrupts ~20% of frames and leaves the rest clean
    -- generally more realistic than corrupting 100% of a file.
"""
import subprocess
import struct
import sys
import os
import random

NAL_START = b'\x00\x00\x00\x01'
HIK_MAGIC = 0x484B5649
DHAV_HEADER_MAGIC = b'DHAV'
DHAV_FOOTER_MAGIC = b'dhav'

CORRUPTION_TYPES = [
    "bit_flip",
    "checksum_mismatch",
    "corrupt_magic",
    "drop_footer",
    "truncate_last",
    "random_mix",
]

# corruption types that get resolved per-frame inside build_*_frame()
_PER_FRAME_TYPES = ["bit_flip", "checksum_mismatch", "corrupt_magic", "drop_footer"]


def extract_annexb_h264(mp4_path: str) -> bytes:
    """Pull the raw H.264 Annex-B bitstream out of any mp4 using ffmpeg,
    WITHOUT re-encoding -- this is a lossless extraction, same principle
    as your pipeline's own remux step, just running in the other direction."""
    tmp_path = "_tmp_extracted.h264"
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", mp4_path, "-c:v", "copy",
         "-bsf:v", "h264_mp4toannexb", "-f", "h264", tmp_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg extraction failed:\n{result.stderr[-500:]}")
    with open(tmp_path, "rb") as f:
        data = f.read()
    os.remove(tmp_path)
    return data


def split_into_nal_units(data: bytes):
    positions = [m for m in range(len(data)) if data[m:m + 4] == NAL_START]
    positions.append(len(data))
    return [data[positions[i]:positions[i + 1]] for i in range(len(positions) - 1)
            if positions[i + 1] > positions[i]]


def simple_checksum(data: bytes) -> int:
    return sum(data) & 0xFFFFFFFF


def flip_random_bits(payload: bytes) -> bytes:
    if not payload:
        return payload
    payload = bytearray(payload)
    for _ in range(max(1, len(payload) // 50)):
        idx = random.randrange(len(payload))
        payload[idx] ^= 1 << random.randrange(8)
    return bytes(payload)


def pick_frame_corruption(corrupt: str, corrupt_rate: float) -> str:
    """Decide what (if anything) happens to this particular frame."""
    if corrupt is None:
        return None
    if random.random() > corrupt_rate:
        return None  # this frame stays clean
    if corrupt == "random_mix":
        return random.choice(_PER_FRAME_TYPES)
    if corrupt in _PER_FRAME_TYPES:
        return corrupt
    return None  # truncate_last is handled separately, not per-frame here


def build_hikvision_frame(payload: bytes, frame_type: int, channel: int, timestamp: int,
                           corruption: str = None) -> bytes:
    # Header is 20 bytes (offsets 0-19), spec says payload length = frame_size - 24,
    # meaning 4 reserved/trailing bytes follow the payload before the next frame.
    if corruption == "bit_flip":
        payload = flip_random_bits(payload)

    frame_size = len(payload) + 24

    magic = HIK_MAGIC
    magic_bytes = struct.pack('<I', magic)
    if corruption == "corrupt_magic":
        magic_bytes = bytes(b ^ 0xFF for b in magic_bytes)

    header = magic_bytes
    header += struct.pack('<B', frame_type)
    header += b'\x00\x00\x00'
    header += struct.pack('<I', frame_size)
    header += struct.pack('<I', timestamp)
    header += struct.pack('<B', channel)
    header += b'\x00\x00\x00'
    trailer = b'\x00\x00\x00\x00'  # reserved 4 bytes accounted for in frame_size math
    return header + payload + trailer


def build_dahua_frame(payload: bytes, frame_number: int, channel: int, timestamp: int,
                       corruption: str = None) -> bytes:
    if corruption == "bit_flip":
        payload = flip_random_bits(payload)

    frame_size = len(payload) + 32
    checksum = simple_checksum(payload)
    if corruption == "checksum_mismatch":
        checksum = (checksum + 1) & 0xFFFFFFFF

    header_magic = DHAV_HEADER_MAGIC
    if corruption == "corrupt_magic":
        header_magic = bytes(b ^ 0xFF for b in header_magic)

    header = header_magic
    header += struct.pack('<B', 1) + struct.pack('<B', 0)
    header += struct.pack('<B', channel) + struct.pack('<B', 0)
    header += struct.pack('<I', frame_number)
    header += struct.pack('<I', frame_size)
    header += struct.pack('<I', timestamp)
    header += struct.pack('<H', 0)
    header += struct.pack('<B', 0)
    header += struct.pack('<I', checksum)
    header += b'\x00' * (32 - len(header))

    if corruption == "drop_footer":
        return header + payload  # no footer -- simulates an interrupted write

    footer = DHAV_FOOTER_MAGIC + struct.pack('<I', frame_size) + struct.pack('<I', checksum)
    return header + payload + footer


def _apply_truncate_last(out: bytearray, last_frame_len: int) -> bytearray:
    """Cut the final frame in the buffer down to roughly half its length."""
    cut_len = max(1, last_frame_len // 2)
    return out[: len(out) - last_frame_len + cut_len]


def convert_to_hikvision(mp4_path: str, out_path: str, corrupt: str = None,
                          corrupt_rate: float = 1.0):
    h264 = extract_annexb_h264(mp4_path)
    nal_units = split_into_nal_units(h264)
    out = bytearray()
    base_ts = 1700000000
    last_frame_len = 0
    for i, nal in enumerate(nal_units):
        frame_corruption = pick_frame_corruption(corrupt, corrupt_rate)
        frame_bytes = build_hikvision_frame(
            nal, frame_type=1, channel=1, timestamp=base_ts + i,
            corruption=frame_corruption,
        )
        out += frame_bytes
        last_frame_len = len(frame_bytes)

    if corrupt in ("truncate_last", "random_mix") and nal_units:
        out = _apply_truncate_last(out, last_frame_len)

    with open(out_path, 'wb') as f:
        f.write(bytes(out))
    tag = f", corrupt={corrupt}" if corrupt else ""
    print(f"Wrote {out_path} ({len(out)} bytes, {len(nal_units)} frames) from {mp4_path}{tag}")


def convert_to_dahua(mp4_path: str, out_path: str, corrupt: str = None,
                      corrupt_rate: float = 1.0):
    h264 = extract_annexb_h264(mp4_path)
    nal_units = split_into_nal_units(h264)
    out = bytearray()
    base_ts = 1700000000
    last_frame_len = 0
    for i, nal in enumerate(nal_units):
        frame_corruption = pick_frame_corruption(corrupt, corrupt_rate)
        frame_bytes = build_dahua_frame(
            nal, frame_number=i, channel=1, timestamp=base_ts + i,
            corruption=frame_corruption,
        )
        out += frame_bytes
        last_frame_len = len(frame_bytes)

    if corrupt in ("truncate_last", "random_mix") and nal_units:
        out = _apply_truncate_last(out, last_frame_len)

    with open(out_path, 'wb') as f:
        f.write(bytes(out))
    tag = f", corrupt={corrupt}" if corrupt else ""
    print(f"Wrote {out_path} ({len(out)} bytes, {len(nal_units)} frames) from {mp4_path}{tag}")


def convert_hikvision_to_mp4(hik_path: str, out_mp4: str):
    """Reverse direction: parse our own Hikvision-format file back out to raw
    H.264, then remux to mp4. This mirrors exactly what your Tier 1 parser +
    remux module should be doing in your actual pipeline."""
    with open(hik_path, 'rb') as f:
        data = f.read()
    frames = []
    pos = 0
    while pos < len(data):
        magic = struct.unpack('<I', data[pos:pos+4])[0]
        if magic != HIK_MAGIC:
            break
        frame_size = struct.unpack('<I', data[pos+8:pos+12])[0]
        payload = data[pos+20:pos+frame_size-4]  # -4 accounts for the trailing reserved bytes
        frames.append(payload)
        pos += frame_size
    raw_h264 = b''.join(frames)
    tmp = "_tmp_recovered.h264"
    with open(tmp, 'wb') as f:
        f.write(raw_h264)
    result = subprocess.run(
        ["ffmpeg", "-y", "-f", "h264", "-i", tmp, "-c", "copy", out_mp4],
        capture_output=True, text=True
    )
    os.remove(tmp)
    if result.returncode != 0:
        raise RuntimeError(f"remux failed:\n{result.stderr[-500:]}")
    print(f"Wrote {out_mp4} ({len(frames)} frames recovered) from {hik_path}")


def convert_dahua_to_mp4(dav_path: str, out_mp4: str):
    with open(dav_path, 'rb') as f:
        data = f.read()
    frames = []
    pos = 0
    while pos < len(data):
        if data[pos:pos+4] != DHAV_HEADER_MAGIC:
            break
        frame_size = struct.unpack('<I', data[pos+12:pos+16])[0]
        payload = data[pos+32:pos+frame_size]
        frames.append(payload)
        pos += frame_size + 12  # skip footer (12 bytes: magic+size+checksum)
    raw_h264 = b''.join(frames)
    tmp = "_tmp_recovered.h264"
    with open(tmp, 'wb') as f:
        f.write(raw_h264)
    result = subprocess.run(
        ["ffmpeg", "-y", "-f", "h264", "-i", tmp, "-c", "copy", out_mp4],
        capture_output=True, text=True
    )
    os.remove(tmp)
    if result.returncode != 0:
        raise RuntimeError(f"remux failed:\n{result.stderr[-500:]}")
    print(f"Wrote {out_mp4} ({len(frames)} frames recovered) from {dav_path}")


def _get_flag_value(args, flag, default=None):
    if flag in args:
        idx = args.index(flag)
        if idx + 1 < len(args):
            return args[idx + 1]
    return default


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    mode = sys.argv[1]

    if mode in ("to_hikvision", "to_dahua"):
        src, dst = sys.argv[2], sys.argv[3]
        corrupt = _get_flag_value(sys.argv, "--corrupt")
        if corrupt is not None and corrupt not in CORRUPTION_TYPES:
            print(f"Unknown --corrupt type '{corrupt}'. Choose from: {', '.join(CORRUPTION_TYPES)}")
            sys.exit(1)
        rate = float(_get_flag_value(sys.argv, "--corrupt-rate", 1.0))
        seed = _get_flag_value(sys.argv, "--seed")
        if seed is not None:
            random.seed(int(seed))

        if mode == "to_hikvision":
            convert_to_hikvision(src, dst, corrupt=corrupt, corrupt_rate=rate)
        else:
            convert_to_dahua(src, dst, corrupt=corrupt, corrupt_rate=rate)

    elif mode == "to_mp4":
        fmt = _get_flag_value(sys.argv, "--format")
        if fmt == "hikvision":
            convert_hikvision_to_mp4(sys.argv[2], sys.argv[3])
        elif fmt == "dahua":
            convert_dahua_to_mp4(sys.argv[2], sys.argv[3])
        else:
            print("Specify --format hikvision or --format dahua")
    else:
        print(__doc__)