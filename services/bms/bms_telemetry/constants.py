"""
constants.py
============
Protocol and BLE constants for BMS telemetry.
"""

# BLE identifiers

# Substring matched against advertised device names: matches "Red-AL1220BT", "Blue-AL1220BT", etc.
DEVICE_NAME_PATTERN = "AL1220BT"
UUID_SERVICE = "0000ffe0-0000-1000-8000-00805f9b34fb"
UUID_CHAR    = "0000ffe4-0000-1000-8000-00805f9b34fb"

# Protocol framing (121-byte packets)

PACKET_SIZE = 121
HEADER = bytes([0xF3, 0x45])
END_PATTERN = bytes([0x03] * 8)
CRC_LENGTH = 4
PAYLOAD_LENGTH = 108  # ASCII hex string length (108 hex chars = 54 bytes)


# Connection tuning

INITIAL_SCAN_TIMEOUT = 15.0  # seconds for startup device discovery
SCAN_TIMEOUT = 5.0           # seconds per reconnect scan attempt
RECONNECT_DELAY = 5.0        # seconds between reconnect attempts

# ZMQ
ZMQ_PUB_PORT = 5559
