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

## Standard

-   11-bit CAN IDs
-   Structured CAN ID allocation

## Recommended Structure

``` text
[ Priority | Node ID | Message Index ]
```

### Example Layout

``` text
Bits 10-8 : Priority
Bits 7-4  : Node ID
Bits 3-0  : Message Index
```

## Priority Rules

Lower CAN IDs have higher arbitration priority.

### Suggested Priority Levels

| Priority | Use Case                  |
|----------|---------------------------|
| 0        | Safety-critical shutdowns |
| 1        | Torque commands           |
| 2        | Pedal/brake signals       |
| 3        | BMS and inverter status   |
| 4        | Telemetry                 |
| 5+       | Diagnostics/debug         |

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

# 4. Standard Units

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

# 5. Signal Formatting Rules

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

# 6. Logging Frequency Categories

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

# 7. Fault Handling and Heartbeats

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

# 8. DBC Management Workflow

## Repository Structure

``` text
/dbc
    /vendor
    /team
```

## Vendor DBC Files

Vendor DBCs should:

-   Remain read-only
-   Never be directly modified
-   Be stored separately from team DBCs

## Team DBC Files

Team DBCs contain:

-   Custom signals
-   Remapped IDs
-   Team-specific telemetry

## Storage

All DBC files should be version-controlled in Git until Azure cloud database is created.
