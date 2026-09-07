"""
Test harness for Tier 1 (Dahua/Hikvision) parsers.

Checks not just "does it run" but "are the extracted values actually
correct" -- a parser reading the wrong offset can still produce output
that looks plausible without being right.

ADJUST the import and function calls to match your actual module names.
"""
import os
import sys
import hashlib

try:
    from tier1_hikvision import extract_metadata as hik_extract_metadata
    from tier1_hikvision import extract_video as hik_extract_video
    from tier1_dahua import extract_metadata as dahua_extract_metadata
    from tier1_dahua import extract_video as dahua_extract_video
except ImportError:
    print("!! Edit the import lines at the top to match your actual Tier 1 module/function names.")
    sys.exit(1)

SAMPLE_DIR = "sample_data"


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_hikvision_clean():
    path = os.path.join(SAMPLE_DIR, "sample_hikvision_clean.hik")
    meta = hik_extract_metadata(path)
    video = hik_extract_video(path)

    checks = []
    # These expected values come from generate_samples.py's known output:
    # 46 frames were written, channel=1, base timestamp = generation time
    checks.append(("channel == 1", meta.get("channel") == 1))
    checks.append(("frame_count == 46 (or close)", meta.get("frame_count", 0) in range(44, 48)))
    checks.append(("video payload non-empty", len(video) > 0))
    checks.append(("video contains real H.264 NAL start codes",
                    b'\x00\x00\x00\x01' in video))

    print("=== Hikvision clean file ===")
    for name, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    assert all(ok for _, ok in checks)


def test_hikvision_corrupt():
    path = os.path.join(SAMPLE_DIR, "sample_hikvision_corrupt.hik")
    print("=== Hikvision corrupt file (should degrade gracefully, not crash) ===")
    try:
        meta = hik_extract_metadata(path)
        video = hik_extract_video(path)
        # We're not expecting perfection here -- just NOT a hard crash,
        # and ideally partial recovery (some frames, not zero, not all).
        recovered_something = len(video) > 0
        print(f"  {'PASS' if recovered_something else 'FAIL'}  recovered some data without crashing")
        assert recovered_something
    except Exception as e:
        print(f"  FAIL  parser crashed on corrupt input: {e}")
        assert False, f"parser crashed on corrupt input: {e}"


def test_dahua_clean():
    path = os.path.join(SAMPLE_DIR, "sample_dahua_clean.dav")
    meta = dahua_extract_metadata(path)
    video = dahua_extract_video(path)

    checks = []
    checks.append(("channel == 1", meta.get("channel") == 1))
    checks.append(("frame_count == 46 (or close)", meta.get("frame_count", 0) in range(44, 48)))
    checks.append(("video payload non-empty", len(video) > 0))
    checks.append(("video contains real H.264 NAL start codes",
                    b'\x00\x00\x00\x01' in video))
    # Dahua-specific: did we correctly find footer-validated frames,
    # not just header-matched ones? (dual-signature check)
    checks.append(("footer_validated_frame_count present in metadata",
                    "footer_validated_frame_count" in meta))

    print("=== Dahua clean file ===")
    for name, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    assert all(ok for _, ok in checks)


def test_dahua_corrupt():
    path = os.path.join(SAMPLE_DIR, "sample_dahua_corrupt.dav")
    print("=== Dahua corrupt file (should degrade gracefully) ===")
    try:
        video = dahua_extract_video(path)
        recovered_something = len(video) > 0
        print(f"  {'PASS' if recovered_something else 'FAIL'}  recovered some data without crashing")
        assert recovered_something
    except Exception as e:
        print(f"  FAIL  parser crashed on corrupt input: {e}")
        assert False, f"parser crashed on corrupt input: {e}"


def test_remux_roundtrip():
    """Confirm the extracted video, once remuxed, has the same underlying
    H.264 stream as what was extracted -- i.e. remux isn't silently re-encoding."""
    import subprocess
    path = os.path.join(SAMPLE_DIR, "sample_dahua_clean.dav")
    video = dahua_extract_video(path)

    tmp_h264 = "tmp_extracted.h264"
    tmp_mp4 = "tmp_remuxed.mp4"
    with open(tmp_h264, "wb") as f:
        f.write(video)

    result = subprocess.run(
        ["ffmpeg", "-y", "-f", "h264", "-i", tmp_h264, "-c", "copy", tmp_mp4],
        capture_output=True, text=True
    )
    print("=== Remux check ===")
    if result.returncode != 0:
        print(f"  FAIL  ffmpeg remux failed: {result.stderr[-300:]}")
        assert False, f"ffmpeg remux failed: {result.stderr[-300:]}"

    # Decode both back to raw frames and compare -- if remux re-encoded,
    # this will differ. This is the actual proof, not just "ffmpeg didn't error."
    decode_orig = subprocess.run(
        ["ffmpeg", "-y", "-f", "h264", "-i", tmp_h264, "-f", "md5", "-"],
        capture_output=True, text=True
    )
    tmp_back = "tmp_back.h264"
    subprocess.run(
        ["ffmpeg", "-y", "-i", tmp_mp4, "-c", "copy", "-bsf:v", "h264_mp4toannexb", tmp_back],
        capture_output=True, text=True
    )
    decode_remux = subprocess.run(
        ["ffmpeg", "-y", "-f", "h264", "-i", tmp_back, "-f", "md5", "-"],
        capture_output=True, text=True
    )
    orig_hash = decode_orig.stdout.strip()
    remux_hash = decode_remux.stdout.strip()
    match = orig_hash == remux_hash and orig_hash != ""
    print(f"  {'PASS' if match else 'FAIL'}  decoded frame data matches after remux (proves lossless copy, not re-encode)")
    print(f"    original decode hash: {orig_hash}")
    print(f"    remuxed  decode hash: {remux_hash}")

    os.remove(tmp_h264)
    if os.path.exists(tmp_mp4):
        os.remove(tmp_mp4)
    if os.path.exists(tmp_back):
        os.remove(tmp_back)
    assert match



if __name__ == "__main__":
    results = [
        test_hikvision_clean(),
        test_hikvision_corrupt(),
        test_dahua_clean(),
        test_dahua_corrupt(),
        test_remux_roundtrip(),
    ]
    passed = sum(results)
    print(f"\n{passed}/{len(results)} test groups passed.")
    sys.exit(0 if all(results) else 1)
