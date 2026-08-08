# main.py
import asyncio
import logging
import os
import zmq
import zmq.asyncio
from client import BMSClient, scan_for_bms_devices
from constants import RECONNECT_DELAY, ZMQ_PUB_PORT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


async def main():
    # Keep scanning until at least one BMS device is found.
    while True:
        devices = await scan_for_bms_devices()
        if devices:
            break
        logging.warning(f"No BMS devices found, retrying in {RECONNECT_DELAY:.0f}s...")
        await asyncio.sleep(RECONNECT_DELAY)

    zmq_ctx = zmq.asyncio.Context()
    publisher = zmq_ctx.socket(zmq.PUB)
    publisher.bind(f"tcp://*:{ZMQ_PUB_PORT}")
    logging.info(f"ZMQ publisher bound to port {ZMQ_PUB_PORT}")

    jsonl   = os.getenv("BMS_JSONL_LOG",   "").lower() in ("1", "true", "yes")
    verbose = os.getenv("BMS_VERBOSE",     "").lower() in ("1", "true", "yes")
    clients = [
        BMSClient(device_name=d.name, topic_prefix=f"lvb{i}", publisher=publisher, jsonl=jsonl, verbose=verbose)
        for i, d in enumerate(devices, 1)
    ]
    logging.info(f"Starting telemetry for {len(clients)} device(s): {[d.name for d in devices]}")

    try:
        # Run all clients concurrently — each handles its own reconnection loop.
        await asyncio.gather(*[c.run() for c in clients])
    finally:
        publisher.close()
        zmq_ctx.term()


asyncio.run(main())
