# Wireless Telemetry

Runs on Raspberry Pi 5.

## 5 Containerized Processes:
- CAN Reading
- RF Sending
- SD Logging
- BMS Reading
- Broker

```mermaid
flowchart LR
    %% Define Node Styles
    classDef pub fill:#e1f5fe,stroke:#01579b,stroke-width:2px,color:black;
    classDef sub fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px,color:black;
    classDef broker fill:#f3e5f5,stroke:#4a148c,stroke-width:2px,color:black,stroke-dasharray: 5 5;

    %% Docker Container Scope
    subgraph DockerScope ["Raspberry Pi - Docker Network (ZMQ via TCP)"]
        
        %% Core Modules
        CAN_RD[<b>CAN Reader</b><br/>Publisher]:::pub
        BMS_RD[<b>BMS Reader</b><br/>Publisher]:::pub

        %% Central Broker
        ZMQ_BRK[<b>ZMQ Proxy/Broker</b><br/>]:::broker

        %% Sinks
        RF_SND[<b>RF Sender</b><br/>Subscriber]:::sub
        SD_LOG[<b>SD Logging</b><br/>Subscriber]:::sub

        %% Data Flow
        CAN_RD -->|PUB connects to frontend| ZMQ_BRK
        BMS_RD -->|PUB connects to frontend| ZMQ_BRK
        
        ZMQ_BRK -->|SUB connects to backend| RF_SND
        ZMQ_BRK -->|SUB connects to backend| SD_LOG

    end
```

Orchestrated with Docker Compose.
Communicating with TCP, ZeroMQ Pub/Sub Protocol broker.

## Remote Development:
If on Unix system (MacOS / Linux) I recommend using plain `rsync` for quick iterations. And then `git pull` for finalised versions of code / closing out of pi.
- Remember to keep the pi up to date with git repo. If testing new code on the pi unless it is pushed to git hub, finish your coding session with a clean `git pull` on the pi.

`cd Wireless-telem`
Then run rsync command:
`rsync -avz --exclude-from='.gitignore' --exclude='.git' . mur@mur-wireless-telemetry:~/Wireless-telem`


## Developent without a Raspi 
Use orbstack as a linux vm. build with `docker compose --profile dev build --no-cache` run with `docker compose --profile dev up`. enable vcan0 with:
```bash
docker run --rm \
    --network host \
    --privileged \
    alpine sh -c '
      apk add --no-cache iproute2 &&
      modprobe vcan || true &&
      ip link add dev vcan0 type vcan &&
      ip link set up vcan0
    '```
