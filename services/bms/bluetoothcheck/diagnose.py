"""
BMS Diagnostic Script - Logs raw BLE data to file
Run with: python diagnose.py
"""

import asyncio
from datetime import datetime
from pathlib import Path
from bleak import BleakClient, BleakScanner

# Configuration
DEVICE_NAME  = "Blue-AL1220BT\r"
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

    # ── BLE callback (must not block) ─────────────────────────────────────────

    def on_notify(self, sender, data: bytearray):
        """Push raw bytes onto the queue; all I/O happens in the writer task."""
        self.queue.put_nowait(bytes(data))

    # ── Writer task ───────────────────────────────────────────────────────────

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


# ── UUID helpers ──────────────────────────────────────────────────────────────

def print_available_uuids(client: BleakClient):
    """Print all services and characteristics discovered on the device."""
    print("\n⚠  UUID not found. Available characteristics on this device:")
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
                    print(f"⚠  UUID {wanted} found but does NOT support notify.")
                    print(f"   Properties: {', '.join(char.properties)}")
                    return None
    return None


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file  = f"bms_diagnostic_{timestamp}.txt"
    session   = DiagnosticSession(log_file)
    stop_event = asyncio.Event()

    print("=" * 60)
    print("BMS Diagnostic Tool")
    print("=" * 60)
    print(f"📁 Logging to: {log_file}")
    print()

    print(f"Scanning for '{DEVICE_NAME}'...")
    device = await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=SCAN_TIMEOUT)
    

    if not device:
        print(f"ERROR: Device '{DEVICE_NAME}' not found!")
        print("\nTroubleshooting:")
        print("  1. Is the BMS powered on?")
        print("  2. Is Bluetooth enabled on this computer?")
        print("  3. Are you within range (~10 meters)?")
        return

    print(f"✓ Found: {device.name} [{device.address}]")
    print("Connecting...")

    try:
        async with BleakClient(device) as client:
            print("✓ Connected!")

            # Validate UUID before subscribing
            notify_uuid = find_notify_uuid(client, UUID_CHAR)
            if notify_uuid is None:
                print_available_uuids(client)
                return

            # Start writer before subscribing so no packets are lost
            writer = asyncio.create_task(session.writer_task(stop_event))

            await client.start_notify(notify_uuid, session.on_notify)
            print(f"✓ Subscribed to {notify_uuid}")
            print(f"  Logging for {LOG_DURATION} seconds... (Ctrl+C to stop early)")
            print("-" * 60)

            try:
                await asyncio.sleep(LOG_DURATION)
            except (asyncio.CancelledError, KeyboardInterrupt):
                print("Stopping early...")
            finally:
                await client.stop_notify(notify_uuid)
                stop_event.set()
                await writer

            await client.stop_notify(notify_uuid)
            stop_event.set()
            await writer   # drain remaining queue items

            print("-" * 60)
            print("Logging complete!")
            print(f"  Total packets: {session.packet_count}")
            print(f"  Total bytes:   {session.total_bytes}")
            if session.packet_count > 0:
                print(f"  Avg packet size: {session.total_bytes / session.packet_count:.1f} bytes")
            print(f"📁 Log saved to: {log_file}")

    except Exception as e:
        print(f"ERROR: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped by user.")