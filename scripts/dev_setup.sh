orb ip link show vcan0 2>/dev/null || (orb sudo ip link add dev vcan0 type vcan && orb sudo ip link set up vcan0)
