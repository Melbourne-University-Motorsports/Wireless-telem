# WaveShare 2-CH CAN HAT

## Enable CAN Overlays

Found in `/boot/firmware/config.txt`
```dtparam=spi=on
dtoverlay=i2c0
dtoverlay=spi1-3cs
dtoverlay=mcp2515,spi1-1,oscillator=16000000,interrupt=22
dtoverlay=mcp2515,spi1-2,oscillator=16000000,interrupt=13```

## Create

Found in `/etc/systemd/network/80-can0.network`
```[Match]
Name=can0

[CAN]
BitRate=1000000
RestartSec=100ms
ListenOnly=yes```
Found in `/etc/systemd/network/80-can1.network`
```[Match]
Name=can0

[CAN]
BitRate=1000000
RestartSec=100ms
ListenOnly=no```
## Enable and Restart networkd
```sudo systemctl enable systemd-networkd
sudo systemctl restart systemd-networkd```

## Verify
```ip -details link show can0
candump can0```

in a new terminal
`cansend can1 000#11.22.33.44`

You should see messages that look like:
`can1 000 [4] 11 22 33 44`

can1 has been temporarily set up to be able to write for testing
