"""conftest.py – pytest session-level setup. Runs before any test is collected."""
import sys, types

def _stub_bleak():
    bleak = types.ModuleType("bleak")
    bleak.BleakClient  = object
    bleak.BleakScanner = object
    sys.modules["bleak"] = bleak

    backends = types.ModuleType("bleak.backends")
    sys.modules["bleak.backends"] = backends

    dev = types.ModuleType("bleak.backends.device")
    dev.BLEDevice = object
    sys.modules["bleak.backends.device"] = dev

_stub_bleak()