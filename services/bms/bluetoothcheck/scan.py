"""
Simple Bluetooth Scanner - Find nearby devices ONCE
Run with: python scan_once.py
"""

import asyncio
from datetime import datetime
from pathlib import Path
from bleak import BleakScanner


# Configuration
SCAN_TIMEOUT = 10  # seconds
LOG_DIR = Path("logs")

async def main():
    # Create log file with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"bluetooth_scan_{timestamp}.txt"
    Path("logs").mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("🔍 Bluetooth Scanner (One-Time Scan)")
    print("=" * 60)
    print()
    print(f"Scanning for {SCAN_TIMEOUT} seconds...")
    print()
    
    # Scan for devices
    devices = await BleakScanner.discover(timeout=SCAN_TIMEOUT, return_adv=True)
    
    # Write results to file
    with open(log_file, 'w') as f:
        f.write(f"Bluetooth Scan Results\n")
        f.write(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Scan Duration: {SCAN_TIMEOUT} seconds\n")
        f.write("=" * 60 + "\n\n")
        
        if not devices:
            print("❌ No devices found.")
            f.write("No devices found.\n")
            return
        
        print(f"✅ Found {len(devices)} device(s):\n")
        f.write(f"Found {len(devices)} device(s):\n\n")
        
        # Sort by signal strength (strongest first)
        sorted_devices = sorted(
            devices.items(),
            key=lambda item: item[1][1].rssi if item[1][1].rssi else -100,
            reverse=True
        )
        
        for i, (address, (device, adv_data)) in enumerate(sorted_devices, 1):
            name = device.name or "(No Name)"
            rssi = adv_data.rssi if adv_data.rssi else "N/A"
            
            # Signal strength bar
            if isinstance(rssi, int):
                bars = max(1, min(20, int((rssi + 100) / 5)))
                signal_bar = "█" * bars + "░" * (20 - bars)
            else:
                signal_bar = "Unknown"
            
            # Print to screen
            print(f"{i:2}. {name}")
            print(f"    Address: {address}")
            print(f"    Signal:  {rssi} dBm  {signal_bar[:10]}")
            print()
            
            # Write to file
            f.write(f"{i}. {name}\n")
            f.write(f"   Address: {address}\n")
            f.write(f"   Signal:  {rssi} dBm\n")
            
            if adv_data.service_uuids:
                f.write(f"   Services: {adv_data.service_uuids}\n")
            
            f.write("\n")
    
    print("-" * 60)
    print(f"📁 Results saved to: {log_file}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n Scan interrupted by user.")