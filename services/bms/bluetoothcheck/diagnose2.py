"""
BMS Diagnostic Script - Logs raw BLE data to file
Run with: python diagnose.py
"""

import asyncio
from datetime import datetime
from pathlib import Path
from bleak import BleakClient, BleakScanner

# Configuration: partial match, case-insensitive, ignores stray control chars
DEVICE_NAME  = "Blue-AL1220BT"
UUID_CHAR    = "0000ffe4-0000-1000-8000-00805f9b34fb"
SCAN_TIMEOUT = 10   # seconds
LOG_DURATION = 30   # seconds

LOG_DIR = Path("logs")


class DiagnosticSession:
    """Holds all mutable state for one logging session."""

    def __init__(self, log_file: str):
        log_file = LOG_DIR / log_file
        self.log_file     = log_file
        Path("logs").mkdir(parents=True, exist_ok=True)
        self.packet_count = 0
        self.total_bytes  = 0
        self.queue: asyncio.Queue = asyncio.Queue()

    def on_notify(self, sender, data: bytearray):
        """Push raw bytes onto the queue; all I/O happens in the writer task."""
        self.queue.put_nowait(bytes(data))

    async def writer_task(self, stop_event: asyncio.Event):
        """Drain the queue and write to file until stopped and queue is empty."""
        while not stop_event.is_set() or not self.queue.empty():
            try:
                raw = await asyncio.wait_for(self.queue.get(), timeout=0.2)
            except asyncio.TimeoutError:
                continue

            self.packet_count += 1
            self.total_bytes  += len(raw)

            line = f"[{self.packet_count:04d}] RAW ({len(raw):3d} bytes): {raw.hex(' ')}\n"
            print(line, end="")
            with open(self.log_file, 'a') as f:
                f.write(line)

            self.queue.task_done()


# ── UUID helpers ───────────────────────────────────────────────────────────────

def print_available_uuids(client: BleakClient):
    """Print all services and characteristics discovered on the device."""
    print("\nWARNING: UUID not found. Available characteristics on this device:")
    for service in client.services:
        print(f"  Service: {service.uuid}  ({service.description})")
        for char in service.characteristics:
            props = ", ".join(char.properties)
            print(f"    Char:  {char.uuid}  [{props}]  ({char.description})")
    print()


def find_notify_uuid(client: BleakClient, wanted: str) -> str | None:
    """Return wanted UUID if it exists and supports notify, else None."""
    for service in client.services:
        for char in service.characteristics:
            if char.uuid.lower() == wanted.lower():
                if "notify" in char.properties:
                    return char.uuid
                else:
                    print(f"WARNING: UUID {wanted} found but does NOT support notify.")
                    print(f"   Properties: {', '.join(char.properties)}")
                    return None
    return None


# ── Scan helper ────────────────────────────────────────────────────────────────

async def find_device(name_fragment: str):
    """
    Discover all BLE devices and return the first whose name contains
    name_fragment (case-insensitive). Always prints every device found
    so you can see the exact advertised name if matching fails.
    """
    print(f"Scanning for devices containing '{name_fragment}' ({SCAN_TIMEOUT}s)...")
    adv_map = await BleakScanner.discover(timeout=SCAN_TIMEOUT, return_adv=True)
    all_devices = list(adv_map.values())  # list of (BLEDevice, AdvertisementData)

    print(f"\nDiscovered {len(all_devices)} device(s):")
    for d, adv in sorted(all_devices, key=lambda x: x[0].name or ""):
        print(f"  [{d.address}]  rssi={adv.rssi:4d}  name={repr(d.name)}")
    print()

    matches = [
        d for d, adv in all_devices
        if d.name and name_fragment.lower() in d.name.lower()
    ]

    if not matches:
        print(f"ERROR: No device found containing '{name_fragment}'.")
        print("Check the names printed above and update DEVICE_NAME to match.")
        return None

    if len(matches) > 1:
        print(f"WARNING: {len(matches)} matches found, using the first:")
        for d in matches:
            print(f"  {repr(d.name)}  [{d.address}]")
        print()

    return matches[0]


# ── Main ───────────────────────────────────────────────────────────────────────

async def main():
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file   = f"bms_diagnostic_{timestamp}.txt"
    session    = DiagnosticSession(log_file)
    stop_event = asyncio.Event()

    print("=" * 60)
    print("BMS Diagnostic Tool")
    print("=" * 60)
    print(f"Log file: {log_file}")
    print()

    device = await find_device(DEVICE_NAME)
    if not device:
        return

    print(f"Using: {repr(device.name)} [{device.address}]")
    print("Connecting...")

    disconnected = asyncio.Event()

    def on_disconnect(client: BleakClient):
        print("\nDevice disconnected unexpectedly.")
        disconnected.set()
        stop_event.set()

    try:
        async with BleakClient(device, disconnected_callback=on_disconnect) as client:
            print("Connected!")

            notify_uuid = find_notify_uuid(client, UUID_CHAR)
            if notify_uuid is None:
                print_available_uuids(client)
                return

            writer = asyncio.create_task(session.writer_task(stop_event))

            await client.start_notify(notify_uuid, session.on_notify)
            print(f"Subscribed to {notify_uuid}")
            print(f"Logging for {LOG_DURATION} seconds... (Ctrl+C to stop early)")
            print("-" * 60)

            await asyncio.wait(
                [asyncio.create_task(asyncio.sleep(LOG_DURATION)),
                 asyncio.create_task(disconnected.wait())],
                return_when=asyncio.FIRST_COMPLETED,
            )

            if not disconnected.is_set():
                try:
                    await client.stop_notify(notify_uuid)
                except Exception:
                    pass

            stop_event.set()
            await writer

    except Exception as e:
        print(f"ERROR: {e}")
        stop_event.set()

    print("-" * 60)
    print("Logging complete!")
    print(f"  Total packets:   {session.packet_count}")
    print(f"  Total bytes:     {session.total_bytes}")
    if session.packet_count > 0:
        print(f"  Avg packet size: {session.total_bytes / session.packet_count:.1f} bytes")
    print(f"Log saved to: {log_file}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped by user.")