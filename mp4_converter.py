"""
Convert ANY mp4 into synthetic Hikvision/Dahua format, and back to mp4.

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
"""
import subprocess
import struct
import sys
import os

NAL_START = b'\x00\x00\x00\x01'
HIK_MAGIC = 0x484B5649
DHAV_HEADER_MAGIC = b'DHAV'
DHAV_FOOTER_MAGIC = b'dhav'


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


def build_hikvision_frame(payload: bytes, frame_type: int, channel: int, timestamp: int) -> bytes:
    # Header is 20 bytes (offsets 0-19), spec says payload length = frame_size - 24,
    # meaning 4 reserved/trailing bytes follow the payload before the next frame.
    frame_size = len(payload) + 24
    header = struct.pack('<I', HIK_MAGIC)
    header += struct.pack('<B', frame_type)
    header += b'\x00\x00\x00'
    header += struct.pack('<I', frame_size)
    header += struct.pack('<I', timestamp)
    header += struct.pack('<B', channel)
    header += b'\x00\x00\x00'
    trailer = b'\x00\x00\x00\x00'  # reserved 4 bytes accounted for in frame_size math
    return header + payload + trailer


def build_dahua_frame(payload: bytes, frame_number: int, channel: int, timestamp: int) -> bytes:
    frame_size = len(payload) + 32
    checksum = simple_checksum(payload)
    header = DHAV_HEADER_MAGIC
    header += struct.pack('<B', 1) + struct.pack('<B', 0)
    header += struct.pack('<B', channel) + struct.pack('<B', 0)
    header += struct.pack('<I', frame_number)
    header += struct.pack('<I', frame_size)
    header += struct.pack('<I', timestamp)
    header += struct.pack('<H', 0)
    header += struct.pack('<B', 0)
    header += struct.pack('<I', checksum)
    header += b'\x00' * (32 - len(header))
    footer = DHAV_FOOTER_MAGIC + struct.pack('<I', frame_size) + struct.pack('<I', checksum)
    return header + payload + footer


def convert_to_hikvision(mp4_path: str, out_path: str):
    h264 = extract_annexb_h264(mp4_path)
    nal_units = split_into_nal_units(h264)
    out = bytearray()
    base_ts = 1700000000
    for i, nal in enumerate(nal_units):
        out += build_hikvision_frame(nal, frame_type=1, channel=1, timestamp=base_ts + i)
    with open(out_path, 'wb') as f:
        f.write(bytes(out))
    print(f"Wrote {out_path} ({len(out)} bytes, {len(nal_units)} frames) from {mp4_path}")


def convert_to_dahua(mp4_path: str, out_path: str):
    h264 = extract_annexb_h264(mp4_path)
    nal_units = split_into_nal_units(h264)
    out = bytearray()
    base_ts = 1700000000
    for i, nal in enumerate(nal_units):
        out += build_dahua_frame(nal, frame_number=i, channel=1, timestamp=base_ts + i)
    with open(out_path, 'wb') as f:
        f.write(bytes(out))
    print(f"Wrote {out_path} ({len(out)} bytes, {len(nal_units)} frames) from {mp4_path}")


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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    mode = sys.argv[1]
    if mode == "to_hikvision":
        convert_to_hikvision(sys.argv[2], sys.argv[3])
    elif mode == "to_dahua":
        convert_to_dahua(sys.argv[2], sys.argv[3])
    elif mode == "to_mp4":
        fmt = sys.argv[sys.argv.index("--format") + 1] if "--format" in sys.argv else None
        if fmt == "hikvision":
            convert_hikvision_to_mp4(sys.argv[2], sys.argv[3])
        elif fmt == "dahua":
            convert_dahua_to_mp4(sys.argv[2], sys.argv[3])
        else:
            print("Specify --format hikvision or --format dahua")
    else:
        print(__doc__)