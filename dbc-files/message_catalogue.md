# MUR CAN Message Catalogue

**Generated directly from `dbc/team/control_can.dbc` and `dbc/team/telemetry_can.dbc` (v1.0).**
Vendor DBCs (`dbc/vendor/Orion_BMS.dbc`, `dbc/vendor/PM100DZ.dbc`) are unedited and are not reproduced here — load them alongside the team DBCs in SavvyCAN/cantools for the full picture of each bus.

If you edit the DBCs, regenerate this file rather than hand-editing it, so it never drifts from source.

---

## Control CAN (500 kbps)

| CAN ID | Message | Producer | Rate | Signals | Notes |
|---|---|---|---|---|---|
| 0x100 | Pedal_Status | PEDALBOX | 250 Hz | PEDAL_Position1, PEDAL_Position2, PEDAL_BrakePressure1, PEDAL_BrakePressure2 | Primary + redundant pedal/brake sensors, single packed message per can_standard.md §4 |
| 0x101 | Pedal_Diagnostics | PEDALBOX | 10 Hz | PEDAL_BSEStatus, PEDAL_HeartbeatCounter | BSEStatus bit meanings TBD |
| 0x110 | TTCS_Status | TTCS | 10 Hz | TTCS_SDCStatus1, TTCS_SDCStatus2, TTCS_IMDState, TTCS_HeartbeatCounter | SDC polarity assumption - confirm |
| 0x111 | TTCS_Diagnostics | TTCS | 10 Hz | TTCS_IMDVoltage, TTCS_HVCellTemp1, TTCS_HVCellTemp2, TTCS_HVCellTemp3 | Cell temps only populated while Orion BMS 2 is fitted |
| 0x120 | ECU_Control | ECU | 200 Hz | ECU_TorqueRequest, ECU_TorqueLimit, ECU_DriveMode, ECU_HeartbeatCounter | Internal torque arbitration message - distinct from PM100DZ vendor M192_Command_Message (0xC0) |
| 0x121 | ECU_Cooling | ECU | 20 Hz | ECU_RadiatorTempIn, ECU_RadiatorTempOut, ECU_RadiatorPressureIn, ECU_RadiatorPressureOut | |
| 0x122 | ECU_Status | ECU | 10 Hz | ECU_FaultFlags, ECU_ECUState, ECU_HeartbeatCounter | 32-bit FaultFlags bit map TBD |
| 0x130-0x13F | *(reserved)* | — | — | — | Reserved for future ENNOID BMS. No DBC/signals defined yet (no firmware exists) — do not allocate. Orion BMS 2 (current hardware) transmits on its own vendor IDs (0x10, 0x20, 0x30, 0x36, 0x40, 0x618), outside this block |
| 0x140 | Telemetry_Heartbeat | TELEMETRY | 10 Hz | TELEM_NodeHealthBitfield, TELEM_CPULoad, TELEM_HeartbeatCounter | Node bit order assumption - confirm |
| 0x141 | Watchdog_Status | TELEMETRY | EVENT | TELEM_LostNodesBitfield, TELEM_TimeoutFlags, TELEM_SystemState | Transmitted only on state change |

Vendor traffic also present on this bus (unchanged, see `dbc/vendor/PM100DZ.dbc`): Cascadia PM100DZ messages 0xA0-0xB0, 0xC0-0xC2, 0x1D5, 0x1D7, 0x202 (`BMS_Current_Limit`, sent by BMS to inverter). None of these overlap the team ID blocks above.

---

## Telemetry CAN (1 Mbps)

| CAN ID | Message | Producer | Rate | Signals | Notes |
|---|---|---|---|---|---|
| 0x200 | Dashboard_Dynamics | DASH | 100 Hz | DASH_SteeringAngle, DASH_ShockPotFrontLeft, DASH_ShockPotFrontRight, DASH_HeartbeatCounter | |
| 0x201 | Dashboard_Inputs | DASH | 20 Hz | DASH_ButtonStates, DASH_RotarySwitch | Button map TBD, to be locked down with driver interface design |
| 0x202 | Dashboard_Environment | DASH | 10 Hz | DASH_WindSpeed | |
| 0x210 | PDU_Status | PDU | 10 Hz | PDU_PumpState, PDU_FanState, PDU_HeartbeatCounter | Byte 2 reserved for future PDU_FanSpeed (speed control not yet implemented). No PDU command messages - commands originate from ECU if implemented |
| 0x220-0x22F | *(reserved)* | — | — | — | Reserved for 2x SBG Eclipse-N. Vendor DBC required (not yet supplied); one unit must be remapped off its factory IDs since both share this bus. No team signals defined here to avoid misrepresenting the vendor protocol |
| 0x230 | Telemetry_System | TELEMETRY | 5 Hz | TELEM_SystemCPULoad, TELEM_SystemMemoryUsage, TELEM_SystemDiskUsage, TELEM_PiTemperature | |
| 0x231 | Telemetry_LVBattery | TELEMETRY | 2 Hz | TELEM_LVBatteryVoltage, TELEM_LVBatteryCurrent | |

Note: `0x202` is used on **both** buses (`Dashboard_Environment` here vs. PM100DZ's `BMS_Current_Limit` on Control CAN). This is not a conflict — they are physically separate CAN networks — but flag it if the two buses are ever merged into a single trace/channel for analysis, since arbitration IDs are only unique per-bus.

---

## Validation Status

Both `control_can.dbc` and `telemetry_can.dbc`:
- ✅ Load cleanly in `cantools` (`cantools.database.load_file`)
- ✅ No duplicate CAN IDs within a bus
- ✅ No overlapping signal bits within any message
- ✅ All messages ≤ 8 bytes
- ✅ `GenMsgCycleTime` set per design brief rates
- ✅ `GenMsgSendType` set (Cyclic / OnChange / Event) for watchdog and status messages
- ✅ Value tables (`VAL_`) present for all enum-type signals
- ⏳ Not yet visually re-confirmed in SavvyCAN GUI — recommend a quick load-test before merging, since SavvyCAN and cantools occasionally diverge on edge-case syntax

## Open Items Requiring Team Input

These were implemented with a clearly-marked placeholder so the files are usable now, but should be confirmed/updated before final release:

1. **Enum values** for `TTCS_IMDState`, `ECU_DriveMode`, `ECU_ECUState`, `TELEM_SystemState` — placeholders based on typical FSAE conventions (Bender IMD states, Eco/Normal/Attack drive modes, standard RTD state machine). Update `VAL_` tables once firmware finalizes these.
2. **Bitfield definitions** for `PEDAL_BSEStatus`, `ECU_FaultFlags`, `TELEM_NodeHealthBitfield`, `TELEM_LostNodesBitfield`, `TELEM_TimeoutFlags`, `DASH_ButtonStates` — bytes/bits are reserved and sized generously, but individual bit meanings need firmware sign-off.
3. **SDC polarity** on `TTCS_SDCStatus1/2` (0=open vs 0=closed) — confirm with TTCS hardware.
4. **SBG Eclipse-N vendor DBC** — not supplied; ID block reserved (0x220-0x22F) but no signals modeled. Send the vendor DBC once available and confirm which unit gets remapped.
5. **ENNOID BMS** — per design brief, intentionally left as a reserved ID block only (0x130-0x13F), no signals, since no firmware/DBC exists yet.
