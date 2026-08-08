"""
models.py
=========
Data containers for parsed BMS telemetry packets.
"""

from dataclasses import dataclass


@dataclass
class BMSData:
    """
    Complete parsed BMS telemetry packet. 
    """
    
    # Core battery parameters
    voltage: int = 0      # Pack voltage (raw ADC value)
    current: int = 0      # Pack current (signed 32-bit)
    soc: int = 0          # State of charge (0-10000 = 0-100%)
    capacity: int = 0     # Battery capacity (mAh or similar)
    cycles: int = 0       # Charge/discharge cycles
    temperature: int = 0  # Temperature (raw value)
    status: int = 0       # Status/fault flags
    afe_status: int = 0   # AFE chip status
    
    # Raw data for debugging
    raw_payload: str = ""  # The 108-char ASCII hex payload
    
    def __str__(self) -> str:
        return (
            f"Voltage={self.voltage} "
            f"Current={self.current} "
            f"SOC={self.soc / 100:.1f}% "
            f"Temp={self.temperature} "
            f"Status=0x{self.status:02X}"
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "voltage": self.voltage,
            "current": self.current,
            "soc": self.soc,
            "capacity": self.capacity,
            "cycles": self.cycles,
            "temperature": self.temperature,
            "status": self.status,
            "afe_status": self.afe_status,
        }