# PluginRotaryREST

A FlexScan3D plugin that provides REST API-based control for turntable devices. This plugin enables FlexScan3D to communicate with turntable hardware through HTTP REST endpoints, allowing remote control of rotation and tilt functions.

## Description

PluginRotaryREST is a FlexScan3D rotary plugin that implements the `PluginRotary` interface to control turntable devices via REST API. The plugin supports:

- **Dual Motor Control**: Rotation (motor 1) and tilt (motor 2)
- **REST API Communication**: HTTP-based communication with turntable server
- **Status Monitoring**: Real-time connection and position status
- **FlexScan3D Integration**: Seamless integration with FlexScan3D scanning software

The plugin communicates with a turntable server running a REST API, allowing for flexible hardware control and remote operation.

## API Used

The plugin communicates with a turntable REST API server using the following endpoints:

### Base URL
Configurable via settings (default: `http://localhost:5001`)

### Endpoints

#### 1. GET `/status`
Retrieves the current status of the turntable.

**Response:**
```json
{
  "Angle": 0,
  "Tilt": 0,
  "Connected": true
}
```

**Fields:**
- `Angle`: Current rotation angle in degrees
- `Tilt`: Current tilt angle in degrees
- `Connected`: Connection status (boolean)

#### 2. PUT `/position`
Sets the position of the turntable (rotation and/or tilt).

**Request Body:**
```json
{
  "angle": 90,    // Optional: rotation angle in degrees
  "tilt": 15      // Optional: tilt angle in degrees
}
```

**Response:** HTTP 200 OK

#### 3. POST `/reset`
Resets the turntable to its initial position.

**Response:** HTTP 200 OK

### Communication Protocol

- **Content-Type**: `application/json`
- **Method**: HTTP GET, PUT, POST
- **Error Handling**: Non-200 status codes throw `HttpRequestException`

## Dependencies

### Required Libraries

1. **FlexScan3D Libraries** (must be installed):
   - `Common.dll` - FlexScan3D common library
   - `PluginRotaryInterface.dll` - FlexScan3D rotary plugin interface
   - Location: `C:\Program Files\Polyga\FlexScan3D 3.5\App\`

2. **NuGet Packages**:
   - `Newtonsoft.Json` (v13.0.3) - JSON serialization/deserialization

3. **.NET Framework**:
   - .NET Framework 4.5.1 or later
   - System libraries: `System`, `System.Core`, `System.Configuration`, `System.Net.Http`, `System.Xml.Linq`

## Building the Project

### Prerequisites

1. **Visual Studio 2019 or later** (or Visual Studio Code with .NET SDK)
2. **.NET Framework 4.5.1 Developer Pack**
3. **FlexScan3D 3.5** installed (for library references)
4. **NuGet Package Manager**

### Build Steps

#### Option 1: Using Visual Studio

1. Open `PluginRotaryREST.slnx` in Visual Studio
2. Restore NuGet packages:
   - Right-click solution → **Restore NuGet Packages**
   - Or: Tools → NuGet Package Manager → Package Manager Console → `dotnet restore`
3. Build the solution:
   - **Build** → **Build Solution** (Ctrl+Shift+B)
   - Or: Right-click project → **Build**

#### Option 2: Using .NET CLI

```bash
# Navigate to project directory
cd PluginRotaryREST

# Restore NuGet packages
dotnet restore

# Build the project
dotnet build

# Build in Release mode
dotnet build -c Release
```

### Build Output

The compiled DLL will be located at:
- **Debug**: `bin\Debug\net451\PluginRotaryREST.dll`
- **Release**: `bin\Release\net451\PluginRotaryREST.dll`

### Build Configuration

The project uses SDK-style project format targeting .NET Framework 4.5.1:
- **Target Framework**: `net451`
- **Assembly Name**: `PluginRotaryREST`
- **Root Namespace**: `PluginRotaryREST`

## Configuration

### Settings

The plugin uses user-scoped settings that can be configured in `app.config` or through FlexScan3D settings:

| Setting Name | Type | Default | Description |
|-------------|------|---------|-------------|
| `Rotary_REST_ServerUrl` | string | `http://localhost:5001` | Base URL of the turntable REST API server |
| `Rotary_REST_Speed` | double | `0.8` | Movement speed (currently unused) |
| `Rotary_REST_StepsPerDegree` | double | `1` | Steps per degree conversion factor |

### Configuration File

Settings are stored in:
- `app.config` - Development settings
- `PluginRotaryREST.dll.config` - Deployment settings (copied to output directory)

## Installation

1. Build the project (see Build Steps above)
2. Copy `PluginRotaryREST.dll` and `PluginRotaryREST.dll.config` to:
   ```
   C:\Program Files\Polyga\FlexScan3D 3.5\App\Rotary Modules\PluginRotaryREST\
   ```
3. Ensure the turntable REST API server is running and accessible
4. Configure the server URL in FlexScan3D settings if different from default
5. Restart FlexScan3D

## Usage

1. **Start the Turntable Server**: Ensure your REST API turntable server is running
2. **Configure Server URL**: Set `Rotary_REST_ServerUrl` to match your server address
3. **Launch FlexScan3D**: The plugin will automatically detect and connect to the turntable
4. **Use in Scanning**: The turntable will appear as `PluginRotaryREST::Turntable` in FlexScan3D

## Project Structure

```
PluginRotaryREST/
├── PluginRotaryREST.cs          # Main plugin class implementing PluginRotary interface
├── RotaryREST.cs                 # Rotary device implementation
├── TurntableRestClient.cs        # REST API client
├── PluginUtils.cs                # Utility functions
├── Settings.cs                   # Settings partial class
├── app.config                    # Application configuration
├── PluginRotaryREST.dll.config  # Runtime configuration
├── Properties/
│   ├── AssemblyInfo.cs          # Assembly metadata
│   ├── Settings.settings        # Settings definition
│   └── Settings.Designer.cs     # Auto-generated settings code
└── PluginRotaryREST.csproj      # Project file
```

## Features

- ✅ REST API-based turntable control
- ✅ Dual motor support (rotation + tilt)
- ✅ Real-time status monitoring
- ✅ Configurable server URL
- ✅ Error handling and logging
- ✅ FlexScan3D integration

## Troubleshooting

### Build Issues

**Error: Cannot find Common.dll or PluginRotaryInterface.dll**
- Ensure FlexScan3D 3.5 is installed
- Verify the HintPath in `.csproj` points to the correct location
- Check that the DLLs exist at: `C:\Program Files\Polyga\FlexScan3D 3.5\App\`

**Warning: Architecture mismatch (MSIL vs AMD64)**
- This is expected and non-critical
- The plugin will work correctly at runtime

### Runtime Issues

**Plugin not detected by FlexScan3D**
- Verify DLL is in the correct directory: `Rotary Modules\PluginRotaryREST\`
- Check that `PluginRotaryREST.dll.config` is present
- Ensure FlexScan3D has permissions to load the plugin

**Connection failures**
- Verify the turntable REST API server is running
- Check the `Rotary_REST_ServerUrl` setting matches your server
- Test the server endpoints manually (e.g., using curl or Postman)
- Check network connectivity and firewall settings

## License

Copyright © 2025

## Version

1.0.0.0
