"""
Test harness for the Vendor Identification module.

HOW TO USE:
1. Put this file in the same folder as your vendor_id module (or adjust the
   import path below).
2. Put the sample_data/ folder (from the earlier message) next to this script,
   or update SAMPLE_DIR to point at wherever you saved it.
3. Run: python test_vendor_id.py
4. Read the PASS/FAIL output. Fix the module, re-run, repeat until all pass.

Adjust the `import` line and the call to `detect_vendor(...)` to match your
actual function name/signature -- this is a template, not a guess at your
exact code.
"""
import os
import sys

# --- ADJUST THIS to match your actual module/function ---
try:
    from vendor_id import detect_vendor  # e.g. def detect_vendor(filepath: str) -> str
except ImportError:
    print("!! Could not import detect_vendor from vendor_id.py")
    print("!! Edit the import line at the top of this script to match your actual filename/function name.")
    sys.exit(1)
# ----------------------------------------------------------

SAMPLE_DIR = "sample_data"

# Each entry: (filename, expected_result)
# expected_result should match whatever string/enum your function returns
# for each case -- adjust "hikvision" / "dahua" / "unknown" to your actual values
TEST_CASES = [
    ("sample_hikvision_clean.hik", "hikvision"),
    ("sample_dahua_clean.dav", "dahua"),
    ("sample_hikvision_corrupt.hik", "hikvision"),  # should still ID correctly even if payload is damaged
    ("sample_dahua_corrupt.dav", "dahua"),
    ("sample_unknown_vendor.bin", "unknown"),
    ("sample_random_noise.bin", "unknown"),
]


def run_tests():
    passed = 0
    failed = 0

    for filename, expected in TEST_CASES:
        path = os.path.join(SAMPLE_DIR, filename)
        if not os.path.exists(path):
            print(f"SKIP  {filename} -- file not found at {path}")
            continue

        try:
            result = detect_vendor(path)
        except Exception as e:
            print(f"ERROR {filename} -- your function raised an exception: {e}")
            failed += 1
            continue

        result_normalized = str(result).strip().lower()
        expected_normalized = expected.lower()

        if result_normalized == expected_normalized:
            print(f"PASS  {filename:35s} -> got '{result}' (expected '{expected}')")
            passed += 1
        else:
            print(f"FAIL  {filename:35s} -> got '{result}' (expected '{expected}')")
            failed += 1

    # Special case: the combined disk image should ideally find BOTH vendors
    # if your module is designed to scan a whole blob, not just one file.
    # Comment this out if your vendor_id only supports single-file input for now.
    combined_path = os.path.join(SAMPLE_DIR, "sample_combined_disk.img")
    if os.path.exists(combined_path):
        print("\n--- Combined disk image check (informational, not pass/fail) ---")
        try:
            result = detect_vendor(combined_path)
            print(f"detect_vendor() on combined disk returned: '{result}'")
            print("(If your module only returns ONE vendor for a multi-vendor blob,")
            print(" that's expected for now unless you've built multi-signature scanning.)")
        except Exception as e:
            print(f"Combined disk test raised an exception: {e}")

    print(f"\n{passed} passed, {failed} failed out of {passed + failed} core tests.")
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
