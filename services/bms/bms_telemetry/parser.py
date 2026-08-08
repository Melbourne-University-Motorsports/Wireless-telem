"""
parser.py
=========
Parser for the BMS ASCII-hex payload format.
"""

import logging
import struct
from typing import Optional

try:
    from .models import BMSData
    from .constants import PAYLOAD_LENGTH
except ImportError:
    from models import BMSData
    from constants import PAYLOAD_LENGTH

log = logging.getLogger(__name__)


class ProtocolParser:
    """
    Parses ASCII-hex payload strings into BMSData objects.

    The payload is a 108-character ASCII hex string (54 encoded bytes).
    Each pair of characters represents one byte (little-endian multi-byte fields).

    Field offsets within the decoded byte array:
        Voltage:     bytes[0:4]   - uint32 LE  (chars  0-7)
        Current:     bytes[4:8]   - int32  LE  (chars  8-15)
        Capacity:    bytes[8:12]  - uint32 LE  (chars 16-23)
        Cycles:      bytes[12:14] - uint16 LE  (chars 24-27)
        SOC:         bytes[14:16] - uint16 LE  (chars 28-31)
        Temperature: bytes[16:18] - uint16 LE  (chars 32-35)
        Status:      bytes[18]    - uint8       (chars 36-37)
        AFE Status:  bytes[20]    - uint8       (chars 40-41)
    """
    
    def __init__(self):
        self._last_valid_data: Optional[BMSData] = None
    
    
    def parse(self, payload: str) -> Optional[BMSData]:
        """
        Parse a payload string into BMSData.
        Args:
            payload: 108-character ASCII hex string (54 encoded bytes)

        Returns:
            BMSData object if parsing succeeds, None otherwise
        """
        if len(payload) < PAYLOAD_LENGTH:  # Must be exactly 108 chars (54 bytes) for all fields
            log.warning(f"Payload too short: {len(payload)} chars (expected {PAYLOAD_LENGTH})")
            return None

        if len(payload) % 2 != 0:
            log.warning(f"Payload has odd length {len(payload)}, cannot decode")
            return None
        
        try:
            payload_bytes = bytes.fromhex(payload)  # 108 chars → 54 bytes

            voltage     = struct.unpack_from('<I', payload_bytes, 0)[0]   # Bytes 0-3   ← Chars 0-7
            current     = struct.unpack_from('<i', payload_bytes, 4)[0]   # Bytes 4-7   ← Chars 8-15
            capacity    = struct.unpack_from('<I', payload_bytes, 8)[0]   # Bytes 8-11  ← Chars 16-23
            cycles      = struct.unpack_from('<H', payload_bytes, 12)[0]  # Bytes 12-13 ← Chars 24-27
            soc         = struct.unpack_from('<H', payload_bytes, 14)[0]  # Bytes 14-15 ← Chars 28-31
            temperature = struct.unpack_from('<H', payload_bytes, 16)[0]  # Bytes 16-17 ← Chars 32-35
            status      = payload_bytes[18]                                # Byte 18     ← Chars 36-37
            afe_status  = payload_bytes[20]                                # Byte 20     ← Chars 40-41`
            
            # Validate required fields
            if any(v is None for v in [voltage, current, capacity, cycles, soc, temperature, status]):
                log.error("Failed to parse one or more required fields")
                return None
            
            data = BMSData(
                voltage=voltage,
                current=current,
                soc=soc,
                capacity=capacity,
                cycles=cycles,
                temperature=temperature,
                status=status,
                afe_status=afe_status,
                raw_payload=payload
            )
            
            self._last_valid_data = data
            return data
            
        except Exception as e:
            log.error(f"Error parsing payload: {e}")
            return None
    
    @property
    def last_valid_data(self) -> Optional[BMSData]:
        """Return the last successfully parsed data."""
        return self._last_valid_data