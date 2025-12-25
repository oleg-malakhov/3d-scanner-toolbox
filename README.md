# 3D Scanner Toolbox

A collection of tools and utilities for 3D scanning workflows, including marker generation for calibration targets and turntable control for automated scanning.

## Overview

This toolbox provides essential tools for 3D scanning operations:

- **Marker Generation** - Create SVG calibration targets with configurable markers
- **Turntable Control** - Control Revopoint Dual Axis Turntable via GUI, CLI, or REST API

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
└── README.md                   # This file
```

## Requirements

### Markers
- Python 3.x (standard library only - no external dependencies)

### Revopoint Turntable
- Python 3.7+
- Bluetooth adapter with BLE support
- See [RevopointTurntable/requirements.txt](RevopointTurntable/requirements.txt) for Python packages

## Installation

### Markers
No installation required - just Python 3.x!

### Revopoint Turntable
```bash
cd RevopointTurntable
pip install -r requirements.txt
```

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
- **Turntable**: Designed for Revopoint Dual Axis Turntable (device name: `REVO_DUAL_AXIS_TABLE`)
- **Platforms**: 
  - Markers: Cross-platform (any OS with Python 3.x)
  - Turntable: Windows, macOS, Linux (requires BLE support)

## Contributing

This is a collection of tools for 3D scanning workflows. Feel free to extend and adapt for your needs.

## License

This code is provided as-is for use in your projects.

## References

- [Revopoint Dual-Axis Turntable Web-based Controller](https://github.com/eXplOiD1/Revopoint-Dual-Axis-Turntable-webbased-Controller) - Original turntable controller implementation
- [FlexScan3D](https://www.flexscan3d.com/) - 3D scanning software that uses complex markers
