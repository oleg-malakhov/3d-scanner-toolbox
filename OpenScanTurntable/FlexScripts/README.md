# FlexScan3D Turntable Scripts

This directory contains automated scanning and calibration scripts for FlexScan3D with 2-axis turntable support.

## Scripts Overview

### 1. `automated_2axis_turntable_calibration.script`

**Purpose:** Automated calibration script that captures calibration images at various tilt and rotation angles for camera calibration.

**Main Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `TILT_START` | `-45` | Starting tilt angle in degrees |
| `TILT_END` | `45` | Ending tilt angle in degrees |
| `TILT_STEP` | `9` | Step size for tilt angle in degrees |
| `ANGLE_START` | `-45` | Starting rotation angle in degrees |
| `ANGLE_END` | `45` | Ending rotation angle in degrees |
| `ANGLE_STEP` | `9` | Step size for rotation angle in degrees |
| `ROTATION_MOTOR` | `1` | Motor index for rotation (typically motor 1) |
| `TILT_MOTOR` | `2` | Motor index for tilt (typically motor 2) |
| `DEBUG_MODE` | `false` | Enable debug mode (limits number of scans) |
| `DEBUG_SCAN_LIMIT` | `3` | Number of scans to capture in debug mode |

**Usage Notes:**
- Captures calibration images using `Advance_CaptureCalibrationImage` API
- Automatically resets turntable to zero position before and after execution
- In debug mode, stops after `DEBUG_SCAN_LIMIT` scans for testing

---

### 2. `automated_2axis_turntable_scan.script`

**Purpose:** Automated scanning script using step-based iteration. Scans the object at regular intervals across rotation and tilt ranges.

**Main Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ROTATION_START` | `0` | Starting rotation angle in degrees |
| `ROTATION_END` | `360` | Ending rotation angle in degrees (full circle) |
| `ROTATION_STEP` | `30` | Step size for rotation angle in degrees |
| `TILT_START` | `-75` | Starting tilt angle in degrees |
| `TILT_END` | `75` | Ending tilt angle in degrees |
| `TILT_STEP` | `15` | Step size for tilt angle in degrees |
| `ROTATION_MOTOR` | `1` | Motor index for rotation (typically motor 1) |
| `TILT_MOTOR` | `2` | Motor index for tilt (typically motor 2) |
| `STABILIZATION_DELAY` | `0` | Seconds to wait after motor movement (for stabilization) |
| `ALIGN_ENABLED` | `false` | Automatically align all scans after completion |
| `GROUP_ENABLED` | `false` | Automatically combine all scans into a single group |
| `MESH_GENERATION_MODE` | `"after"` | When to generate meshes: `"during"` or `"after"` |

**Usage Notes:**
- Total number of scans = `((ROTATION_END - ROTATION_START) / ROTATION_STEP + 1) × ((TILT_END - TILT_START) / TILT_STEP + 1)`
- With default values: 13 rotation positions × 11 tilt positions = 143 scans
- `MESH_GENERATION_MODE`:
  - `"during"`: Generate mesh immediately after each scan
  - `"after"`: Generate all meshes after all scans are completed
- Automatically resets turntable to zero position after execution

---

### 3. `automated_2axis_turntable_scan_fibonacci.script`

**Purpose:** Automated scanning script using the Fibonacci Lattice algorithm for optimal sphere coverage. Generates camera positions algorithmically based on a specified number of photos rather than step-based iteration.

**Main Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `TOTAL_PHOTOS` | `20` | Total number of photos to capture |
| `TILT_MIN` | `-60` | Minimum tilt angle in degrees (mechanical limit) |
| `TILT_MAX` | `90` | Maximum tilt angle in degrees (mechanical limit) |
| `ROTATION_MOTOR` | `1` | Motor index for rotation (typically motor 1) |
| `TILT_MOTOR` | `2` | Motor index for tilt (typically motor 2) |
| `STABILIZATION_DELAY` | `0` | Seconds to wait after motor movement |
| `STOP_AFTER_PHOTOS` | `nil` | Stop after N photos for debugging (set to number or `nil` for no limit) |
| `ALIGN_ENABLED` | `false` | Automatically align all scans after completion |
| `GROUP_ENABLED` | `false` | Automatically combine all scans into a single group |
| `SORT_STRATEGY` | `"rotation_first"` | Angle sorting strategy: `"none"`, `"rotation_first"`, `"tilt_first"`, or `"nearest"` |

**Usage Notes:**
- Uses Fibonacci Lattice algorithm for uniform sphere coverage
- Rotation is always 0° to 360° (full circle)
- `SORT_STRATEGY` options:
  - `"none"`: Preserves Fibonacci order exactly
  - `"rotation_first"`: Groups by tilt, completes rotations at each tilt level (default, most efficient)
  - `"tilt_first"`: Alternative grouping strategy
  - `"nearest"`: Greedy nearest-neighbor optimization
- Automatically validates angle sequence and warns if many angles are clamped to limits
- Automatically resets turntable to zero position after execution
- `Scan()` automatically generates meshes based on `Scanning_Generation_Type` setting

---

## Common Configuration

All scripts share these common characteristics:

- **Motor Assignment:** Motor 1 = Rotation, Motor 2 = Tilt (configurable)
- **Error Handling:** Scripts stop execution on fatal errors and reset turntable
- **Logging:** Uses FlexScan3D API logging functions (`DisplayString`, `PrintValue`)
- **API Safety:** All API calls are wrapped with existence checks
- **Cleanup:** Turntable is automatically reset to zero position after execution

## Prerequisites

- FlexScan3D 3.3.x or later
- 2-axis turntable connected and configured
- Scanner connected and configured
- Rotary table connection verified

## Usage Tips

1. **Calibration First:** Run the calibration script before scanning to ensure accurate camera calibration
2. **Step-based vs Fibonacci:** 
   - Use step-based script (`automated_2axis_turntable_scan.script`) for predictable, grid-like coverage
   - Use Fibonacci script (`automated_2axis_turntable_scan_fibonacci.script`) for optimal coverage with fewer photos
3. **Debug Mode:** Enable debug mode or set `STOP_AFTER_PHOTOS` to test scripts with fewer scans
4. **Post-processing:** Enable `ALIGN_ENABLED` and `GROUP_ENABLED` for automatic alignment and combining after scanning
5. **Stabilization:** Increase `STABILIZATION_DELAY` if motors need time to stabilize after movement

## Algorithm Reference

For mathematical details on the Fibonacci Lattice algorithm used in the Fibonacci scanning script, see `Docs/scanning.md` (if available in the repository).
