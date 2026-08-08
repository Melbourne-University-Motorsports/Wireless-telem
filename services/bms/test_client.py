"""
test_client.py
==============
Integration-style tests for BMSClient — the layer test_bms.py doesn't touch.

Where test_bms.py tests pure logic (bytes in → objects out), client.py talks
to the outside world: Bluetooth, ZMQ, files, the clock. The technique for
testing such code is to replace each outside dependency with a *fake* we
control, then check the client did the right thing to each of them:

    real dependency          fake used here
    ---------------          -------------------------------------------
    ZMQ PUB socket        →  FakePublisher   (records every message)
    BLE device + bleak    →  FakeBleakClient (replays canned bytes)
    BleakScanner          →  fake find_device_by_name (scripted results)
    logs/ folder          →  pytest's tmp_path (fresh temp dir per test)

Tests are organised in three levels, each exercising a bigger slice:

  1. TestOnData     — on_data() alone: publish + JSONL write
  2. TestOnNotify   — _on_notify(): raw chunked bytes → assembled → on_data
  3. TestFullFlow   — run(): scan → connect → stream → disconnect → files
"""

import asyncio
import json

import pytest

# Reuse the packet-builder fixtures from the existing suite.
# (conftest.py has already stubbed out bleak before these imports run.)
from test_bms import build_packet, chunk

from bms_telemetry.models import BMSData
import bms_telemetry.client as client_mod
from bms_telemetry.client import BMSClient


# ===========================================================================
# Fakes
# ===========================================================================

class FakePublisher:
    """
    Stands in for zmq.asyncio.Socket. The real one sends bytes over TCP;
    this one just appends every message to a list so tests can inspect
    exactly what *would* have been sent.
    """

    def __init__(self):
        self.messages = []          # list of [topic, timestamp, value] frame-lists

    async def send_multipart(self, frames):
        self.messages.append(frames)

    # -- convenience helpers for assertions --------------------------------

    def topics(self) -> list[str]:
        return [frames[0].decode() for frames in self.messages]

    def value_for(self, topic: str) -> str:
        """Return the value frame of the first message with this topic."""
        for frames in self.messages:
            if frames[0].decode() == topic:
                return frames[2].decode()
        raise AssertionError(f"no message published for topic {topic!r}")


def make_client(tmp_path, *, device_name="Test-AL1220BT", jsonl=True) -> tuple[BMSClient, FakePublisher]:
    """Build a BMSClient wired to a FakePublisher, logging into tmp_path."""
    publisher = FakePublisher()
    client = BMSClient(
        device_name=device_name,
        topic_prefix="lvb1",
        publisher=publisher,
        log_dir=str(tmp_path / "logs"),
        jsonl=jsonl,
    )
    return client, publisher


def read_jsonl_records(client: BMSClient) -> list[dict]:
    """Read every record from every session .jsonl file of this client."""
    records = []
    for path in sorted(client._data_subdir.glob("*.jsonl")):
        for line in path.read_text().splitlines():
            records.append(json.loads(line))
    return records


# ===========================================================================
# 1. on_data() — publishing and JSONL persistence
# ===========================================================================

class TestOnData:

    def _run_on_data(self, client, data_objects):
        """Drive the async on_data() from a plain sync test."""
        async def scenario():
            client._open_session_files()
            for data in data_objects:
                await client.on_data(data)
        asyncio.run(scenario())

    def test_publishes_name_plus_every_signal(self, tmp_path):
        client, publisher = make_client(tmp_path)
        self._run_on_data(client, [BMSData(voltage=13338, soc=9700)])

        # 1 name message + 8 signal messages (see BMSData.to_dict)
        assert len(publisher.messages) == 9
        assert publisher.topics()[0] == "lvb1.name"
        assert publisher.value_for("lvb1.name") == "Test-AL1220BT"
        assert publisher.value_for("lvb1.voltage") == "13338"
        assert publisher.value_for("lvb1.soc") == "9700"

    def test_every_message_has_three_frames(self, tmp_path):
        client, publisher = make_client(tmp_path)
        self._run_on_data(client, [BMSData()])
        for frames in publisher.messages:
            assert len(frames) == 3

    def test_same_timestamp_across_one_packet(self, tmp_path):
        """All signals from one packet must share an identical timestamp."""
        client, publisher = make_client(tmp_path)
        self._run_on_data(client, [BMSData()])
        timestamps = {frames[1] for frames in publisher.messages}
        assert len(timestamps) == 1

    def test_jsonl_record_written(self, tmp_path):
        """The bug we fixed: jsonl=True must actually persist packets."""
        client, _ = make_client(tmp_path, jsonl=True)
        self._run_on_data(client, [BMSData(voltage=123, current=-50)])

        records = read_jsonl_records(client)
        assert len(records) == 1
        assert records[0]["voltage"] == 123
        assert records[0]["current"] == -50
        assert records[0]["device"] == "Test-AL1220BT"
        assert records[0]["packet_number"] == 1

    def test_jsonl_packet_numbers_increment(self, tmp_path):
        client, _ = make_client(tmp_path)
        self._run_on_data(client, [BMSData(), BMSData(), BMSData()])
        assert [r["packet_number"] for r in read_jsonl_records(client)] == [1, 2, 3]

    def test_jsonl_disabled_writes_nothing(self, tmp_path):
        client, publisher = make_client(tmp_path, jsonl=False)
        self._run_on_data(client, [BMSData(voltage=999)])

        # Still publishes over ZMQ...
        assert publisher.value_for("lvb1.voltage") == "999"
        # ...but creates no data dir and opens no data file.
        assert not (client._device_dir / "data").exists()
        assert client._log_file is None


# ===========================================================================
# 2. _on_notify() — raw BLE chunks through assembly + parse to on_data
# ===========================================================================

class TestOnNotify:

    def _feed(self, client, raw: bytes, mtu: int = 20):
        """Deliver raw bytes to the client the way bleak would: in chunks."""
        async def scenario():
            client._open_session_files()
            for piece in chunk(raw, mtu):
                await client._on_notify(0, bytearray(piece))
        asyncio.run(scenario())

    def test_one_packet_chunked_reaches_publisher(self, tmp_path):
        client, publisher = make_client(tmp_path)
        self._feed(client, build_packet(voltage=4242), mtu=20)
        assert publisher.value_for("lvb1.voltage") == "4242"
        assert client._packet_count == 1

    def test_three_packets_all_processed_in_order(self, tmp_path):
        client, publisher = make_client(tmp_path)
        stream = (build_packet(soc=1000) + build_packet(soc=5000)
                  + build_packet(soc=9999))
        self._feed(client, stream, mtu=23)
        soc_values = [f[2].decode() for f in publisher.messages
                      if f[0] == b"lvb1.soc"]
        assert soc_values == ["1000", "5000", "9999"]

    def test_corrupt_packet_publishes_nothing(self, tmp_path):
        client, publisher = make_client(tmp_path)
        self._feed(client, build_packet(corrupt_crc=True), mtu=20)
        assert publisher.messages == []
        assert client._packet_count == 0

    def test_corrupt_between_good_only_good_published(self, tmp_path):
        client, publisher = make_client(tmp_path)
        stream = (build_packet(voltage=1001)
                  + build_packet(voltage=9999, corrupt_crc=True)
                  + build_packet(voltage=1002))
        self._feed(client, stream, mtu=20)
        voltages = [f[2].decode() for f in publisher.messages
                    if f[0] == b"lvb1.voltage"]
        assert voltages == ["1001", "1002"]


# ===========================================================================
# 3. run() — the full session lifecycle with a fake Bluetooth stack
# ===========================================================================

class TestFullFlow:
    """
    Simulates one complete real-world session:

        scan finds device → connect → notifications stream in (MTU 20)
        → device disconnects → loop rescans → we stop the client

    by patching the two bleak entry points client.py uses. Everything else
    (BroadcastHandler, ProtocolParser, session files, JSONL, publishing)
    is the real production code.
    """

    def _run_session(self, tmp_path, raw_stream: bytes,
                     scan_results: list) -> tuple[BMSClient, FakePublisher]:
        """
        scan_results scripts each successive scan: a "device" object to
        connect to, None for "not found", or StopClient to end the test.
        """
        client, publisher = make_client(tmp_path)

        class StopClient(Exception):
            pass

        class FakeDevice:
            name = client._device_name
            address = "AA:BB:CC:DD:EE:FF"

        scans = iter(scan_results)

        class FakeScanner:
            @staticmethod
            async def find_device_by_name(name, timeout):
                step = next(scans, StopClient)
                if step is StopClient:
                    # Simulate Ctrl-C: run() treats CancelledError as "stop".
                    raise asyncio.CancelledError
                if isinstance(step, Exception):
                    raise step
                return FakeDevice() if step else None

        class FakeBleakClient:
            """Mimics bleak's async context manager + notify API."""

            def __init__(self, device, disconnected_callback=None):
                self._disconnected_callback = disconnected_callback

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def start_notify(self, uuid, callback):
                # Replay the canned byte stream in BLE-sized chunks,
                # then report a disconnect — like a real session ending.
                for piece in chunk(raw_stream, 20):
                    await callback(0, bytearray(piece))
                self._disconnected_callback(self)

        # Swap the real bleak classes inside the client module for our fakes
        real_scanner, real_bleak = client_mod.BleakScanner, client_mod.BleakClient
        client_mod.BleakScanner, client_mod.BleakClient = FakeScanner, FakeBleakClient
        client_mod.RECONNECT_DELAY = 0.0   # don't sleep 5s in failure tests
        try:
            asyncio.run(client.run())
        finally:
            client_mod.BleakScanner, client_mod.BleakClient = real_scanner, real_bleak

        return client, publisher

    def test_full_session_publishes_and_persists(self, tmp_path):
        stream = build_packet(voltage=13338, soc=9700) + build_packet(voltage=13340, soc=9698)
        client, publisher = self._run_session(
            tmp_path, stream,
            scan_results=[True],       # scan 1: found → session runs; scan 2: stop
        )

        # Both packets went out over ZMQ (9 messages each)
        assert len(publisher.messages) == 18
        voltages = [f[2].decode() for f in publisher.messages
                    if f[0] == b"lvb1.voltage"]
        assert voltages == ["13338", "13340"]

        # Both packets were persisted to the session's JSONL file
        records = read_jsonl_records(client)
        assert [r["voltage"] for r in records] == [13338, 13340]

        # A session .log file exists and recorded the lifecycle
        logs = list(client._log_subdir.glob("*.log"))
        assert logs, "expected at least one session .log file"
        merged = "".join(p.read_text() for p in logs)
        assert "Connected" in merged
        assert "Device disconnected." in merged
        assert "Stopped." in merged

        # No failures were recorded
        assert not client._errors_file.exists()

    def test_reconnect_gets_fresh_session_files(self, tmp_path):
        """Two connect/disconnect cycles → two separate session data files."""
        stream = build_packet(voltage=1111)
        client, publisher = self._run_session(
            tmp_path, stream,
            scan_results=[True, True],   # two full sessions, then stop
        )
        assert len(list(client._data_subdir.glob("*.jsonl"))) >= 2
        voltages = [f[2].decode() for f in publisher.messages
                    if f[0] == b"lvb1.voltage"]
        assert voltages == ["1111", "1111"]

    def test_scan_failure_recorded_in_errors_file(self, tmp_path):
        """An exception in the loop must append a record to the errors file."""
        client, publisher = self._run_session(
            tmp_path, b"",
            scan_results=[RuntimeError("adapter exploded")],  # then stop
        )
        assert publisher.messages == []

        lines = client._errors_file.read_text().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["error"] == "adapter exploded"
        assert record["packets_received"] == 0
        assert record["device"] == client._device_name
