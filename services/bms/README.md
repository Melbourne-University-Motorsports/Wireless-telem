# BMS Telemetry

Python script for receiving and logging real-time battery telemetry from the Allion AL1220-BT BMS over Bluetooth Low Energy (BLE). Runs on a Raspberry Pi in the car. Connects to both batteries automatically.

---

## Repository Layout

```
bms_telemetry/          ← repo root
├── bms_telemetry/      ← Python package, deployed to Pi directly and run standalone
│   ├── main.py
│   ├── client.py
│   ├── broadcast_handler.py
│   ├── parser.py
│   ├── models.py
│   ├── constants.py
│   └── requirements.txt
├── bluetoothcheck/     ← dev/debug tools only, NOT deployed to Pi
│   ├── scan.py
│   ├── diagnose.py
│   ├── diagnose2.py
│   ├── crcalgo.py
│   └── hex_to_ascii.py
├── test_bms.py         ← unit tests (run locally, not on Pi)
├── conftest.py
├── Dockerfile
└── docker-compose.yml
```

Dockerfile copies just `bms_telemetry/` (the inner folder) into the image, so tests and `bluetoothcheck/` never end up on the Pi

---

## How It Works

On startup, `main.py` scans for all nearby BLE devices whose name contains `"AL1220BT"` (matches `Red-AL1220BT`, `Blue-AL1220BT`, etc.). One `BMSClient` is created per battery found, then all clients run concurrently via `asyncio.gather`.Each `BMSClient` holds private state

Data flow per battery:

```
BLE notify chunks
  → BroadcastHandler  (buffer bytes, sync on 0xF3 header, assemble 121-byte packets, validate CRC)
  → ProtocolParser    (decode ASCII-hex payload → voltage, current, SOC, temp, cycles, status)
  → BMSData
  → printed to console  (only when BMS_VERBOSE=true)
  → ZMQ PUB socket      (port 5559, one multipart message per signal — always on)
      topic:   lvb1.voltage / lvb2.voltage / lvb1.soc / etc.
      frame 1: topic bytes
      frame 2: timestamp in microseconds
      frame 3: value as string
  → JSONL data file     (only when BMS_JSONL_LOG=true)
```

Each client reconnects automatically on disconnect. The async event loop yields at every BLE wait (scan, connect, disconnect event, reconnect sleep), so both devices stay live simultaneously.

Log files are written to `logs/`, organized by device and type:

```
logs/
  Red-AL1220BT/
    log/
      Red-AL1220BT_20260508_120000.log    ← session 1
      Red-AL1220BT_20260508_130012.log    ← session 2 (after reconnect)
    data/                                ← only created when BMS_JSONL_LOG=true
      Red-AL1220BT_20260508_120000.jsonl
      Red-AL1220BT_20260508_130012.jsonl
    errors/
      Red-AL1220BT_failures.jsonl         ← one file, all failed sessions appended
  Blue-AL1220BT/
    log/
      Blue-AL1220BT_20260508_120000.log
    data/
      Blue-AL1220BT_20260508_120000.jsonl
    errors/
      Blue-AL1220BT_failures.jsonl
```

Each reconnection creates a new timestamped `.log` (and `.jsonl` if enabled). Failures append to the same `_failures.jsonl` file so the full error history is in one place.

**`log/<name>_<timestamp>.log`** — operational events (connection status, errors, warnings):

```
2026-05-08 12:00:00,123 [INFO] Session started — data → logs/Red-AL1220BT/data/Red-AL1220BT_20260508_120000.jsonl
2026-05-08 12:00:00,124 [INFO] Scanning...
2026-05-08 12:00:05,312 [INFO] Connected [4A:41:99:D5:AB:CD]
2026-05-08 12:00:05,812 [INFO] Streaming data...
2026-05-08 12:00:06,001 [INFO] Packet OK → Voltage=13332 Current=0 SOC=9700 ...
2026-05-08 12:01:23,456 [WARNING] Device disconnected.
2026-05-08 12:01:28,789 [INFO] Scanning...
```

**`data/<name>_<timestamp>.jsonl`** — raw battery data, one JSON object per line (requires `BMS_JSONL_LOG=true`):

```json
{"timestamp": "2026-05-08T12:00:06.001", "device": "Red-AL1220BT", "packet_number": 1, "voltage": 13332, "current": 0, "soc": 9700, "capacity": 20000, "cycles": 8, "temperature": 2939, "status": 0, "afe_status": 7}
{"timestamp": "2026-05-08T12:00:07.002", "device": "Red-AL1220BT", "packet_number": 2, "voltage": 13330, "current": -120, "soc": 9698, "capacity": 20000, "cycles": 8, "temperature": 2941, "status": 0, "afe_status": 7}
```

**`errors/<name>_failures.jsonl`** — one record per failed session, appended across restarts:

```json
{
  "timestamp": "2026-05-08T12:01:23.456",
  "device": "Red-AL1220BT",
  "packets_received": 47,
  "error": "ConnectionError: ...",
  "traceback": "Traceback (most recent call last):\n ..."
}
```

`packets_received` tells you how far into the session the failure happened — 0 means it died before connecting, a high number means it crashed mid-stream.

---

## Raspberry Pi Setup (Docker)

`bms_telemetry` runs standalone in its own container, the only integration surface is ZMQ port 5559 (see [CAN Pi Integration (ZMQ Subscriber)](#can-pi-integration-zmq-subscriber)).

- **Standalone** (steps 1–3).
- **As a service in an existing compose file** add a `bms-telemetry` service entry [Adding bms-telemetry to an existing docker-compose.yml](#adding-bms-telemetry-to-an-existing-docker-composeyml).

### 1. Clone and start

```bash
git clone <this-repo-url> bms_telemetry
cd bms_telemetry
docker compose up -d --build
```

### 2. Check it's running

```bash
docker compose logs -f
```

Expected output:

```
2026-05-08 12:00:00 [INFO] Scanning for BMS devices (pattern: 'AL1220BT', timeout: 15.0s)...
2026-05-08 12:00:15 [INFO] Found 2 BMS device(s): ['Red-AL1220BT', 'Blue-AL1220BT']
2026-05-08 12:00:15 [INFO] ZMQ publisher bound to port 5559
2026-05-08 12:00:15 [INFO] Starting telemetry for 2 device(s): ['Red-AL1220BT', 'Blue-AL1220BT']
2026-05-08 12:00:20 [INFO] Connected [4A:41:99:D5:AB:CD]
2026-05-08 12:00:21 [INFO] Packet OK → Voltage=13332 Current=0 SOC=97.0% Temp=2939 Status=0x00
```

Console lines don't say which device they came from, check per-device files under `logs/`. Per-packet `[Red-AL1220BT][0001] ...` console lines only appear when `BMS_VERBOSE=true`.

### Stop / restart

```bash
docker compose down
docker compose up -d
```

### Deploying a code update

```bash
git pull
docker compose up -d --build
```

### Toggling debug output (no rebuild needed)

Uncomment the relevant lines in `docker-compose.yml` and restart:

```yaml
environment:
  - BMS_JSONL_LOG=true # write per-packet .jsonl data files
  - BMS_VERBOSE=true # print every packet to the console
```

### Adding bms-telemetry to an existing docker-compose.yml

**1. Clone this repo next to the existing compose file:**

```bash
cd ~/wherever the main docker-compose.yml
git clone <this-repo-url> bms_telemetry
```

**2. Add this service entry to the existing `docker-compose.yml`:**

```yaml
services:
  bms-telemetry:
    build:
      context: ./bms_telemetry # path to the cloned repo, NOT "."
      target: production
    restart: unless-stopped
    ports:
      - "5559:5559"
    privileged: true # permission to access hardware (Bluetooth)
    volumes:
      - /run/dbus/system_bus_socket:/run/dbus/system_bus_socket
      - ./bms_telemetry/logs:/bms_telemetry/logs
    environment:
      - PYTHONUNBUFFERED=1
      # Uncomment to enable debug outputs:
      # - BMS_JSONL_LOG=true
      # - BMS_VERBOSE=true
```

- `context: .` becomes `context: ./bms_telemetry` so Docker finds the `Dockerfile` inside the cloned repo.
- `./logs:...` becomes `./bms_telemetry/logs:...` — so log files land inside the repo folder as usual, not next to the outer compose file.

**3. Build and start everything:**

```bash
docker compose up -d --build
```

Any other service in the same compose file can now reach the publisher at `tcp://bms-telemetry:5559`

**Updating later:**

```bash
cd ~/xxx/bms_telemetry && git pull
cd ~/xxx && docker compose up -d --build
```

---

## CAN Pi Integration (ZMQ Subscriber)

`bms_telemetry` is **not** imported as a Python package or git submodule by CAN Pi. It runs as its own independent process/container (see [Raspberry Pi Setup (Docker)](#raspberry-pi-setup-docker) above) and publishes every signal over its ZMQ PUB socket on port `5559`.

### 1. Make sure the port is reachable

- connect to `tcp://localhost:5559` if on pi.
- connect to `tcp://<pi-ip-or-hostname>:5559` if diff machine.
- If both run as services in the **same compose file** (see [Adding bms-telemetry to an existing docker-compose.yml](#adding-bms-telemetry-to-an-existing-docker-composeyml)), can connect to `tcp://bms-telemetry:5559`

### 2. Subscribe from CAN Pi

```python
import zmq

ctx = zmq.Context()
sub = ctx.socket(zmq.SUB)
sub.connect("tcp://localhost:5559")   # adjust host per above
sub.setsockopt(zmq.SUBSCRIBE, b"")    # b"" = everything; use e.g. b"lvb1." for one battery only

while True:
    topic, timestamp_us, value = sub.recv_multipart()
    print(topic.decode(), timestamp_us.decode(), value.decode())
```

Each message is 3 frames: topic (bytes), timestamp in microseconds since epoch (ASCII string), value (ASCII string).

Topics published per battery (`lvb1` = first battery found, `lvb2` = second):

```
lvb1.name          lvb2.name
lvb1.voltage       lvb2.voltage
lvb1.current       lvb2.current
lvb1.soc           lvb2.soc
lvb1.capacity      lvb2.capacity
lvb1.cycles        lvb2.cycles
lvb1.temperature   lvb2.temperature
lvb1.status        lvb2.status
lvb1.afe_status    lvb2.afe_status
```

`lvb1.name` / `lvb2.name` carry the actual advertised device name (e.g. `Red-AL1220BT`)

---

## Configuration

All tunable values are in [bms_telemetry/constants.py](bms_telemetry/constants.py):

| Constant               | Default        | Purpose                                        |
| ---------------------- | -------------- | ---------------------------------------------- |
| `DEVICE_NAME_PATTERN`  | `"AL1220BT"`   | Substring matched against advertised BLE names |
| `INITIAL_SCAN_TIMEOUT` | `15.0 s`       | How long to scan on startup                    |
| `SCAN_TIMEOUT`         | `5.0 s`        | How long to scan per reconnect attempt         |
| `RECONNECT_DELAY`      | `5.0 s`        | Wait between reconnect attempts                |
| `UUID_CHAR`            | `0000ffe4-...` | BLE characteristic to subscribe to             |
| `ZMQ_PUB_PORT`         | `5559`         | Port the ZMQ PUB socket binds to               |

**Environment variables** (set in `docker-compose.yml` or export before running manually):

| Variable        | Default | Effect when set to `true`                                                      |
| --------------- | ------- | ------------------------------------------------------------------------------ |
| `BMS_JSONL_LOG` | unset   | Write each packet to `logs/<device>/data/<device>_<timestamp>.jsonl`           |
| `BMS_VERBOSE`   | unset   | Print each received packet to the console (`[Red-AL1220BT][0001] Voltage=...`) |

Errors are always logged to `logs/<device>/errors/<device>_failures.jsonl` regardless of these flags.

---

## bluetoothcheck/ — Debug Tools

Development-only tools for when you're debugging Bluetooth issues. **x deploy to the Pi.**

| Script            | What it does                                      | When to use                         |
| ----------------- | ------------------------------------------------- | ----------------------------------- |
| `scan.py`         | Lists all nearby BLE devices with signal strength | Confirm the Pi/laptop sees the BMS  |
| `diagnose.py`     | Connects and logs raw BLE notification bytes      | Capture raw packets for analysis    |
| `diagnose2.py`    | Like diagnose.py but with fuzzy name matching     | More robust — use this one          |
| `crcalgo.py`      | Tests 3 CRC algorithms against captured samples   | Verify checksum logic               |
| `hex_to_ascii.py` | Decodes and verifies a hardcoded raw hex packet   | Inspect individual packets manually |

Run from the `bluetoothcheck/` directory:

```bash
cd bluetoothcheck
python3 scan.py           # find devices
python3 diagnose2.py      # capture raw packets
```

---

## Tests

Tests cover packet assembly (`BroadcastHandler`), field parsing (`ProtocolParser`), and simulated BLE chunking. No Bluetooth hardware required, bleak is stubbed out.

```bash
# From repo root:
pytest test_bms.py -v
```

---

## Troubleshooting

### "No BMS devices found"

- Run `bluetoothcheck/scan.py` to see what the Pi can see
- Run `bluetoothctl scan on` to verify BlueZ is working
- check constants.py's name pattern

### Container can't access Bluetooth

`bleak` reaches the host's BlueZ daemon via D-Bus, not raw network sockets.

```bash
# Verify BlueZ is running on the Pi
sudo systemctl status bluetooth
```

### Only one battery found at startup

The 15-second initial scan (`INITIAL_SCAN_TIMEOUT`) should catch both batteries. each client's reconnect loop handles disconnects independently.

### View raw packet data

Use `bluetoothcheck/diagnose2.py` — it logs raw bytes before any parsing, useful for protocol debugging.

---

## Dependencies

- Python 3.13+
- [bleak](https://github.com/hbldh/bleak) >= 0.19.0 — BLE communication
- [pyzmq](https://pyzmq.readthedocs.io) >= 25.0.0 — ZMQ publisher
- Raspberry Pi OS with BlueZ (Bluetooth stack)
- Docker (for containerised deployment)
