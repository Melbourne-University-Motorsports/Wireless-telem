# CAN Communication Standard

## Purpose

This document defines the communication standards, conventions, and governance rules for the university racing team's CAN architecture.

The goals of this standard are to:

-   Maintain a scalable and organised CAN system
-   Ensure message consistency across all nodes
-   Standardise signal naming and units
-   Define logging and telemetry conventions
-   Simplify debugging and future development

------------------------------------------------------------------------

# 1. CAN Bus Architecture

## Control CAN

The Control CAN contains all critical drivetrain and safety-related communication.

### Connected Nodes

-   Pedalbox Sensor Node
-   TTCS Sensor Node
-   Orion BMS 2 / ENNOID BMS
-   Cascadia Motion PM100DZ Inverter
-   ECU
-   Telemetry Unit (Raspberry Pi)

### Baud Rate

500 kbps

### Allowed Traffic

-   Torque requests
-   Pedal positions
-   Brake pressures
-   BMS status
-   Inverter status
-   Safety-critical faults
-   Heartbeat messages

### Restricted Traffic

The following should NOT be placed on Control CAN unless necessary:

-   High-volume telemetry
-   Dashboard UI data
-   Debug information
-   Non-critical logging

------------------------------------------------------------------------

## Telemetry CAN

The Telemetry CAN contains non-critical telemetry, logging, dashboard, and driver interface data.

### Connected Nodes

-   Dashboard Sensor Node
-   Power Distribution Unit
-   2x SBG Eclipse-N
-   ECU
-   Telemetry Unit (Raspberry Pi)

### Baud Rate

1 Mbps

### Allowed Traffic

-   Dashboard data
-   Shock potentiometers
-   Steering angle
-   Wind speed
-   Logging-only signals
-   Telemetry system data
-   Driver interface data

------------------------------------------------------------------------

# 2. CAN ID Structure
## CAN ID Allocation

The team uses standard 11-bit CAN identifiers.

CAN IDs are allocated in sequential ranges based on the originating node. This simplifies debugging, DBC management, future expansion and CAN trace analysis.

Lower numerical CAN IDs retain higher arbitration priority as defined by the CAN protocol.

### Team CAN ID Allocation

| Node | CAN ID Range |
|------|--------------|
| Pedalbox Sensor Node | 0x100 - 0x10F |
| TTCS Sensor Node | 0x110 - 0x11F |
| ECU | 0x120 - 0x12F |
| BMS | 0x130 - 0x13F |
| Telemetry Unit (Raspberry Pi) | 0x140 - 0x14F |
| Dashboard Sensor Node | 0x200 - 0x20F |
| Power Distribution Unit | 0x210 - 0x21F |

### Vendor Devices

Vendor devices (such as the Cascadia Motion PM100DZ inverter) retain their manufacturer-defined CAN identifiers.

------------------------------------------------------------------------

# 3. Signal Naming Convention

## Standard Format

``` text
Node_SignalName
```

## Examples

``` text
ECU_TorqueRequest
BMS_PackVoltage
INV_MotorTemp
DASH_SteeringAngle
PEDAL_BrakePressureFront
```

## Naming Rules

-   Use PascalCase for signal names
-   Avoid abbreviations where possible
-   Names should clearly describe the signal purpose
-   Prefix signals with owning node

------------------------------------------------------------------------

# 4. Message Packing

Signals would be grouped into logical CAN messages where possible.

Example:

Pedal_Status

- Pedal Position 1
- Pedal Position 2
- Brake Pressure 1
- Brake Pressure 2

should be transmitted as a single CAN message rather than four separate messages.

------------------------------------------------------------------------

# 5. Standard Units

| Quantity    | Standard Unit |
|-------------|---------------|
| Temperature | degC          |
| Pressure    | psi           |
| Voltage     | V             |
| Current     | A             |
| Speed       | rpm           |
| Angle       | deg           |
| Distance    | mm            |
| Time        | ms            |
| Frequency   | Hz            |

------------------------------------------------------------------------

# 6. Signal Formatting Rules

## Signedness

-   Use unsigned values unless negative values are physically possible

## Scaling

Scaling should be explicitly defined in the DBC.

### Recommended Examples

| Signal Type | Suggested Resolution |
|-------------|----------------------|
| Temperature | 0.1 degC             |
| Voltage     | 0.01 V               |
| Pressure    | 0.1 psi              |
| Angle       | 0.1 deg              |
| Current     | 0.1 A                |

------------------------------------------------------------------------

# 7. Logging Frequency Categories

## FAST (100-250 Hz)

Used for real-time dynamics and control signals.

Examples:

-   Pedal positions
-   Brake pressures
-   Torque requests
-   Steering angle
-   Shock potentiometers

------------------------------------------------------------------------

## MEDIUM (10-50 Hz)

Used for moderately changing system data.

Examples:

-   Motor temperatures
-   Inverter temperatures
-   Pack current
-   Cooling system data

------------------------------------------------------------------------

## SLOW (1-10 Hz)

Used for slow-changing monitoring signals.

Examples:

-   LV battery voltage
-   Dashboard states
-   Fan and pump states

------------------------------------------------------------------------

## EVENT-Based

Only transmitted when state changes occur.

Examples:

-   Fault states
-   Shutdown triggers
-   Heartbeat failures
-   Watchdog alerts

------------------------------------------------------------------------

# Vendor CAN Messages

Some off-the-shelf components broadcast CAN messages at manufacturer-defined polling rates.

These rates should be treated as authoritative unless configurable through vendor software.

Examples include:

- Cascadia Motion PM100DZ
- Orion BMS (current vehicle)

When replacing vendor hardware, a new DBC file should be created describing the team's CAN implementation.

------------------------------------------------------------------------

# 8. Fault Handling and Heartbeats

## Fault Encoding

Faults should use bitfield fault bytes where possible.

## Heartbeat Policy

Critical nodes should periodically transmit heartbeat messages.

### Recommended Heartbeat Rate

100-500 ms

## Failure Behaviour

If heartbeat messages stop:

-   Node should revert to safe state
-   Fault should be logged
-   Telemetry system should broadcast watchdog error message

------------------------------------------------------------------------

# 9. DBC Management Workflow

## Repository Structure

``` text
dbc/
    vendor/
        PM100DZ.dbc
        Orion_BMS.dbc

    team/
        control_can.dbc
        telemetry_can.dbc
        ENNOID_BMS.dbc
```

# 10. Team DBC file contents

## control_can.dbc 
Pedal_Status
Pedal_Status2

TTCS_Status
TTCS_IMD

ECU_Control
ECU_Cooling
ECU_Faults

Telemetry_Heartbeat

ENNOID messages (consumed)

## telemetry_can.dbc
Dashboard_Status

Dashboard_Suspension

Dashboard_Wind

PDU_Status

Telemetry_Status

Telemetry_LVBattery

Telemetry_Heartbeat

SBG_Remapped (placeholder)

Future messages

## ENNOID_BMS.dbc
BMS_Status

BMS_Cells

BMS_Temperatures

BMS_Faults

BMS_Heartbeat
