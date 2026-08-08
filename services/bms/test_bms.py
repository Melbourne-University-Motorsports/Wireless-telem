"""
test_bms.py
===========
Unit tests for the BMS BLE telemetry protocol stack.

Tests are organised into four groups:

  1. Packet builder helpers (sanity-check the test fixtures themselves)
  2. BroadcastHandler – framing, checksum, buffer management
  3. ProtocolParser   – field decoding, edge cases
  4. BLE simulation   – realistic chunked-delivery scenarios that mirror
                        what the car sends over Bluetooth
"""

from pathlib import Path
import struct
import pytest


# Inline the package without needing bleak installed
import sys, types

# Stub bleak before any bms import — __init__.py pulls in client.py which imports bleak
def _stub_bleak():
    bleak = types.ModuleType("bleak")
    bleak.BleakClient  = object
    bleak.BleakScanner = object
    sys.modules["bleak"] = bleak
    sys.modules["bleak.backends"] = types.ModuleType("bleak.backends")
    dev = types.ModuleType("bleak.backends.device")
    dev.BLEDevice = object
    sys.modules["bleak.backends.device"] = dev
_stub_bleak()

sys.path.insert(0, str(Path(__file__).parent))
from bms_telemetry.broadcast_handler import BroadcastHandler
from bms_telemetry.parser import ProtocolParser
from bms_telemetry.models import BMSData

import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("_constants", Path(__file__).parent / "bms_telemetry" / "constants.py")
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
DEVICE_NAME_PATTERN = _mod.DEVICE_NAME_PATTERN


# ===========================================================================
# Test fixtures / packet builder
# ===========================================================================

# Real captured packets from the car (space-separated hex tokens → bytes)
def _h(s: str) -> bytes:
    return bytes(int(x, 16) for x in s.split())

REAL_PKT1_BAD_CRC = _h(
    "f3 31 42 33 34 30 30 30 30 30 30 30 30 30 30 30 30 32 30 34 45 30 30 30 30 30 38 30 30"
    " 26 31 30 30 36 44 30 42 30 30 43 30 30 37 42 34 30 31 30 44 30 36 30 44 30 38 30 44"
    " 30 43 30 44 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30"
    " 30 20 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 33 36 38"
    " 03 03 03 03 03 03 03 03"
)

REAL_PKT2_GOOD = _h(
    "f3 31 41 33 34 30 30 30 30 30 30 30 30 30 30 30 30 32 30 34 45 30 30 30 30 30 38 30 30"
    " 36 31 30 30 36 45 30 42 30 30 43 30 30 37 42 34 30 31 30 44 30 36 30 44 30 38 30 44"
    " 30 42 30 44 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30"
    " 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 33 36 37"
    " 03 03 03 03 03 03 03 03"
)

REAL_PKT3_GOOD = _h(
    "f3 32 31 33 34 30 30 30 30 30 30 30 30 30 30 30 30 32 30 34 45 30 30 30 30 30 38 30 30"
    " 36 31 30 30 36 45 30 42 30 30 43 30 30 37 42 34 30 33 30 44 30 38 30 44 30 39 30 44"
    " 30 44 30 44 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30"
    " 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 33 37 35"
    " 03 03 03 03 03 03 03 03"
)


def build_packet(
    voltage: int = 13338,
    current: int = 0,
    capacity: int = 20000,
    cycles: int = 8,
    soc: int = 97,
    temperature: int = 2926,
    status: int = 0x00,
    afe_status: int = 0x07,
    corrupt_crc: bool = False,
    bad_byte_offset: int = None,
    bad_byte_val: int = 0xFF,
) -> bytes:
    """
    Construct a valid 121-byte BMS packet from field values.

    Layout: [0xF3][108 ASCII hex payload][4 ASCII hex CRC][8 x 0x03]

    Set corrupt_crc=True to produce a packet with a wrong CRC.
    Set bad_byte_offset/bad_byte_val to stomp a raw byte anywhere in the packet.
    """
    payload_bytes = bytearray(54)
    struct.pack_into("<I", payload_bytes, 0, voltage & 0xFFFFFFFF)
    struct.pack_into("<i", payload_bytes, 4, current)
    struct.pack_into("<I", payload_bytes, 8, capacity & 0xFFFFFFFF)
    struct.pack_into("<H", payload_bytes, 12, cycles & 0xFFFF)
    struct.pack_into("<H", payload_bytes, 14, soc & 0xFFFF)
    struct.pack_into("<H", payload_bytes, 16, temperature & 0xFFFF)
    payload_bytes[18] = status & 0xFF
    payload_bytes[20] = afe_status & 0xFF

    payload_str = payload_bytes.hex().upper()  # 108 chars
    assert len(payload_str) == 108

    crc = sum(int(payload_str[i : i + 2], 16) for i in range(0, 108, 2)) & 0xFFFF
    if corrupt_crc:
        crc = (crc + 1) & 0xFFFF
    crc_str = f"{crc:04X}"

    packet = bytearray()
    packet.append(0xF3)
    packet.extend(payload_str.encode("ascii"))
    packet.extend(crc_str.encode("ascii"))
    packet.extend([0x03] * 8)

    assert len(packet) == 121

    if bad_byte_offset is not None:
        packet[bad_byte_offset] = bad_byte_val

    return bytes(packet)


def chunk(data: bytes, size: int):
    """Split bytes into chunks of `size`, simulating BLE MTU fragmentation."""
    return [data[i : i + size] for i in range(0, len(data), size)]


# ===========================================================================
# 1. Packet builder sanity checks
# ===========================================================================

class TestPacketBuilder:
    def test_length_is_121(self):
        assert len(build_packet()) == 121

    def test_header_byte(self):
        assert build_packet()[0] == 0xF3

    def test_trailer_bytes(self):
        pkt = build_packet()
        assert all(b == 0x03 for b in pkt[113:])

    def test_payload_is_ascii_hex(self):
        pkt = build_packet()
        payload = pkt[1:109].decode("ascii")
        assert all(c in "0123456789ABCDEFabcdef" for c in payload)

    def test_crc_field_is_ascii_hex(self):
        pkt = build_packet()
        crc_str = pkt[109:113].decode("ascii")
        int(crc_str, 16)  # should not raise

    def test_corrupt_crc_differs(self):
        good = build_packet()
        bad = build_packet(corrupt_crc=True)
        assert good[109:113] != bad[109:113]

    def test_negative_current_roundtrip(self):
        pkt = build_packet(current=-1000)
        payload_str = pkt[1:109].decode("ascii")
        pb = bytes.fromhex(payload_str)
        assert struct.unpack_from("<i", pb, 4)[0] == -1000

    def test_real_pkt2_length(self):
        assert len(REAL_PKT2_GOOD) == 121

    def test_real_pkt3_length(self):
        assert len(REAL_PKT3_GOOD) == 121


# ===========================================================================
# 2. BroadcastHandler unit tests
# ===========================================================================

class TestBroadcastHandler:

    # --- Happy path ---------------------------------------------------------

    def test_single_valid_packet_accepted(self):
        handler = BroadcastHandler()
        results = handler.feed(build_packet())
        assert len(results) == 1

    def test_single_valid_packet_payload_length(self):
        handler = BroadcastHandler()
        results = handler.feed(build_packet())
        assert len(results[0]) == 108

    def test_real_packet2_accepted(self):
        handler = BroadcastHandler()
        results = handler.feed(REAL_PKT2_GOOD)
        assert len(results) == 1

    def test_real_packet3_accepted(self):
        handler = BroadcastHandler()
        results = handler.feed(REAL_PKT3_GOOD)
        assert len(results) == 1

    def test_two_consecutive_valid_packets(self):
        handler = BroadcastHandler()
        results = handler.feed(build_packet() + build_packet(voltage=9999))
        assert len(results) == 2

    def test_payload_content_roundtrip(self):
        """Payload returned by handler decodes back to the same field values."""
        handler = BroadcastHandler()
        results = handler.feed(build_packet(voltage=12345, soc=5000))
        assert len(results) == 1
        pb = bytes.fromhex(results[0])
        assert struct.unpack_from("<I", pb, 0)[0] == 12345
        assert struct.unpack_from("<H", pb, 14)[0] == 5000

    # --- CRC rejection ------------------------------------------------------

    def test_corrupt_crc_rejected(self):
        handler = BroadcastHandler()
        results = handler.feed(build_packet(corrupt_crc=True))
        assert results == []

    def test_real_packet1_rejected_bad_crc(self):
        """Packet 1 from car sample contains non-hex chars → should be rejected."""
        handler = BroadcastHandler()
        results = handler.feed(REAL_PKT1_BAD_CRC)
        assert results == []

    def test_invalid_hex_in_payload_rejected(self):
        """A packet with a non-hex ASCII char inside the payload is rejected."""
        pkt = bytearray(build_packet())
        pkt[30] = ord("&")  # stomp a payload byte with a non-hex char
        handler = BroadcastHandler()
        results = handler.feed(bytes(pkt))
        assert results == []

    # --- Trailer validation -------------------------------------------------

    def test_bad_trailer_rejected(self):
        pkt = bytearray(build_packet())
        pkt[115] = 0xFF  # corrupt one trailer byte
        handler = BroadcastHandler()
        results = handler.feed(bytes(pkt))
        assert results == []

    # --- Junk / partial data ------------------------------------------------

    def test_junk_prefix_stripped(self):
        """Random bytes before the header should be discarded."""
        junk = bytes([0xAA, 0xBB, 0xCC, 0x00, 0x11])
        handler = BroadcastHandler()
        results = handler.feed(junk + build_packet())
        assert len(results) == 1

    def test_partial_packet_not_returned(self):
        """Feeding half a packet returns nothing."""
        pkt = build_packet()
        handler = BroadcastHandler()
        results = handler.feed(pkt[:60])
        assert results == []

    def test_partial_then_complete(self):
        """Feeding the second half completes the packet."""
        pkt = build_packet()
        handler = BroadcastHandler()
        handler.feed(pkt[:60])
        results = handler.feed(pkt[60:])
        assert len(results) == 1

    def test_empty_feed_returns_empty(self):
        handler = BroadcastHandler()
        assert handler.feed(b"") == []

    def test_no_header_in_garbage(self):
        garbage = bytes([0x00, 0x01, 0x02, 0xAA, 0xBB] * 30)
        handler = BroadcastHandler()
        assert handler.feed(garbage) == []

    # --- Reset --------------------------------------------------------------

    def test_reset_clears_partial(self):
        pkt = build_packet()
        handler = BroadcastHandler()
        handler.feed(pkt[:60])       # partial — nothing returned
        handler.reset()
        results = handler.feed(pkt)  # full packet after reset
        assert len(results) == 1

    def test_reset_then_two_packets(self):
        handler = BroadcastHandler()
        handler.feed(build_packet()[:40])
        handler.reset()
        results = handler.feed(build_packet() + build_packet(voltage=1))
        assert len(results) == 2

    # --- Buffer state after extraction --------------------------------------

    def test_buffer_empty_after_clean_extraction(self):
        """After extracting a packet the internal buffer should be empty."""
        handler = BroadcastHandler()
        handler.feed(build_packet())
        assert len(handler._buffer) == 0

    def test_remainder_kept_in_buffer(self):
        """Trailing bytes that don't form a packet stay buffered."""
        handler = BroadcastHandler()
        handler.feed(build_packet() + bytes([0xF3, 0x00]))
        assert len(handler._buffer) == 2


# ===========================================================================
# 3. ProtocolParser unit tests
# ===========================================================================

class TestProtocolParser:

    def _payload(self, **kwargs) -> str:
        """Build a packet and extract just the payload string."""
        pkt = build_packet(**kwargs)
        return pkt[1:109].decode("ascii")

    # --- Happy path ---------------------------------------------------------

    def test_parse_returns_bmsdata(self):
        parser = ProtocolParser()
        result = parser.parse(self._payload())
        assert isinstance(result, BMSData)

    def test_voltage_field(self):
        parser = ProtocolParser()
        result = parser.parse(self._payload(voltage=13338))
        assert result.voltage == 13338

    def test_current_field_positive(self):
        parser = ProtocolParser()
        result = parser.parse(self._payload(current=1500))
        assert result.current == 1500

    def test_current_field_negative(self):
        """Negative current (charging) must be decoded as signed int32."""
        parser = ProtocolParser()
        result = parser.parse(self._payload(current=-750))
        assert result.current == -750

    def test_capacity_field(self):
        parser = ProtocolParser()
        result = parser.parse(self._payload(capacity=20000))
        assert result.capacity == 20000

    def test_cycles_field(self):
        parser = ProtocolParser()
        result = parser.parse(self._payload(cycles=42))
        assert result.cycles == 42

    def test_soc_field(self):
        parser = ProtocolParser()
        result = parser.parse(self._payload(soc=5000))
        assert result.soc == 5000

    def test_temperature_field(self):
        parser = ProtocolParser()
        result = parser.parse(self._payload(temperature=2926))
        assert result.temperature == 2926

    def test_status_field(self):
        parser = ProtocolParser()
        result = parser.parse(self._payload(status=0xAB))
        assert result.status == 0xAB

    def test_afe_status_field(self):
        parser = ProtocolParser()
        result = parser.parse(self._payload(afe_status=0x07))
        assert result.afe_status == 0x07

    def test_raw_payload_stored(self):
        parser = ProtocolParser()
        payload = self._payload()
        result = parser.parse(payload)
        assert result.raw_payload == payload

    def test_last_valid_data_updated(self):
        parser = ProtocolParser()
        parser.parse(self._payload(voltage=111))
        assert parser.last_valid_data is not None
        assert parser.last_valid_data.voltage == 111

    def test_last_valid_data_not_overwritten_on_bad_parse(self):
        parser = ProtocolParser()
        parser.parse(self._payload(voltage=999))
        parser.parse("tooshort")
        assert parser.last_valid_data.voltage == 999

    # --- Real packets -------------------------------------------------------

    def test_real_packet2_voltage(self):
        parser = ProtocolParser()
        handler = BroadcastHandler()
        payloads = handler.feed(REAL_PKT2_GOOD)
        result = parser.parse(payloads[0])
        assert result.voltage == 13338

    def test_real_packet2_capacity(self):
        parser = ProtocolParser()
        handler = BroadcastHandler()
        payloads = handler.feed(REAL_PKT2_GOOD)
        result = parser.parse(payloads[0])
        assert result.capacity == 20000

    def test_real_packet3_voltage_differs_from_pkt2(self):
        """Packets 2 and 3 have slightly different voltages."""
        parser = ProtocolParser()
        handler = BroadcastHandler()
        r2 = parser.parse(handler.feed(REAL_PKT2_GOOD)[0])
        handler.reset()
        r3 = parser.parse(handler.feed(REAL_PKT3_GOOD)[0])
        assert r2.voltage != r3.voltage

    # --- Rejection ----------------------------------------------------------

    def test_payload_too_short_returns_none(self):
        parser = ProtocolParser()
        assert parser.parse("1A2B3C") is None

    def test_empty_payload_returns_none(self):
        parser = ProtocolParser()
        assert parser.parse("") is None

    def test_odd_length_payload_returns_none(self):
        parser = ProtocolParser()
        # 109 chars is odd but > 108
        assert parser.parse("A" * 109) is None

    def test_non_hex_payload_returns_none(self):
        parser = ProtocolParser()
        assert parser.parse("ZZ" * 54) is None

    # --- BMSData helpers ----------------------------------------------------

    def test_str_representation(self):
        parser = ProtocolParser()
        result = parser.parse(self._payload(voltage=13338, soc=5000))
        s = str(result)
        assert "50.0%" in s
        assert "13338" in s

    def test_to_dict_keys(self):
        parser = ProtocolParser()
        result = parser.parse(self._payload())
        d = result.to_dict()
        for key in ("voltage", "current", "soc", "capacity", "cycles",
                    "temperature", "status", "afe_status"):
            assert key in d


# ===========================================================================
# 4. BLE simulation tests
#    These tests mimic the Bluetooth stack delivering packets in chunks,
#    exactly as the car sends them over the air.
# ===========================================================================

class TestBLESimulation:
    """
    Real BLE has a negotiated ATT MTU (commonly 20, 23, 64, or 247 bytes).
    The BMS notifies 121-byte packets which the Android/iOS BLE stack
    fragments into consecutive notification chunks.  We simulate this by
    splitting our built packets into N-byte chunks and feeding them one at
    a time, just like _on_notify() would be called.
    """

    def _pipe(self, raw_bytes: bytes, mtu: int) -> list[BMSData]:
        """Feed `raw_bytes` through handler+parser in `mtu`-sized chunks."""
        handler = BroadcastHandler()
        parser = ProtocolParser()
        results = []
        for chunk_data in chunk(raw_bytes, mtu):
            for payload in handler.feed(chunk_data):
                data = parser.parse(payload)
                if data:
                    results.append(data)
        return results

    # --- Single packet, various MTU sizes -----------------------------------

    def test_mtu_20_single_packet(self):
        """20-byte MTU: 121 bytes needs 7 notifications (6×20 + 1×1)."""
        results = self._pipe(build_packet(voltage=1111), mtu=20)
        assert len(results) == 1
        assert results[0].voltage == 1111

    def test_mtu_23_single_packet(self):
        results = self._pipe(build_packet(voltage=2222), mtu=23)
        assert len(results) == 1
        assert results[0].voltage == 2222

    def test_mtu_64_single_packet(self):
        results = self._pipe(build_packet(voltage=3333), mtu=64)
        assert len(results) == 1
        assert results[0].voltage == 3333

    def test_mtu_247_single_packet(self):
        """Packet fits in one notification at high MTU."""
        results = self._pipe(build_packet(voltage=4444), mtu=247)
        assert len(results) == 1
        assert results[0].voltage == 4444

    def test_mtu_1_byte_at_a_time(self):
        """Pathological: every byte arrives as a separate notification."""
        results = self._pipe(build_packet(voltage=5555), mtu=1)
        assert len(results) == 1
        assert results[0].voltage == 5555

    # --- Multiple packets back-to-back --------------------------------------

    def test_three_packets_mtu_20(self):
        pkt_a = build_packet(voltage=100, soc=1000)
        pkt_b = build_packet(voltage=200, soc=2000)
        pkt_c = build_packet(voltage=300, soc=3000)
        results = self._pipe(pkt_a + pkt_b + pkt_c, mtu=20)
        assert len(results) == 3
        assert results[0].voltage == 100
        assert results[1].voltage == 200
        assert results[2].voltage == 300

    def test_three_packets_soc_values(self):
        pkt_a = build_packet(soc=1000)
        pkt_b = build_packet(soc=5000)
        pkt_c = build_packet(soc=9999)
        results = self._pipe(pkt_a + pkt_b + pkt_c, mtu=23)
        assert [r.soc for r in results] == [1000, 5000, 9999]

    # --- Junk between valid packets (line noise / BLE resets) ---------------

    def test_junk_between_packets_mtu_20(self):
        junk = bytes([0xAA, 0xBB, 0xCC, 0xDD] * 5)
        stream = build_packet(voltage=777) + junk + build_packet(voltage=888)
        results = self._pipe(stream, mtu=20)
        assert len(results) == 2
        assert results[0].voltage == 777
        assert results[1].voltage == 888

    def test_junk_at_start_mtu_20(self):
        junk = bytes([0x00, 0x11, 0x22] * 10)
        stream = junk + build_packet(voltage=555)
        results = self._pipe(stream, mtu=20)
        assert len(results) == 1
        assert results[0].voltage == 555

    # --- Bad packet sandwiched between good ones ----------------------------

    def test_corrupt_packet_between_good_ones(self):
        """A packet with wrong CRC must not prevent the next good packet parsing."""
        good1 = build_packet(voltage=1001)
        bad = build_packet(voltage=9999, corrupt_crc=True)
        good2 = build_packet(voltage=1002)
        results = self._pipe(good1 + bad + good2, mtu=20)
        # Only the two good packets come through
        assert len(results) == 2
        assert results[0].voltage == 1001
        assert results[1].voltage == 1002

    def test_real_pkt1_bad_pkt2_good_pkt3_good_mtu_20(self):
        """Exactly the three real captured packets, MTU=20."""
        stream = REAL_PKT1_BAD_CRC + REAL_PKT2_GOOD + REAL_PKT3_GOOD
        results = self._pipe(stream, mtu=20)
        assert len(results) == 2

    # --- Negative current (charging scenario) -------------------------------

    def test_charging_current_mtu_20(self):
        """Car is charging: current is negative."""
        results = self._pipe(build_packet(current=-1500), mtu=20)
        assert len(results) == 1
        assert results[0].current == -1500

    # --- Field value boundary checks ----------------------------------------

    def test_soc_100_percent(self):
        results = self._pipe(build_packet(soc=10000), mtu=20)
        assert results[0].soc == 10000

    def test_soc_0_percent(self):
        results = self._pipe(build_packet(soc=0), mtu=20)
        assert results[0].soc == 0

    def test_max_cycles(self):
        results = self._pipe(build_packet(cycles=65535), mtu=20)
        assert results[0].cycles == 65535

    def test_status_flags_preserved(self):
        results = self._pipe(build_packet(status=0xFF), mtu=20)
        assert results[0].status == 0xFF

    # --- Exactly MTU-boundary-aligned split ---------------------------------

    def test_split_exactly_at_crc_boundary(self):
        """Split the packet right between payload and CRC bytes."""
        pkt = build_packet(voltage=6666)
        # 1 header + 108 payload = 109 → split here, leaving CRC+trailer in second chunk
        handler = BroadcastHandler()
        parser = ProtocolParser()
        handler.feed(pkt[:109])
        payloads = handler.feed(pkt[109:])
        results = [parser.parse(p) for p in payloads if parser.parse(p)]
        # Re-parse correctly
        handler2 = BroadcastHandler()
        parser2 = ProtocolParser()
        for half in (pkt[:109], pkt[109:]):
            for p in handler2.feed(half):
                r = parser2.parse(p)
                if r:
                    assert r.voltage == 6666

    def test_split_exactly_at_trailer_boundary(self):
        """Split right before the 8-byte trailer."""
        pkt = build_packet(voltage=7777)
        handler = BroadcastHandler()
        parser = ProtocolParser()
        results = []
        for half in (pkt[:113], pkt[113:]):
            for p in handler.feed(half):
                r = parser.parse(p)
                if r:
                    results.append(r)
        assert len(results) == 1
        assert results[0].voltage == 7777


# ===========================================================================
# 5. Device name pattern matching
#    Tests the substring filter used in scan_for_bms_devices() to pick up
#    BMS devices by name. If DEVICE_NAME_PATTERN or the filter logic changes,
#    these tests will catch it.
# ===========================================================================

class _FakeDevice:
    def __init__(self, name):
        self.name = name

def _filter(devices):
    return [d for d in devices if d.name and DEVICE_NAME_PATTERN in d.name]


class TestDeviceNamePattern:

    def test_exact_name_matches(self):
        assert len(_filter([_FakeDevice("AL1220BT")])) == 1

    def test_prefixed_name_matches(self):
        assert len(_filter([_FakeDevice("Red-AL1220BT")])) == 1

    def test_multiple_prefixed_names_all_match(self):
        devices = [_FakeDevice("Red-AL1220BT"), _FakeDevice("Blue-AL1220BT")]
        assert len(_filter(devices)) == 2

    def test_unrelated_name_no_match(self):
        assert _filter([_FakeDevice("SomeOtherDevice")]) == []

    def test_partial_pattern_no_match(self):
        assert _filter([_FakeDevice("AL1220")]) == []

    def test_none_name_no_match(self):
        assert _filter([_FakeDevice(None)]) == []

    def test_empty_name_no_match(self):
        assert _filter([_FakeDevice("")]) == []

    def test_case_sensitive_no_match(self):
        assert _filter([_FakeDevice("al1220bt")]) == []

    def test_mixed_devices_only_bms_returned(self):
        devices = [
            _FakeDevice("AL1220BT"),
            _FakeDevice("Unrelated"),
            _FakeDevice(None),
            _FakeDevice("Blue-AL1220BT"),
        ]
        result = _filter(devices)
        assert len(result) == 2
        assert all(DEVICE_NAME_PATTERN in d.name for d in result)