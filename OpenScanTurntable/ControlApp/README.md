# Arduino Nano + CNC Shield v4 (Keyes) Troubleshooting Guide

This guide documents the critical hardware and software fixes required to make the Arduino Nano and CNC Shield v4 (clone) work correctly. This combination is notorious for design flaws that prevent it from working with standard GRBL settings out of the box.

## ⚠️ Critical Hardware Fixes

### 1. Pin Mapping (GRBL v1.1 Compatibility)

The CNC Shield v4 has a mismatched pinout compared to the default GRBL `cpu_map.h`.

**The Issue:** The Step and Direction pins are swapped on the PCB traces.

**The Fix:** You must modify the `cpu_map.h` file in your GRBL library before uploading the firmware to the Nano:

- **Step Pins:** Set X to 5, Y to 6, Z to 7.
- **Direction Pins:** Set X to 2, Y to 3, Z to 4.

```c
// Define step pulse output pins. NOTE: All step bit pins must be on the same port.
#define STEP_DDR        DDRD
#define STEP_PORT       PORTD
#define X_STEP_BIT      5  // Uno Digital Pin 2
#define Y_STEP_BIT      6  // Uno Digital Pin 3
#define Z_STEP_BIT      7  // Uno Digital Pin 4
#define STEP_MASK       ((1<<X_STEP_BIT)|(1<<Y_STEP_BIT)|(1<<Z_STEP_BIT)) // All step bits

// Define step direction output pins. NOTE: All direction pins must be on the same port.
#define DIRECTION_DDR     DDRD
#define DIRECTION_PORT    PORTD
#define X_DIRECTION_BIT   2  // Uno Digital Pin 5
#define Y_DIRECTION_BIT   3  // Uno Digital Pin 6
#define Z_DIRECTION_BIT   4  // Uno Digital Pin 7
#define DIRECTION_MASK    ((1<<X_DIRECTION_BIT)|(1<<Y_DIRECTION_BIT)|(1<<Z_DIRECTION_BIT)) // All direction bits
```

### 2. Motor Wiring & Phase Verification

If a motor vibrates loudly, grinds, or stalls, the internal coils (phases) are likely not paired correctly at the 4-pin connector.

**Check Motor Specifications:**
- Always consult the datasheet for your specific motor model. Do not rely on wire colors, as they vary by manufacturer.
- Identify Phase A and Phase B (e.g., A = Black/Green, B = Red/Blue).
- Use a multimeter to check continuity. A pair of wires belonging to the same phase will show low resistance.

**The Fix:** Ensure the phases are paired on the shield header in an AABB sequence.

**Swapping Pins:** Use a precision screwdriver to lift the plastic tabs on the connector housing and rearrange the pins so that the two wires of the same phase are sitting next to each other.

### 3. Directional Issues (One-Way Movement)

If an axis moves in only one direction regardless of the command:

**The Issue:** The DIR signal is not reaching the driver (often due to poor manufacturing).

**The Fix:**
1. Swap the A4988 driver with a known working one to rule out a blown chip.
2. Inspect the underside of the shield for "cold" or missing solder joints on the header pins and reflow them with a soldering iron.

## ⚙️ Essential GRBL Settings ($$)

For a 2-axis turntable (especially with a gravity-fed tilt axis), these settings are mandatory:

| Setting | Value | Description |
|---------|-------|-------------|
| `$1` | `255` | Holding Torque: Keeps motors energized when idle. Prevents the turntable from falling under its own weight. |
| `$100` | `80.00` | X-axis steps/mm (or degree). |
| `$101` | `80.00` | Y-axis steps/mm (or degree). |
| `$110/111` | `500.00` | Max Rate. Lower this if the motor "screams" or stalls. |
| `$120/121` | `10.00` | Acceleration. Start low to handle the inertia of the turntable. |

## 🛠 Hardware Safety & Setup

**Driver Orientation:** Ensure the potentiometer on the A4988 driver faces away from the Nano (check the "EN" pin alignment on the board).

**Vref Tuning:** Adjust the driver potentiometer to set the current. If the motor is too weak to hold the table (even with `$1=255`), slightly increase the Vref voltage.

**Cooling:** Because `$1=255` keeps the motors powered at all times, the drivers will generate significant heat. Active cooling (a fan) is required to prevent thermal shutdown.

**Power:** ⚠️ **NEVER** plug or unplug a motor while the board is powered. This will instantly destroy the stepper driver.
