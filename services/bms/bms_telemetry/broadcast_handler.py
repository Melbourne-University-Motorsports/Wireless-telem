"""
broadcast_handler.py
====================
Handles accumulation and extraction of 121-byte packets using the 
additive checksum.
"""

import logging
from typing import Optional, List

log = logging.getLogger(__name__)

PACKET_SIZE = 121
HEADER_BYTE = 0xF3
TRAILER_BYTE = 0x03
TRAILER_COUNT = 8
CRC_FIELD_SIZE = 4 
PAYLOAD_LENGTH = 108 
CHECKSUM_SEED = 0xF36C



class BroadcastHandler:
    """
    Buffers raw BLE bytes and extracts packets using a additive checksum.
    """
    
    def __init__(self):
        self._buffer = bytearray()
    
    def feed(self, data: bytes) -> List[str]:
        """add bytes into buffer, try to extract packet (payload string). Return payload as ascii-hex string"""
        self._buffer.extend(data)
        packets = []

        while True:
            # 1. Sync: Align buffer to the next valid header (start with f3)
            if not self._sync_buffer():
                break

            # 2. Try to process a single packet (end with 8 bytes of 03)
            payload_str = self._try_extract_packet()
            if payload_str:
                packets.append(payload_str)
            else:
                # Could not extract a full/valid packet yet, continue extending data into the buffer.
                break

        return packets

    def _sync_buffer(self) -> bool:
        """
        Discards junk bytes until a header (0xF3) is at the front. Return true if f3 is 
        found in buffer (bytearray). 
        """
        try:
            header_idx = self._buffer.index(HEADER_BYTE)
            if header_idx > 0:
                log.debug(f"Discarding {header_idx} junk bytes")
                del self._buffer[:header_idx]
            return True
        except ValueError:
            # No header found; keep only the last byte to check for split headers
            self._buffer = self._buffer[-1:] if self._buffer else bytearray()
            return False

    def _try_extract_packet(self) -> Optional[str]:
        """Attempts to extract and validate one packet from the front of the buffer."""
        if len(self._buffer) < PACKET_SIZE:
            return None

        # Verify trailer 
        if not self._is_trailer_valid():
            log.debug("Invalid trailer, shifting buffer")
            del self._buffer[:1]
            return None

        # Extract raw components
        payload_bytes = bytes(self._buffer[1 : 1 + PAYLOAD_LENGTH])
        crc_raw = self._buffer[1 + PAYLOAD_LENGTH : 1 + PAYLOAD_LENGTH + CRC_FIELD_SIZE]

        # Checksum check
        payload_str = payload_bytes.decode('ascii')
        if not self._is_checksum_valid(payload_str, crc_raw):
            del self._buffer[:1]
            return None

        # Success: Cleanup and Return
        del self._buffer[:PACKET_SIZE]
        return payload_str

    def _is_trailer_valid(self) -> bool:
        """Checks if the 8-byte trailer (0x03) is correct."""
        trailer_start = PACKET_SIZE - TRAILER_COUNT
        return all(b == TRAILER_BYTE for b in self._buffer[trailer_start:PACKET_SIZE])

    def _is_checksum_valid(self, payload_str: str, crc_raw: bytes) -> bool:
        """
        Validates the 16-bit additive checksum.
        Returns False if any corruption is detected.
        """
        try:
            received_crc = int(crc_raw.decode('ascii'), 16)
            calculated_crc = 0
            
            for i in range(0, len(payload_str), 2):
                hex_pair = payload_str[i:i+2]
                
                # fail immediately if invalid character
                if not all(c.upper() in "0123456789ABCDEF" for c in hex_pair):
                    log.warning(f"Invalid hex {payload_str}' - packet rejected")
                    return False
                
                byte_val = int(hex_pair, 16)
                calculated_crc += byte_val
            
            calculated_crc = calculated_crc & 0xFFFF
            
            if received_crc == calculated_crc:
                return True
            
            log.warning(f"Checksum mismatch: calc=0x{calculated_crc:04X} recv=0x{received_crc:04X}")
            return False
            
        except (UnicodeDecodeError, ValueError) as e:
            log.warning(f"Malformed packet: {e}")
            return False
        
    def reset(self):
        """Clear the internal buffer."""
        self._buffer.clear()