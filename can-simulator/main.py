import asyncio
import os
import random

import can
import cantools

dbc_file_path = os.environ["DBC_PATH"]
critical_can = os.environ["CRITICAL_CAN_INTERFACE"]
noncritical_can = os.environ["NONCRITICAL_CAN_INTERFACE"]

SKIP_FRAME_IDS = {3221225472}  # VECTOR__INDEPENDENT_SIG_MSG — not a real message


async def simulate_bus(
    bus: can.interface.Bus,
    messages: list[cantools.db.Message],
) -> None:
    while True:
        for msg in messages:
            data = {}
            for signal in msg.signals:
                low = float(signal.minimum) if signal.minimum is not None else 0.0
                high = float(signal.maximum) if signal.maximum is not None else 1.0
                data[signal.name] = random.uniform(low, high)

            try:
                encoded = msg.encode(data)
                frame = can.Message(
                    arbitration_id=msg.frame_id,
                    data=encoded,
                    is_extended_id=False,
                )
                bus.send(frame)
            except Exception:
                pass  # skip unencodable messages (e.g. multiplexed)

            interval = (msg.cycle_time / 1000) if msg.cycle_time else 0.1
            await asyncio.sleep(interval)


async def main() -> None:
    dbc = cantools.database.load_file(dbc_file_path)
    messages = [m for m in dbc.messages if m.frame_id not in SKIP_FRAME_IDS]

    # split messages across the two buses to simulate real two-line setup
    critical_messages = messages[: len(messages) // 2]
    noncritical_messages = messages[len(messages) // 2 :]

    with (
        can.interface.Bus(channel=critical_can, interface="socketcan") as critical_bus,
        can.interface.Bus(
            channel=noncritical_can, interface="socketcan"
        ) as noncritical_bus,
    ):
        await asyncio.gather(
            asyncio.create_task(simulate_bus(critical_bus, critical_messages)),
            asyncio.create_task(simulate_bus(noncritical_bus, noncritical_messages)),
        )


if __name__ == "__main__":
    asyncio.run(main())
