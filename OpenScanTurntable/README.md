# OpenScanTurntable

A modular 3D scanning turntable system based on the [OpenScan Classic](https://openscan-org.github.io/OpenScan-Doc/hardware/OpenScanClassic/) design. This project provides software tools and automation scripts for controlling a 2-axis turntable used in structured light scanning (SLS). The system includes full integration with FlexScan3D through a turntable plugin and automated scanning and calibration scripts.

## Overview

The OpenScan Classic turntable enables scanning objects up to ~16 cm. The system uses a fully 3D-printable frame with off-the-shelf components, making it accessible and repairable.

For detailed hardware assembly instructions, BOM, and 3D printing files, refer to the official [OpenScan Classic building guide](https://openscan-org.github.io/OpenScan-Doc/hardware/OpenScanClassic/).

## Recommended Hardware Setup

### ✅ Recommended Configuration

**Controller & Drivers:**
- **Arduino Uno** with **CNC Shield v3**
- **TMC2209** stepper drivers (silent operation, advanced features)

**Motors:**
- 1x Nema 17 stepper motor (>40 Ncm) - for turntable rotation
- 1x Nema 17 stepper motor (>13 Ncm) - for tilt mechanism

**Control Software:**
The controller application is written in Python and can be run on either Linux or Windows machines, providing cross-platform support for turntable control.

### ⚠️ NOT Recommended: Arduino Nano with CNC Shield v4

**Avoid this combination** due to multiple critical compatibility issues:

1. **Pin Mapping Mismatch**: The CNC Shield v4 has swapped Step and Direction pins compared to standard GRBL pinouts, requiring manual modification of `cpu_map.h` in the GRBL firmware
2. **Poor Manufacturing Quality**: Cold solder joints and missing connections on header pins, especially affecting DIR signal routing
3. **Power Delivery Issues**: Insufficient power handling for reliable stepper driver operation
4. **Form Factor Problems**: Poor shield seating and connection reliability due to physical design incompatibilities
5. **Motor Control Instability**: Directional issues where motors may only move in one direction regardless of command
6. **Requires Extensive Troubleshooting**: Multiple hardware fixes needed (soldering, pin swapping, firmware modifications) that shouldn't be necessary with proper hardware

For detailed troubleshooting information if you're already using this combination, see [`ControlApp/README.md`](ControlApp/README.md).

## Directory Structure

### `ControlApp/`

Python-based control application providing a GUI and REST API for turntable control. Features include:

- **GRBL Communication**: Full GRBL protocol implementation for Arduino-based controllers
- **REST API Server**: HTTP endpoints for remote turntable control (`/status`, `/position`, `/reset`)
- **Graphical User Interface**: Tkinter-based desktop application for manual control
- **Dual-Axis Support**: Independent control of rotation (X-axis) and tilt (Y-axis)
- **Configuration Management**: JSON-based settings for motors, speeds, and limits

**Key Files:**
- `main.py` - Application entry point
- `src/api/rest_server.py` - REST API server implementation
- `src/grbl/` - GRBL communication modules
- `src/ui/main_window.py` - GUI implementation

See [`ControlApp/README.md`](ControlApp/README.md) for detailed documentation.

### `FlexScripts/`

Automated scanning and calibration scripts for FlexScan3D software integration. These Lua scripts enable fully automated 3D scanning workflows:

- **`automated_2axis_turntable_calibration.script`**: Automated calibration image capture at various angles
- **`automated_2axis_turntable_scan.script`**: Step-based scanning with regular angle intervals
- **`automated_2axis_turntable_scan_fibonacci.script`**: Fibonacci Lattice algorithm for optimal sphere coverage

**Features:**
- Configurable angle ranges and step sizes
- Automatic turntable reset and error handling
- Integration with FlexScan3D alignment and grouping features

See [`FlexScripts/README.md`](FlexScripts/README.md) for detailed script documentation and parameters.

### `PluginRotaryREST/`

C# plugin for FlexScan3D that enables REST API-based turntable control. This plugin allows FlexScan3D to communicate with the ControlApp REST server:

- **FlexScan3D Integration**: Implements the `PluginRotary` interface
- **REST API Client**: HTTP communication with turntable server
- **Dual Motor Support**: Rotation and tilt control
- **Status Monitoring**: Real-time connection and position status

**Requirements:**
- FlexScan3D 3.5 or later
- .NET Framework 4.5.1 (not newer)
- Visual Studio 2019+ (for building)

See [`../PluginRotaryREST/README.md`](../PluginRotaryREST/README.md) for build instructions and API documentation.

## Getting Started

### 1. Hardware Assembly

Follow the [OpenScan Classic building guide](https://openscan-org.github.io/OpenScan-Doc/hardware/OpenScanClassic/) for:
- 3D printing required parts
- Motor mounting and wiring
- Control module assembly
- Complete setup instructions

### 2. Firmware Setup

1. Install GRBL firmware on your Arduino Uno
2. Configure GRBL settings for your motor configuration (steps/mm, max rates, acceleration)
3. Connect motors to CNC Shield v3 with TMC2209 drivers
4. Configure TMC2209 driver current (Vref) for your motors

### 3. Software Setup

**Option A: Standalone Control Application**
1. Navigate to the ControlApp directory: `cd ControlApp`
2. Run the application:
   - **Windows**: `run.bat`
   - **Linux/macOS**: `./run.sh` (or `bash run.sh`)
3. The script will automatically check Python installation, install dependencies if needed, and launch the application
4. Configure serial port and motor settings in the GUI

**Option B: FlexScan3D Integration**
1. Build and install `PluginRotaryREST` plugin (see [`../PluginRotaryREST/README.md`](../PluginRotaryREST/README.md))
2. Start the ControlApp REST server
3. Configure plugin settings in FlexScan3D
4. Use FlexScripts for automated scanning workflows

## System Architecture

```
┌─────────────────┐
│   FlexScan3D    │
│   (Optional)    │
└────────┬────────┘
         │ REST API
         ▼
┌─────────────────┐     ┌──────────────┐
│  ControlApp     │────▶│  Arduino Uno │
│  (REST Server)  │ USB │  + GRBL      │
└─────────────────┘     └──────┬───────┘
                                │
                         ┌──────┴──────┐
                         │ CNC Shield  │
                         │   v3 +      │
                         │ TMC2209     │
                         └──────┬──────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
              ┌─────▼─────┐         ┌──────▼─────┐
              │  Nema 17  │         │  Nema 17   │
              │ (Rotation) │         │  (Tilt)   │
              └───────────┘         └────────────┘
```

## Additional Resources

- [OpenScan Classic Documentation](https://openscan-org.github.io/OpenScan-Doc/hardware/OpenScanClassic/)
- [OpenScan Project](https://openscan-org.github.io/OpenScan-Doc/)
- [GRBL Documentation](https://github.com/gnea/grbl/wiki)

## License

See individual directory README files for license information.
