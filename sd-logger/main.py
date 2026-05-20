import asyncio
import os
import queue
import signal
import sys
import threading

import numpy as np
import zmq
from asammdf import MDF, Signal

dbc_file_path = os.environ["DBC_PATH"]
log_dir = os.environ["LOG_DIR"]

write_queue = queue.Queue()


def mdf_writer_thread(mdf: MDF, units: dict[str, str]):
    """Dedicated thread to write queue to MDF4"""
    while True:
        item = write_queue.get()
        if item is None:
            break
        topic, timestamp_us, value = item
        signal_name = topic.decode().split(".")[-1]
        unit = units.get(signal_name, "")
        mdf.append(
            Signal(
                samples=np.array([float(value)]),
                timestamps=np.array([int(timestamp_us) / 1_000_000]),
                name=signal_name,
                unit=unit,
            )
        )


async def receive_loop(subscriber):
    while True:
        topic, timestamp_us, value = await subscriber.recv_multipart()
        write_queue.put((topic, timestamp_us, value))


def shutdown(sig, frame):
    write_queue.put(None)  # Stop writer thread
    mdf.save(dst=log_dir, overwrite=True)
    sys.exit(0)


def main():
    dbc = cantools.database.load_file(dbc_file_path)
    units = {
        sig.name: sig.unit
        for msg in dbc.messages
        for sig in msg.signal_name
        if sig.unit
    }

    with MDF(version="4.10") as mdf4:

        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)

        t = threading.Thread(target=writer_thread, args=(mdf, units), daemon=True)
        t.start()

        with zmq.asyncio.Context() as ctx:
            with ctx.socket(zmq.SUB) as subscriber:

                subscriber.connect("tcp://broker:5560")
                subscriber.setsockopt(zmq.SUBSCRIBE, b"")
                asyncio.run(receive_loop(subscriber))


if __name__ == "__main__":
    main()
