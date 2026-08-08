"""
BMS Checksum Verifier - Test multiple CRC calculation methods
Just change the SAMPLES list below to test different packets.
"""

SAMPLES = [
    # (payload_string, expected_crc_decimal, label)
    ("1934000000000000204E0000080061006D0B00C007B4010D050D070D0B0D000000000000000000000000000000000000000000000000", 867, "Sample A (clean)"),
    ("1B34000000000000204E00000800&1006D0B00C007B4010D060D080D0C0D0000000000000000000000000 0000000000000000000000", 872, "Sample B (has space)"),
]


def method_1_valid_only(hex_str):
    """
    Method 1: Skip invalid hex pairs.
    Only sum pairs where BOTH characters are valid hex (0-9, A-F).
    """
    valid_hex = set("0123456789ABCDEFabcdef")
    total = 0
    skipped = 0

    for i in range(0, len(hex_str) - 1, 2):
        pair = hex_str[i:i+2]
        if pair[0] in valid_hex and pair[1] in valid_hex:
            total += int(pair, 16)
        else:
            skipped += 1

    return total & 0xFFFF, skipped


def method_2_replace_bad(hex_str):
    """
    Method 2: Replace non-hex characters with '0', then sum.
    """
    cleaned = ""
    replaced = 0

    for char in hex_str:
        if char.upper() in "0123456789ABCDEF":
            cleaned += char
        else:
            cleaned += "0"
            replaced += 1

    total = 0
    for i in range(0, len(cleaned), 2):
        total += int(cleaned[i:i+2], 16)

    return total & 0xFFFF, replaced


def method_3_raw_bytes(hex_str):
    """
    Method 3: Sum the raw byte values of EVERY character (as-is).
    Does NOT decode hex—just sums the ASCII/byte values of each char.
    '&' stays as 0x26, ' ' stays as 0x20, 'p' stays as 0x70.
    """
    total = sum(hex_str.encode('ascii', errors='replace'))
    return total & 0xFFFF


# ===========================================================================
# Run all methods against all samples
# ===========================================================================

print("=" * 70)
print("BMS CHECKSUM VERIFIER - Testing 3 Methods")
print("=" * 70)

for payload_str, expected_crc, label in SAMPLES:
    print(f"\n{'─' * 70}")
    print(f"📋 {label}")
    print(f"   Payload length: {len(payload_str)} chars")
    print(f"   Expected CRC:   {expected_crc} (0x{expected_crc:04X})")

    # Method 1: Valid pairs only
    result, skipped = method_1_valid_only(payload_str)
    match = "✅ MATCH" if result == expected_crc else "❌"
    print(f"\n   Method 1 (skip invalid):     {result:5d} (0x{result:04X}) {match}")
    if skipped:
        print(f"     → Skipped {skipped} invalid pair(s)")

    # Method 2: Replace invalid with '0'
    result, replaced = method_2_replace_bad(payload_str)
    match = "✅ MATCH" if result == expected_crc else "❌"
    print(f"   Method 2 (replace → '0'):    {result:5d} (0x{result:04X}) {match}")
    if replaced:
        print(f"     → Replaced {replaced} character(s)")

    # Method 3: Raw byte sum (no hex decoding)
    result = method_3_raw_bytes(payload_str)
    match = "✅ MATCH" if result == expected_crc else "❌"
    print(f"   Method 3 (raw byte sum):      {result:5d} (0x{result:04X}) {match}")

print(f"\n{'=' * 70}")
print("Done! Add more samples to the SAMPLES list to test more packets.")
print("=" * 70)