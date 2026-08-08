Subscribes to the telemetry broker over ZMQ and forwards signal updates to base-station XBee-PRO 900HP over DigiMesh.

Asyncio ZMQ receive loop feeds thread-safe queue, and dedicated worker thread drains and does I/O blocking for serial writes to XBee module.

# Wire Format

RF Bandwidth is limiting resource, signals are packed as compact binary records rather than strings
record = <uint8 id><uint32 timestamp_us><float32 value> (9 bytes)

Records are batched into XBee payload.

For the receiver to know what the signals mean, id->(signal name, unit) mappings are defined by DBC file and are periodically broadcast as small JSON "maping" frame so a receiver that joins late can decode the stream.

# Frame layout

0x01 mapping frame: JSON payload, {"<id>": ["<name>", "<unit>"], ...}
0x02 data frame: repeated <uint8 id><uint32 timestamp_us><float32 value>
