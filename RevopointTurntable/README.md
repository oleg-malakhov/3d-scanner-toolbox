# Revopoint Dual Axis Turntable Controller

A Python-based controller for the Revopoint Dual Axis Turntable (DAT) with both GUI and command-line interfaces, plus a REST API for programmatic control. This tool enables precise control of the turntable's rotation and tilt axes for 3D scanning workflows.

## Features

- **Graphical User Interface (GUI)** - Visual control panel with real-time status updates
- **Command-Line Interface (CLI)** - Script-friendly control for automation
- **REST API** - HTTP endpoints for integration with other applications
- **Bluetooth Low Energy (BLE) Communication** - Direct connection to the turntable
- **Automatic Reconnection** - Handles disconnections gracefully
- **Position Tracking** - Real-time angle and tilt monitoring
- **Windows Popup Handler** - Automatically closes FlexScan3D error dialogs (Windows only)

## Requirements

- Python 3.7 or higher
- Bluetooth adapter with BLE support
- Revopoint Dual Axis Turntable (device name: `REVO_DUAL_AXIS_TABLE`)

### Python Dependencies

- `bleak` - Bluetooth Low Energy communication
- `flask` - REST API server
- `requests` - HTTP client (for CLI)
- `tkinter` - GUI framework (usually included with Python)
- `pywinauto` - Windows popup handler (optional, Windows only)

## Installation

1. Install the required Python packages:

```bash
pip install bleak flask requests
```

2. (Optional, Windows only) Install pywinauto for automatic popup handling:

```bash
pip install pywinauto
```

## Usage

### GUI Application

Launch the graphical interface:

```bash
python turntable_gui.py
```

The GUI displays:
- **Address** - Bluetooth address of the connected turntable
- **Angle** - Current rotation angle (0-360 degrees)
- **Tilt** - Current tilt angle (-30 to +30 degrees)
- **Status** - Connection status and operation feedback
- **Reset Button** - Returns turntable to zero position

The GUI automatically:
- Scans for and connects to the turntable
- Saves the device address to `turntable_address.txt` for faster reconnection
- Starts a REST API server on port 5001
- Updates status in real-time

### Command-Line Interface

The CLI provides three commands:

#### Rotate to Absolute Angle

```bash
python turntable_client.py rotate <angle>
```

Example:
```bash
python turntable_client.py rotate 90
```

#### Tilt to Absolute Angle

```bash
python turntable_client.py tilt <angle>
```

Example:
```bash
python turntable_client.py tilt 15
```

**Note:** Tilt angle must be between -30 and 30 degrees.

#### Reset to Zero Position

```bash
python turntable_client.py reset
```

This resets both rotation and tilt to their zero positions.

### REST API

The GUI application automatically starts a Flask server on port 5001 (default). The API provides the following endpoints:

#### Set Position

```http
PUT http://localhost:5001/position
Content-Type: application/json

{
  "angle": 90,
  "tilt": 15
}
```

Both `angle` and `tilt` are optional. If omitted, the current value is maintained.

**Response:**
```json
{
  "status": "success"
}
```

#### Reset Position

```http
POST http://localhost:5001/reset
```

**Response:**
```json
{
  "status": "success"
}
```

#### Get Status

```http
GET http://localhost:5001/status
```

**Response:**
```json
{
  "angle": 90,
  "tilt": 15,
  "connected": true
}
```

**Error Responses:**

- `400` - Bad Request (invalid JSON)
- `500` - Internal Server Error
- `503` - Service Unavailable (turntable not connected)

## Bluetooth API Reference

This implementation is based on the Bluetooth API documented in the [Revopoint Dual-Axis Turntable Web-based Controller](https://github.com/eXplOiD1/Revopoint-Dual-Axis-Turntable-webbased-Controller) project.

### Device Information

- **Device Name:** `REVO_DUAL_AXIS_TABLE`
- **UART Service UUID:** `0000ffe0-0000-1000-8000-00805f9b34fb`
- **UART Characteristic UUID:** `0000ffe1-0000-1000-8000-00805f9b34fb`

### Command Protocol

Commands are sent as UTF-8 encoded strings and responses are received via BLE notifications.

#### Rotation Commands

- `+CT,TURNANGLE=<degrees>;` - Rotate by relative angle (degrees)
- `+CT,TURNSPEED=<speed>;` - Set rotation speed (default: 35.64)
- `+CT,TOZERO;` - Reset rotation to zero position

#### Tilt Commands

- `+CR,TILTVALUE=<degrees>;` - Set absolute tilt angle (-30 to 30 degrees)
- `+CR,TILTSPEED=<speed>;` - Set tilt speed (default: 9)
- `+CR,TOZERO;` - Reset tilt to zero position

#### Query Commands

- `+QT,CHANGEANGLE;` - Query current rotation angle
  - Response format: `+DATA=<angle>;`

### Command Format

- Commands must end with a semicolon (`;`)
- Responses are received asynchronously via BLE notifications
- The device responds with `+DATA=<value>;` format for queries

## Configuration

### Device Address Caching

The application automatically saves the turntable's Bluetooth address to `turntable_address.txt` in the current directory. This speeds up reconnection on subsequent runs.

To force a rescan, delete the `turntable_address.txt` file.

### API Port

The default API port is 5001. To change it, modify the `API_PORT` constant in `turntable_gui.py`:

```python
API_PORT = 5001  # Change to your desired port
```

### Rotation and Tilt Speeds

Default speeds are defined as constants:

```python
FASTEST_ROTATION_SPEED = 35.64
FASTEST_TILT_SPEED = 9
```

These are set automatically when the turntable connects. Modify these values in `turntable_gui.py` if needed.

## Architecture

The application consists of three main components:

1. **TurntableController** - Manages BLE communication in a separate thread
2. **TurntableApp** - GUI application with Flask API server
3. **turntable_client.py** - Command-line client for the REST API

### Threading Model

- **Controller Thread** - Handles all BLE communication asynchronously
- **API Thread** - Runs Flask server for REST endpoints
- **GUI Thread** - Main thread for Tkinter interface
- **Popup Watcher Thread** - Windows-only thread for closing FlexScan3D dialogs

## Troubleshooting

### Turntable Not Found

- Ensure the turntable is powered on
- Check that Bluetooth is enabled on your computer
- Verify the device name is `REVO_DUAL_AXIS_TABLE`
- Try deleting `turntable_address.txt` to force a rescan
- Move the turntable closer to your computer

### Connection Failures

- Restart the turntable
- Restart Bluetooth on your computer
- Check for other applications using the turntable
- Ensure you have proper Bluetooth permissions

### API Connection Errors

- Verify the GUI application is running (it starts the API server)
- Check that port 5001 is not in use by another application
- Ensure firewall allows connections on port 5001

### Position Not Updating

- The turntable may still be moving (wait a few seconds)
- Check connection status in the GUI
- Try resetting the position

### Windows Popup Handler Not Working

- Install `pywinauto`: `pip install pywinauto`
- Ensure you're running on Windows
- Check that FlexScan3D is running (if applicable)

## Integration Examples

### Python Script

```python
import requests

# Set position
response = requests.put('http://localhost:5001/position', 
                       json={'angle': 180, 'tilt': 0})
print(response.json())

# Get status
status = requests.get('http://localhost:5001/status').json()
print(f"Angle: {status['angle']}, Tilt: {status['tilt']}")
```

### Bash Script

```bash
#!/bin/bash
# Rotate through 8 positions for scanning

for angle in 0 45 90 135 180 225 270 315; do
    curl -X PUT http://localhost:5001/position \
         -H "Content-Type: application/json" \
         -d "{\"angle\": $angle}"
    sleep 2
done
```

## License

This code is provided as-is for use in your projects.

## References

- [Revopoint Dual-Axis Turntable Web-based Controller](https://github.com/eXplOiD1/Revopoint-Dual-Axis-Turntable-webbased-Controller) - Original web-based controller implementation
- [Bleak Documentation](https://bleak.readthedocs.io/) - BLE library documentation

