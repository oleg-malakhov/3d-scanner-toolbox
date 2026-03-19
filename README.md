# 3D Scanner Toolbox

A collection of tools and utilities for 3D scanning workflows, including marker generation for calibration targets and turntable control for automated scanning.

## Overview

This toolbox provides essential tools for 3D scanning operations:

- **Marker Generation** — Create SVG calibration targets with configurable markers (complex markers for FlexScan3D or simple single-ring markers)
- **Revopoint Turntable** — Control the Revopoint Dual Axis Turntable via BLE; includes GUI, CLI, and REST API
- **OpenScan Turntable** — GRBL-based 2-axis turntable (OpenScan Classic design): Python ControlApp with GUI and REST API, plus FlexScan3D automation scripts (calibration and scanning)
- **FlexScan3D Integration** — PluginRotaryREST plugin for REST-based turntable control in FlexScan3D; works with both Revopoint (REST server) and OpenScan ControlApp

## Components

### 📍 Markers

Generate SVG vector images of calibration targets with randomly placed markers. Perfect for creating calibration patterns used in 3D scanning software like FlexScan3D.

**Features:**
- Complex markers with multiple concentric rings (for FlexScan3D)
- Simple markers with single black ring
- Configurable marker placement and spacing
- Vector output (SVG) that scales perfectly

**Quick Start:**
```bash
cd Markers
python3 generate_circle.py 100 10 30
```

📖 [Full Documentation →](Markers/README.md)

### 🔄 Revopoint Turntable

Control the Revopoint Dual Axis Turntable (DAT) for automated 3D scanning workflows. Provides multiple interfaces for integration with scanning software.

**Features:**
- Graphical user interface with real-time status
- Command-line interface for automation
- REST API for programmatic control
- Automatic reconnection handling
- Windows popup handler for FlexScan3D integration

**Quick Start:**
```bash
cd RevopointTurntable
pip install -r requirements.txt
python turntable_gui.py
```

📖 [Full Documentation →](RevopointTurntable/README.md)

### 🔌 PluginRotaryREST

A FlexScan3D plugin that enables REST API-based turntable control. This C# plugin allows FlexScan3D to communicate with turntable hardware through HTTP REST endpoints, enabling seamless integration with turntable control servers.

**Features:**
- FlexScan3D integration via PluginRotary interface
- REST API client for HTTP-based turntable communication
- Dual motor support (rotation and tilt control)
- Real-time status monitoring and connection management
- Configurable server URL and settings

**Quick Start:**
```bash
cd PluginRotaryREST
# Open PluginRotaryREST.slnx in Visual Studio
# Build the solution and copy DLL to FlexScan3D plugins directory
```

📖 [Full Documentation →](PluginRotaryREST/README.md)

## Project Structure

```
3d-scanner-toolbox/
├── Markers/                    # Marker generation tools
│   ├── generate_circle.py      # Complex markers (FlexScan3D compatible)
│   ├── generate_circle_simple.py  # Simple markers
│   ├── README.md               # Marker documentation
│   └── requirements.txt        # Dependencies (none - stdlib only)
│
├── RevopointTurntable/         # Turntable control
│   ├── turntable_gui.py        # GUI application with REST API
│   ├── turntable_client.py     # Command-line client
│   ├── README.md               # Turntable documentation
│   └── requirements.txt        # Python dependencies
│
├── OpenScanTurntable/          # OpenScan turntable system
│   ├── ControlApp/             # Python control application
│   ├── FlexScripts/            # FlexScan3D automation scripts
│   └── README.md               # OpenScan documentation
│
├── PluginRotaryREST/           # FlexScan3D REST API plugin
│   ├── PluginRotaryREST.cs     # Main plugin implementation
│   ├── PluginRotaryREST.csproj # C# project file
│   └── README.md               # Plugin documentation
│
└── README.md                   # This file
```

## Requirements

### Markers
- Python 3.x (standard library only - no external dependencies)

### Revopoint Turntable
- Python 3.7+
- Bluetooth adapter with BLE support
- See [RevopointTurntable/requirements.txt](RevopointTurntable/requirements.txt) for Python packages

### PluginRotaryREST
- FlexScan3D 3.5 or later
- .NET Framework 4.5.1 (not newer)
- Visual Studio 2019+ (for building)
- See [PluginRotaryREST/README.md](PluginRotaryREST/README.md) for detailed requirements

## Installation

### Markers
No installation required - just Python 3.x!

### Revopoint Turntable
```bash
cd RevopointTurntable
pip install -r requirements.txt
```

### PluginRotaryREST
1. Open `PluginRotaryREST.slnx` in Visual Studio
2. Restore NuGet packages
3. Build the solution
4. Copy `PluginRotaryREST.dll` and `PluginRotaryREST.dll.config` to FlexScan3D plugins directory

See [PluginRotaryREST/README.md](PluginRotaryREST/README.md) for detailed installation instructions.

## Usage Examples

### Generate Calibration Target

Create a 100mm circle with 30 complex markers (FlexScan3D compatible):
```bash
cd Markers
python3 generate_circle.py 100 10 30 --output calibration_target.svg
```

### Control Turntable via CLI

Rotate to 90 degrees:
```bash
cd RevopointTurntable
python turntable_client.py rotate 90
```

### Control Turntable via API

```python
import requests

# Set position
requests.put('http://localhost:5001/position', 
             json={'angle': 180, 'tilt': 15})

# Get status
status = requests.get('http://localhost:5001/status').json()
print(f"Angle: {status['angle']}, Tilt: {status['tilt']}")
```

## Workflow Integration

### Typical 3D Scanning Workflow

1. **Generate Calibration Target**
   ```bash
   cd Markers
   python3 generate_circle.py 100 10 30
   ```

2. **Print the SVG** at the correct scale

3. **Start Turntable Controller**
   ```bash
   cd RevopointTurntable
   python turntable_gui.py
   ```

4. **Automate Scanning** using the REST API or CLI to rotate through positions

5. **Process Scans** in your 3D scanning software (e.g., FlexScan3D)

## Compatibility

- **Markers**: Compatible with FlexScan3D and other 3D scanning software that uses checkerboard/marker patterns
- **Revopoint Turntable**: Designed for Revopoint Dual Axis Turntable (device name: `REVO_DUAL_AXIS_TABLE`)
- **PluginRotaryREST**: Compatible with FlexScan3D 3.5+ and any turntable server implementing the REST API protocol
- **Platforms**: 
  - Markers: Cross-platform (any OS with Python 3.x)
  - Revopoint Turntable: Windows, macOS, Linux (requires BLE support)
  - PluginRotaryREST: Windows (FlexScan3D requirement)

## Contributing

This is a collection of tools for 3D scanning workflows. Feel free to extend and adapt for your needs.

## License

This code is provided as-is for use in your projects.

## References

- [Revopoint Dual-Axis Turntable Web-based Controller](https://github.com/eXplOiD1/Revopoint-Dual-Axis-Turntable-webbased-Controller) - Original turntable controller implementation
- [FlexScan3D](https://www.flexscan3d.com/) - 3D scanning software that uses complex markers
