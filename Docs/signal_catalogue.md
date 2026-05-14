# Signal Catalog

## Purpose

This document tracks all CAN signals used across the vehicle.

Each signal entry should define:

-   Signal name
-   Owning node
-   CAN bus
-   Logging frequency
-   Units
-   Scaling
-   Consumers
-   Notes

------------------------------------------------------------------------

# Control CAN Signals

| Signal Name | Node | Frequency Category | Suggested Rate | Units | Notes |
|----|----|----|----|----|----|
| PEDAL_Position1 | Pedalbox | FAST | 250 Hz | \% | Primary accelerator position |
| PEDAL_Position2 | Pedalbox | FAST | 250 Hz | \% | Redundant accelerator position |
| PEDAL_BrakePressure1 | Pedalbox | FAST | 250 Hz | psi | Brake pressure sensor 1 |
| PEDAL_BrakePressure2 | Pedalbox | FAST | 250 Hz | psi | Brake pressure sensor 2 |
| PEDAL_BSEStatus | Pedalbox | EVENT | On Change | bitfield | Brake system plausibility |
| TTCS_SDCStatus1 | TTCS | EVENT | On Change | binary | Shutdown circuit state |
| TTCS_SDCStatus2 | TTCS | EVENT | On Change | binary | Shutdown circuit state |
| TTCS_IMDState | TTCS | EVENT | On Change | enum | IMD operating state |
| TTCS_IMDVoltage | TTCS | MEDIUM | 10 Hz | V | IMD measured voltage |
| BMS_PackVoltage | BMS | MEDIUM | 10-50 Hz | V | Total pack voltage |
| BMS_PackCurrent | BMS | MEDIUM | 50 Hz | A | Total pack current |
| INV_FaultBytes | Inverter | EVENT | On Change | bitfield | Inverter fault states |
| INV_MotorTemp | Inverter | MEDIUM | 10-50 Hz | degC | Motor temperature |
| INV_InverterTemp | Inverter | MEDIUM | 10-50 Hz | degC | Inverter temperature |
| ECU_TorqueRequest | ECU | FAST | 250 Hz | Nm | Requested motor torque |
| ECU_FaultBytes | ECU | EVENT | On Change | bitfield | ECU fault states |
| ECU_RadiatorPressureIn | ECU | MEDIUM | 10-50 Hz | psi | Cooling loop pressure |
| ECU_RadiatorPressureOut | ECU | MEDIUM | 10-50 Hz | psi | Cooling loop pressure |
| ECU_RadiatorTempIn | ECU | MEDIUM | 10-50 Hz | degC | Cooling loop temperature |
| ECU_RadiatorTempOut | ECU | MEDIUM | 10-50 Hz | degC | Cooling loop temperature |

------------------------------------------------------------------------

# Telemetry CAN Signals

| Signal Name | Node | Frequency Category | Suggested Rate | Units | Notes |
|----|----|----|----|----|----|
| DASH_SteeringAngle | Dashboard Node | FAST | 100-250 Hz | deg | Steering wheel angle |
| DASH_ShockPotFront | Dashboard Node | FAST | 100-250 Hz | mm | Front suspension displacement |
| DASH_WindSpeed | Dashboard Node | MEDIUM | 10-20 Hz | m/s | Wind speed data |
| DASH_ButtonStates | Dashboard Node | SLOW | 5-10 Hz | bitfield | Driver controls |
| PDU_PumpState | PDU | SLOW | 1-5 Hz | binary | Radiator pump state |
| PDU_FanState | PDU | SLOW | 1-5 Hz | binary | Radiator fan state |
| SBG_Position | SBG Eclipse-N | MEDIUM | 10-50 Hz | deg | GPS/INS position |
| SBG_Acceleration | SBG Eclipse-N | FAST | 100 Hz | m/s\^2 | Vehicle acceleration |
| TELEM_LVBatteryVoltage | Telemetry Unit | SLOW | 1-5 Hz | V | LV battery voltage |
| TELEM_LVBatteryCurrent | Telemetry Unit | SLOW | 1-5 Hz | A | LV battery current |

------------------------------------------------------------------------

# Event-Based Signals

| Signal Name       | Trigger           |
|-------------------|-------------------|
| IMD Faults        | State change      |
| BMS Faults        | Fault trigger     |
| ECU Faults        | Fault trigger     |
| Watchdog Failures | Heartbeat timeout |
| Shutdown Triggers | State change      |
