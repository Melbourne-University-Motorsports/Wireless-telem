"""
client.py
=========
Async BLE client for the BMS telemetry system.
"""

import asyncio
from datetime import datetime
import json
import logging
from pathlib import Path
import time
import traceback

import zmq.asyncio
from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

try:
    # Package import (e.g. `pytest`, or another project importing bms_telemetry as a module)
    from .constants import (
        DEVICE_NAME_PATTERN,
        INITIAL_SCAN_TIMEOUT,
        RECONNECT_DELAY,
        SCAN_TIMEOUT,
        UUID_CHAR,
    )
    from .models import BMSData
    from .broadcast_handler import BroadcastHandler
    from .parser import ProtocolParser
except ImportError:
    # Bare import (running `python3 main.py` directly on the Pi)
    from constants import (
        DEVICE_NAME_PATTERN,
        INITIAL_SCAN_TIMEOUT,
        RECONNECT_DELAY,
        SCAN_TIMEOUT,
        UUID_CHAR,
    )
    from models import BMSData
    from broadcast_handler import BroadcastHandler
    from parser import ProtocolParser

log = logging.getLogger(__name__)


async def scan_for_bms_devices(timeout: float = INITIAL_SCAN_TIMEOUT) -> list[BLEDevice]:
    """Scan all nearby BLE devices and return those whose name contains DEVICE_NAME_PATTERN."""
    log.info(f"Scanning for BMS devices (pattern: '{DEVICE_NAME_PATTERN}', timeout: {timeout}s)...")
    devices = await BleakScanner.discover(timeout=timeout)
    matched = [d for d in devices if d.name and DEVICE_NAME_PATTERN in d.name]
    if matched:
        log.info(f"Found {len(matched)} BMS device(s): {[d.name for d in matched]}")
    else:
        log.warning("No BMS devices found.")
    return matched


def _safe_name(device_name: str) -> str:
    return "".join(c for c in device_name if c.isalnum() or c in "-_")


class BMSClient:
    """
    Connects to a single BMS device by name, subscribes to notifications,
    and processes data. Reconnects automatically on disconnect.
    """

    def __init__(self, device_name: str, topic_prefix: str, publisher: zmq.asyncio.Socket, 
                 log_dir: str = "logs", jsonl: bool = False, verbose: bool = False) -> None:
        self._device_name = device_name
        self._topic_prefix = topic_prefix
        self._publisher = publisher
        self._jsonl = jsonl
        self._verbose = verbose
        self._broadcast = BroadcastHandler()
        self._parser = ProtocolParser()

        name = _safe_name(device_name)
        self._device_dir = Path(log_dir) / name
        self._log_subdir = self._device_dir / "log"
        self._log_subdir.mkdir(parents=True, exist_ok=True)
        self._errors_dir = self._device_dir / "errors"
        self._errors_dir.mkdir(parents=True, exist_ok=True)
        self._errors_file = self._errors_dir / f"{_safe_name(device_name)}_failures.jsonl"
        if jsonl:
            self._data_subdir = self._device_dir / "data"
            self._data_subdir.mkdir(parents=True, exist_ok=True)

        self._log_file = None # this has nothing to do w self._log, purely for jsonl
        self._packet_count = 0

        # Per-device logger — new file each session, set in _open_session_files()
        self._log = logging.getLogger(f"bms_telemetry.device.{name}")
        self._log.setLevel(logging.DEBUG)
        self._log_handler: logging.FileHandler | None = None

    def _log_failure(self, exc: Exception) -> None:
        """Append a failed session record to the device's errors file."""
        record = {
            "timestamp": datetime.now().isoformat(),
            "device": self._device_name,
            "packets_received": self._packet_count,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        with open(self._errors_file, "a") as f:
            f.write(json.dumps(record) + "\n")

    def _open_session_files(self):
        """Create timestamped log and data files for this session."""
        # %f (microseconds) guarantees unique filenames even on same-second reconnects
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        name = _safe_name(self._device_name)

        # Rotate the log file handler for this session
        if self._log_handler:
            self._log.removeHandler(self._log_handler)
            self._log_handler.close()
        log_path = self._log_subdir / f"{name}_{timestamp}.log"
        self._log_handler = logging.FileHandler(log_path)
        self._log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        self._log.addHandler(self._log_handler)

        if self._jsonl:
            data_path = self._data_subdir / f"{name}_{timestamp}.jsonl"
            self._log_file = open(data_path, "w")
            self._log.info(f"Session started — data → {data_path}")
        else:
            self._log.info("Session started — JSONL logging disabled")

    async def on_data(self, data: BMSData) -> None:
        """Called for every valid received packet."""
        self._packet_count += 1

        if self._verbose:
            print(f"[{self._device_name}][{self._packet_count:04d}] {data}")

        timestamp_us = time.time_ns() // 1000

        # Publish device name so subscribers know which physical battery lvb1/lvb2 is
        await self._publisher.send_multipart([
            f"{self._topic_prefix}.name".encode(),
            str(timestamp_us).encode(),
            self._device_name.encode(),
        ])

        # Publish each signal
        for signal_name, value in data.to_dict().items():
            await self._publisher.send_multipart([
                f"{self._topic_prefix}.{signal_name}".encode(),
                str(timestamp_us).encode(),
                str(value).encode(),
            ])

        if self._log_file:
            record = {
                "timestamp": datetime.now().isoformat(),
                "device": self._device_name,
                "packet_number": self._packet_count,
                **data.to_dict(),
            }
            self._log_file.write(json.dumps(record) + "\n")
            self._log_file.flush()

    async def _on_notify(self, _sender: int, raw: bytearray) -> None:
        """Handle incoming BLE notifications."""
        self._log.debug(f"RX {len(raw)} bytes: {raw.hex(' ')}")

        payloads = self._broadcast.feed(bytes(raw))
        for payload in payloads:
            result = self._parser.parse(payload)
            if result:
                self._log.info(f"Packet OK → {result}")
                await self.on_data(result)

    async def _connect_and_run(self, device: BLEDevice) -> None:
        """Connect, subscribe, and block until the device disconnects."""
        disconnected = asyncio.Event()

        async with BleakClient(
            device,
            disconnected_callback=lambda _: disconnected.set(),
        ) as client:
            self._log.info(f"Connected [{device.address}]")
            await client.start_notify(UUID_CHAR, self._on_notify)
            await asyncio.sleep(0.5)
            self._log.info("Streaming data...")
            await disconnected.wait()
            self._log.warning("Device disconnected.")

    async def run(self) -> None:
        """Scan, connect, and reconnect indefinitely. Stop with Ctrl-C."""
        while True:
            try:
                self._packet_count = 0
                self._open_session_files()
                self._log.info("Scanning...")
                device = await BleakScanner.find_device_by_name(
                    self._device_name, timeout=SCAN_TIMEOUT
                )

                if device is None:
                    self._log.warning(f"Not found, retrying in {RECONNECT_DELAY:.0f}s...")
                    await asyncio.sleep(RECONNECT_DELAY)
                    continue

                await self._connect_and_run(device)

            except asyncio.CancelledError:
                self._log.info("Stopped.")
                break
            except Exception as exc:
                self._log.error(f"Error: {exc} – retrying in {RECONNECT_DELAY:.0f}s...")
                self._log_failure(exc)
                await asyncio.sleep(RECONNECT_DELAY)
            finally:
                if self._log_file:
                    self._log_file.close()
                    self._log_file = None
