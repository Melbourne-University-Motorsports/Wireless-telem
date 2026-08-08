# check crc logic sum: conclusion: ascii bytes turn into hex, sum the hex and we can get the crc (ascii to hex)
# '32 31' (ascii bytes) -> 32 31 (hex bytes) -> '2 1' (hex to ascii) ->21 (ascii to hex = 1byte)


def hex_to_ascii(hex_string):
    """Convert hex string to ASCII, handling non-printable characters."""
    hex_clean = hex_string.replace(" ", "")
    try:
        bytes_data = bytes.fromhex(hex_clean)
        ascii_text = bytes_data.decode('ascii', errors='replace')
        return ascii_text
    except Exception as e:
        return f"Error: {e}"


raw_hex = """f3 31 42 33 34 30 30 30 30 30 30 30 30 30 30 30 30
32 30 34 45 30 30 30 30 30 38 30 30 26 31 30 30
36 44 30 42 30 30 43 30 30 37 42 34
30 31 30 44 30 36 30 44 30 38 30 44 30 43 30 44
30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30
30 30 30 30 30 30 30 30 30 20 30 30 30 30 30 30
30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30
30 33 36 38 03 03 03 03 03 03 03 03"""

# Convert to raw bytes
hex_clean = raw_hex.replace(" ", "")
raw_bytes = bytes.fromhex(hex_clean) # 1. convert hex strings into actual bytes

# Extract each part
header = raw_bytes[0:1]       # Byte 0: 0xF3
payload = raw_bytes[1:109]    # Bytes 1-108: Payload (108 bytes)
crc_bytes = raw_bytes[109:113] # Bytes 109-112: CRC (4 ASCII chars)
trailer = raw_bytes[113:121]  # Bytes 113-120: Trailer (8 x 0x03)

# Convert payload to ASCII string
payload_str = payload.decode('ascii', errors='replace') # 2. convert bytes into ascii string, replace w ? if not valid ascii
print(f"Payload string: {payload_str}")
print(f"Payload length: {len(payload_str)} chars")

# Convert CRC bytes to string
crc_str = crc_bytes.decode('ascii')
crc_value = int(crc_str, 16) # convert hex str to int
print(f"\nCRC string: '{crc_str}'")
print(f"CRC value:  {crc_value} (0x{crc_value:04X})")

# THE ACTUAL CHECKSUM CALCULATION:
# Sum of decoded hex values from the payload string
checksum = 0
for i in range(0, len(payload_str), 2):
    hex_pair = payload_str[i:i+2]
    
    # Process each character in the pair
    safe_pair = ""
    for char in hex_pair:
        # Check if the character is a valid hex digit (0-9, a-f)
        if char.upper() in "0123456789ABCDEF":
            safe_pair += char
        else:
            # Replace invalid character with '0'
            safe_pair += "0"
    
    # Now convert the "sanitized" pair to an integer
    byte_val = int(safe_pair, 16)
    checksum += byte_val & 0xFFFF # keep only the lower 16 bit

print(f"\nCalculated checksum: {checksum} (0x{checksum:04X})")
print(f"Received CRC:       {crc_value} (0x{crc_value:04X})")
print(f"Match: {'yes, accept packet' if checksum == crc_value else 'no, reject packet'}")