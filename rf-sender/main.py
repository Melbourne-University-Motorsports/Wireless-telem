import asyncio
import datetime
import json
import os
import queue
import signal
import struct
import sys
import threading
import time
from pathlib import Path

import cantools
import zmq
from digi_xbee.devices import XBeeDevice
from digi_xbee.exception import XBeeException
from digi_xbee.models.address import XBee64BitAddress

DBC_FILE_PATH = os.environ["DBC_PATH"]
LOG_DIR = Path(os.environ["LOG_DIR"], datetime.now().strftime("%Y%m%d_%H%M%S.mf4"))
BROKER_HOST = os.environ.get("BROKER_HOST", "broker")
BROKER_PORT = int(os.environ.get("BROKER_PORT", "5560"))

XBEE_PORT = os.environ.get("XBEE_PORT", "/dev/ttyUSB0")
XBEE_BAUD = int(os.environ.get("XBEE_BAUD", "230400"))
XBEE_DEST_ADDR = os.environ.get("XBEE_DEST_ADDR", "FFFFFFFFFFFFFFFF")
XBEE_MAX_PAYLOAD = int(os.environ.get("XBEE_MAX_PAYLOAD", "240"))

MAPPING_INTERVAL_S = float(os.environ.get("MAPPING_INTERVAL_S", "2.0"))
BATCH_FLUSH_INTERVAL_S = float(os.environ.get("BATCH_FLUSH_INTERVAL_S", "0.02"))

RECORD_FMT = "<BIf"
RECORD_SIZE = struct.calcsize(RECORD_FMT)
FRAME_TYPE_MAPPING = b"\x01"
FRAME_TYPE_DATA = b"\x02"

write_queue = queue.Queue()

_SENTINEL = None

def build_signal_id_map(dbc: cantools.database.Database):
    """Assign uint8 id to every unique DBC signal name (order is definition order)"""
    names = sorted({sig.name for msg in dbc.messages for sig in msg.signals})
    if len(names) >255:
        raise ValueError(f"{len(names)} signals defined but only 255 ids are addressable with a uint8 id -- widen RECORD_FMT's id field if this DBC grows.")
    id_to_name = {i: name for i, name in enumerate(names)}
    name_to_id = {name: i for i, name in id_to_name.items()}
    units = {sig.name:sig.unit for msg in dbc.messages for sig in msg.signals if sig.unit}
    return name_to_id, id_to_name, units


def xbee_sender_thread(device: XBeeDevice, dest_addr: XBee64BitAddress, id_to_name, units):
    """Batches queued records and sends them over xbee serial link. This is BLOCKING as XBee send calls are blocking and this thread owns the port exclusively"""
    mapping_payload = FRAME_TYPE_MAPPING + json.dumps(
            {str(i): [name, units.get(name, "")] for i, name in id_to_name.items()}).enode()
    last_mapping_sent = 0.0

    max_records_per_frame = max(1, (XBEE_MAX_PAYLOAD - 1) // RECORD_SIZE)
    batch = []
    batch_deadline = None
    def flush():
        nonlocal batch, batch_deadline
        if not batch:
            return
        payload = FRAME_TYPE_DATA + b"".join(batch)
        try:
            device.send_data_64(dest_addr, payload)
        except XBeeException as e:
            print(f"[rf-sender] send failed, dropping batch of {len(batch)}: {e}", file=sys.stderr)
        batch = []
        batch_deadline = None

    while True:
        now = time.monotonic()

        if now - last_mapping_sent >= MAPPING_INTERVAL_S:
            try:
                device.send_data_64(dest_addr, mapping_payload)
            except XBeeException as e:
                print(f"[rf-sender] mapping send failed: {e}", file=sys.stderr)
            last_mapping_sent = now

        timeout = BATCH_FLUSH_INTERVAL_S

        if batch_deadline is not None:
            timeout = max(0.0, min(timeout, batch_deadline - now))

        try:
            item = write_queue.get(timeout=timeout)
        except queue.Empty:
            flush()
            continue
        
        if item is _SENTINEL:
            flush()
            break

        record = item
        if record is not None:
            batch.append(record)
            if batch_deadline is None:
                batch_deadline = time.monotonic() + BATCH_FLUSH_INTERVAL_S
            if len(batch) >= max_records_per_frame:
                flush()


async def receive_loop(subscriber: zmq.asynio.Socket, name_to_id: dict):
    while True:
        topic, timestamp_us, value = await subscriber.recv_multipart()
        signal_name = topic.decode().split(".")[-1]
        signal_id = name_to_id.get(signal_name)
        if signal_id is None:
            continue
        try:
            ts = int(timestamp_us) & 0xFFFFFFFF
            val = float(value)
        except(ValueError, TypeError):
            continue
        write_queue.put(struct.pack(RECORD_FMT, signal_id, ts, val))


def main():
    """open ports and devices, load dbc, safe shutdown function, craete send thread"""
    dbc = cantools.database.load_file(DBC_FILE_PATH)
    name_to_id, id_to_name, units = build_signal_id_map(dbc)

    device = XBeeDevice(XBEE_PORT, XBEE_BAUD)
    device.open()
    dest_addr = XBee64BitAddress.from_hex_string(XBEE_DEST_ADDR)

    def shutdown(sig, frame):
        write_queue.put(_SENTINEL)
        t.join(timeout=2.0)
        device.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    t = threading.Thread(target=xbee_sender_thread, args=(device, dest_addr, id_to_name, units), daemon=True,)
    t.start()

    with zmq.asyncio.Context() as ctx:
        with ctx.socket(zmq.SUB) as subscriber:
            subscriber.connect(f"tcp://{BROKER_HOST}:{BROKER_PORT}")
            subscriber.setsockopt(zmq.SUBSCRIBE, b"")
            try: 
                asyncio.run(receive_loop(subscriber, name_to_id))
            except KeyboardInterrupt:
                shutdown(None, None)

if __name__ == "__main__":
    main()
