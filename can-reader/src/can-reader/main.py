import asyncio
import os

import can
import cantools
import zmq

dbc_file_path = os.environ["DBC_PATH"]
critical_can = os.environ["CRITICAL_CAN_INTERFACE"]
noncritical_can = os.environ["NONCRITICAL_CAN_INTERFACE"]


async def process_bus(
    reader: can.AsyncBufferedReader,
    topic_prefix: str,
    publisher: zmq.asyncio.Socket,
    dbc: cantools.db.Database,
) -> None:
    async for msg in reader:
        try:
            decoded = dbc.decode_message(msg.arbitration_id, msg.data)
            timestamp_us = int(msg.timestamp * 1_000_000)
            for signal_name, value in decoded.items():
                topic = f"{topic_prefix}.{signal_name}".encode()
                publisher.send_multipart(
                    [topic, str(timestamp).encode(), str(value).encode()]
                )
        except KeyError:
            pass


async def main() -> None:
    with zmq.asyncio.Context() as ctx:
        with ctx.socket(zmq.PUB) as publisher:

            dbc = cantools.database.load_file(dbc_file_path)
            publisher.connect("tcp://broker:5555")
            loop = asyncio.get_event_loop()

            with (
                can.interface.Bus(
                    channel=critical_can, interface="socketcan"
                ) as critical_bus,
                can.interface.Bus(
                    channel=noncritical_can, interface="socketcan"
                ) as noncritical_bus,
            ):

                critical_reader = can.AsyncBufferedReader()
                noncritical_reader = can.AsyncBufferedReader()

                with (
                    can.Notifier(
                        critical_bus, [critical_reader], loop=loop
                    ) as critical_notifier,
                    can.Notifier(
                        noncritical_bus, [noncritical_reader], loop=loop
                    ) as noncritical_notifier,
                ):

                    await asyncio.gather(
                        asyncio.create_task(
                            process_bus(critical_reader, "critical.can", publisher, dbc)
                        ),
                        asyncio.create_task(
                            process_bus(noncritical_reader, "log.can", publisher, dbc)
                        ),
                    )


if __name__ == "__main__":
    asyncio.run(main())
