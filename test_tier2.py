"""
Test harness for Tier 2 (universal H.264/H.265 carving).

Checks two different things from Tier 1:
1. Does it actually RECOVER real video from an unknown-wrapper file?
2. What's the FALSE POSITIVE RATE on pure noise? (This is the number
   your teammate's review flagged as the real risk -- get an actual
   measured number, don't guess.)
3. Is it FAST ENOUGH (mmap + regex, not byte-by-byte) for a live demo file?

ADJUST the import to match your actual Tier 2 module/function name.
"""
import os
import sys
import time

try:
    from tier2_universal import carve_deleted  # e.g. def carve_deleted(filepath) -> list[bytes]
except ImportError:
    print("!! Edit the import line to match your actual Tier 2 module/function name.")
    sys.exit(1)

SAMPLE_DIR = "sample_data"


def test_unknown_vendor_recovery():
    path = os.path.join(SAMPLE_DIR, "sample_unknown_vendor.bin")
    print("=== Unknown-vendor file (should recover real video) ===")
    start = time.time()
    recovered = carve_deleted(path)
    elapsed = time.time() - start

    ok_found = len(recovered) > 0
    print(f"  {'PASS' if ok_found else 'FAIL'}  recovered {len(recovered)} fragment(s)")
    print(f"       time taken: {elapsed:.3f}s for {os.path.getsize(path)} bytes")

    # Confirm what was recovered actually contains valid H.264 (not garbage)
    if recovered:
        has_valid_nal = any(b'\x00\x00\x00\x01' in frag for frag in recovered)
        print(f"  {'PASS' if has_valid_nal else 'FAIL'}  recovered data contains real NAL start codes")
        return ok_found and has_valid_nal
    return False


def test_false_positive_rate():
    path = os.path.join(SAMPLE_DIR, "sample_random_noise.bin")
    print("=== Random noise file (false-positive control test) ===")
    start = time.time()
    recovered = carve_deleted(path)
    elapsed = time.time() - start

    file_size = os.path.getsize(path)
    fp_count = len(recovered)
    # Report the actual number -- don't just pass/fail, know the rate.
    # Per the reference paper: header-only matching ~12.7% FP, dual-signature ~2.4%.
    # On 500KB of pure noise you should see very few or zero false hits if
    # your dual-signature (header+footer+checksum) validation is working.
    print(f"  Recovered {fp_count} 'frame(s)' from {file_size} bytes of pure random noise")
    print(f"  Time taken: {elapsed:.3f}s")
    if fp_count == 0:
        print("  PASS  zero false positives on noise")
        return True
    elif fp_count <= 3:
        print("  MARGINAL  a few false positives -- acceptable for demo but worth tightening")
        return True
    else:
        print("  FAIL  high false-positive rate -- check your dual-signature validation logic")
        return False


def test_scan_speed_on_larger_file():
    """Simulate a 'judge hands you a bigger file live' scenario. Concatenates
    the combined disk image several times to simulate a larger unknown file,
    and checks that scan time scales reasonably (mmap+regex should stay fast)."""
    combined_path = os.path.join(SAMPLE_DIR, "sample_combined_disk.img")
    big_path = "tmp_big_test_file.bin"

    with open(combined_path, "rb") as f:
        data = f.read()
    with open(big_path, "wb") as f:
        for _ in range(50):  # ~2MB -- small, but proves the scan path works before you test truly huge files yourself
            f.write(data)

    print("=== Scan speed check on a larger synthetic file ===")
    start = time.time()
    recovered = carve_deleted(big_path)
    elapsed = time.time() - start
    size_mb = os.path.getsize(big_path) / (1024 * 1024)
    speed_mbps = size_mb / elapsed if elapsed > 0 else float('inf')

    print(f"  Scanned {size_mb:.2f} MB in {elapsed:.3f}s ({speed_mbps:.1f} MB/s)")
    # Byte-by-byte iteration is ~5-15 MB/s; mmap+regex should be well above that.
    ok_speed = speed_mbps > 20
    print(f"  {'PASS' if ok_speed else 'FAIL'}  scan speed is consistent with mmap+regex, not byte-by-byte iteration")

    os.remove(big_path)
    return ok_speed


if __name__ == "__main__":
    results = [
        test_unknown_vendor_recovery(),
        test_false_positive_rate(),
        test_scan_speed_on_larger_file(),
    ]
    passed = sum(results)
    print(f"\n{passed}/{len(results)} test groups passed.")
    sys.exit(0 if all(results) else 1)
