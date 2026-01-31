"""GRBL controller for communication with GRBL firmware."""

import serial
import threading
import queue
import time
import re
from typing import Optional, Callable, Dict, Any, List
from enum import Enum

from src.utils.config import Config
from src.utils.serial_utils import find_grbl_device, list_serial_ports

# Hardcoded GRBL max rate (applied to both axes on connection)
GRBL_MAX_RATE = 15000.0  # steps/min


class MachineState(Enum):
    """GRBL machine states."""
    IDLE = "Idle"
    RUN = "Run"
    HOLD = "Hold"
    JOG = "Jog"
    ALARM = "Alarm"
    DOOR = "Door"
    CHECK = "Check"
    HOME = "Home"
    SLEEP = "Sleep"
    UNKNOWN = "Unknown"


class GRBLController:
    """Handles all communication with GRBL firmware."""
    
    def __init__(self, config: Config):
        """
        Initialize GRBL controller.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.serial: Optional[serial.Serial] = None
        self.connected = False
        self.machine_state = MachineState.UNKNOWN
        self.current_position = {'x': 0.0, 'y': 0.0}
        self.command_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.status_callbacks: List[Callable] = []
        
        # GRBL settings (tracked from responses)
        self.grbl_x_steps_per_mm = 1.0  # Default, will be updated from GRBL
        self.grbl_y_steps_per_mm = 1.0  # Default, will be updated from GRBL
        self.grbl_settings = {}  # Store all GRBL settings
        self.settings_received = threading.Event()  # Signal when settings are received
        
        # Threading
        self.read_thread: Optional[threading.Thread] = None
        self.status_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Configuration
        self.baud_rate = config.get('serial.baud_rate', 115200)
        self.timeout = config.get('serial.timeout', 1.0)
        self.status_poll_interval = config.get('grbl.status_poll_interval', 0.1)
    
    def connect(self, port: Optional[str] = None, auto_detect: bool = True) -> bool:
        """
        Connect to GRBL device.
        
        Args:
            port: Serial port name. If None and auto_detect is True, will auto-detect.
            auto_detect: If True, automatically find GRBL device.
            
        Returns:
            True if connected successfully, False otherwise
        """
        if self.connected:
            self.disconnect()
        
        # Auto-detect if requested
        if auto_detect and port is None:
            progress_callback = lambda msg: self._notify_status(f"Auto-detecting: {msg}")
            port = find_grbl_device(
                baud_rate=self.baud_rate,
                timeout=self.config.get('serial.auto_detect_timeout', 2.0),
                progress_callback=progress_callback
            )
        
        if port is None:
            self._notify_status("No GRBL device found")
            return False
        
        try:
            self.serial = serial.Serial(
                port,
                self.baud_rate,
                timeout=self.timeout,
                write_timeout=self.timeout
            )
            time.sleep(0.1)  # Small delay for port to stabilize
            
            # Clear buffers
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            
            # Send wake-up command
            self.serial.write(b'\r\n')
            time.sleep(0.2)
            
            # Read welcome message
            response = self.serial.read(100).decode('utf-8', errors='ignore')
            if 'Grbl' not in response and 'grbl' not in response.lower():
                self.serial.close()
                self.serial = None
                self._notify_status(f"Device on {port} is not GRBL")
                return False
            
            # Initialize GRBL
            self._initialize_grbl()
            
            # Start threads
            self.running = True
            self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.read_thread.start()
            self.status_thread = threading.Thread(target=self._status_loop, daemon=True)
            self.status_thread.start()
            
            # Mark as connected
            self.connected = True
            
            # Retrieve and display GRBL settings
            time.sleep(0.5)  # Give threads time to start
            self._retrieve_and_display_settings()
            
            # Configure GRBL for direct step control
            # Do this after marking as connected so send_command works
            time.sleep(0.5)  # Give time for settings to be received
            self._configure_grbl_steps()
            
            self._notify_status(f"Connected to {port}")
            return True
            
        except (serial.SerialException, OSError) as e:
            self._notify_status(f"Connection error: {e}")
            if self.serial:
                try:
                    self.serial.close()
                except:
                    pass
                self.serial = None
            return False
    
    def disconnect(self) -> None:
        """Disconnect from GRBL device."""
        self.running = False
        self.connected = False
        
        # Wait for threads to finish
        if self.read_thread and self.read_thread.is_alive():
            self.read_thread.join(timeout=1.0)
        if self.status_thread and self.status_thread.is_alive():
            self.status_thread.join(timeout=1.0)
        
        if self.serial and self.serial.is_open:
            try:
                self.serial.close()
            except:
                pass
            self.serial = None
        
        self._notify_status("Disconnected")
    
    def _initialize_grbl(self) -> None:
        """Send initialization commands to GRBL."""
        init_commands = self.config.get('grbl.init_commands', ['$X', 'G90', 'G21', 'G54'])
        
        # Command explanations
        command_explanations = {
            '$X': 'Kill Alarm Lock - Unlocks GRBL if it\'s in an alarm state (e.g., after limit switch trigger or reset)',
            'G90': 'Absolute Positioning Mode - All coordinates are absolute (0-360° for X, -90° to +90° for Y)',
            'G91': 'Incremental Positioning Mode - All coordinates are relative to current position',
            'G20': 'Inch Units - Positions reported in inches',
            'G21': 'Millimeter Units - Positions reported in millimeters (default for turntable)',
            'G54': 'Work Coordinate System 1 - Use work coordinate system G54 (default coordinate system)',
            'G55': 'Work Coordinate System 2',
            'G56': 'Work Coordinate System 3',
            'G57': 'Work Coordinate System 4',
            'G58': 'Work Coordinate System 5',
            'G59': 'Work Coordinate System 6',
            'G92': 'Set Work Coordinate Offset - Sets current position as origin',
            'G28': 'Go to Predefined Position 1 - Move to stored G28 position',
            'G30': 'Go to Predefined Position 2 - Move to stored G30 position',
        }
        
        print(f"  [GRBL] Initializing GRBL...")
        for cmd in init_commands:
            try:
                # Get explanation for this command
                explanation = command_explanations.get(cmd, 'Unknown command')
                print(f"  [GRBL]   Sending: {cmd}")
                print(f"  [GRBL]          → {explanation}")
                self.serial.write(f"{cmd}\r\n".encode('utf-8'))
                time.sleep(0.2)  # Give GRBL time to process
            except Exception as e:
                print(f"  [GRBL]   Error sending {cmd}: {e}")
        
        # Query GRBL settings to verify coordinate system
        print(f"  [GRBL] Querying GRBL settings (this may take a moment)...")
        time.sleep(0.3)
        try:
            # Query steps/mm settings ($100 for X, $101 for Y)
            self.serial.write(b'$\r\n')  # Request all settings
            time.sleep(0.5)  # Give time for response
        except:
            pass
        
        # Query current position after initialization
        time.sleep(0.3)
        print(f"  [GRBL] Querying initial position...")
        try:
            self.serial.write(b'?')
            time.sleep(0.5)  # Give time for status report
        except:
            pass
        
        # Align work coordinate system with current machine position
        # This ensures G90 absolute positioning works correctly
        print(f"  [GRBL] Aligning work coordinate system...")
        time.sleep(0.3)
        try:
            print(f"  [GRBL]   Sending: G92 X0 Y0")
            print(f"  [GRBL]          → Set Work Coordinate Offset - Sets current position as origin (0,0)")
            self.serial.write(b'G92 X0 Y0\r\n')
            time.sleep(0.2)
        except:
            pass
        
        print(f"  [GRBL] IMPORTANT: Verify GRBL settings:")
        print(f"  [GRBL]   $100 (X steps/mm) should be 1.0 for direct step control")
        print(f"  [GRBL]   $101 (Y steps/mm) should be 1.0 for direct step control")
        print(f"  [GRBL]   If $100/$101 are not 1.0, positions will be incorrect!")
        print(f"  [GRBL]   To fix: Send '$100=1.0' and '$101=1.0' to GRBL")
        print(f"  [GRBL]   Or enable 'auto_configure_steps' in config to set automatically")
    
    def _configure_grbl_steps(self) -> None:
        """Configure GRBL steps/mm settings for direct step control."""
        print(f"  [GRBL] Auto-configuring GRBL for direct step control...")
        print(f"  [GRBL]   This ensures positions are interpreted as steps (1:1 mapping)")
        time.sleep(0.3)
        
        # Set $100 and $101 to 1.0 for direct step control
        success = True
        try:
            print(f"  [GRBL]   Setting $100=1.0 (X-axis: 1 step per unit)")
            if not self.send_command("$100=1.0", wait_for_ok=True):
                print(f"  [GRBL]   ⚠️  Failed to set $100")
                success = False
            time.sleep(0.3)
            
            print(f"  [GRBL]   Setting $101=1.0 (Y-axis: 1 step per unit)")
            if not self.send_command("$101=1.0", wait_for_ok=True):
                print(f"  [GRBL]   ⚠️  Failed to set $101")
                success = False
            time.sleep(0.3)
            
            # Verify settings were applied by querying them directly
            print(f"  [GRBL]   Verifying settings...")
            time.sleep(0.3)
            # Query $100 directly
            if self.send_command("$100", wait_for_ok=False):
                time.sleep(0.3)
            # Query $101 directly  
            if self.send_command("$101", wait_for_ok=False):
                time.sleep(0.3)
            # Also request all settings
            self.serial.write(b'$\r\n')  # Request all settings
            time.sleep(0.8)  # Give more time for response
            
            if success:
                print(f"  [GRBL]   ✓ GRBL configured for direct step control")
                print(f"  [GRBL]   Positions will now be interpreted as steps (1:1 mapping)")
                print(f"  [GRBL]   Note: Settings are saved to GRBL's EEPROM automatically")
            else:
                print(f"  [GRBL]   ⚠️  Some settings may not have been applied")
        except Exception as e:
            print(f"  [GRBL]   ✗ Error configuring GRBL: {e}")
            print(f"  [GRBL]   You may need to manually set $100=1.0 and $101=1.0")
    
    def send_command(self, command: str, wait_for_ok: bool = True) -> bool:
        """
        Send G-code command to GRBL.
        
        Args:
            command: G-code command string
            wait_for_ok: If True, wait for OK response before returning
            
        Returns:
            True if command sent successfully (and OK received if wait_for_ok), False otherwise
        """
        if not self.serial or not self.serial.is_open:
            print(f"  [GRBL] ✗ Serial port not available, cannot send command")
            return False
        
        try:
            # Add line ending if not present
            raw_command = command
            if not command.endswith('\r\n'):
                command = command.rstrip() + '\r\n'
            
            print(f"  [GRBL] Sending command: {raw_command.strip()}")
            print(f"  [GRBL]   Raw bytes: {command.encode('utf-8')}")
            
            bytes_written = self.serial.write(command.encode('utf-8'))
            print(f"  [GRBL]   Bytes written: {bytes_written}")
            
            if wait_for_ok:
                print(f"  [GRBL]   Waiting for OK response (timeout: 5s)...")
                # Wait for OK response (with timeout)
                timeout = time.time() + 5.0
                response_received = False
                while time.time() < timeout:
                    try:
                        response = self.response_queue.get(timeout=0.1)
                        print(f"  [GRBL]   Response received: {response.strip()}")
                        if 'ok' in response.lower():
                            print(f"  [GRBL]   ✓ Command acknowledged")
                            response_received = True
                            return True
                        elif 'error' in response.lower():
                            print(f"  [GRBL]   ✗ Error response: {response.strip()}")
                            self._notify_status(f"GRBL error: {response}")
                            return False
                    except queue.Empty:
                        continue
                
                if not response_received:
                    print(f"  [GRBL]   ✗ Timeout waiting for response")
                return False
            
            print(f"  [GRBL]   Command sent (not waiting for response)")
            return True
            
        except Exception as e:
            print(f"  [GRBL]   ✗ Exception: {e}")
            self._notify_status(f"Error sending command: {e}")
            return False
    
    def move_to(self, x: Optional[float] = None, y: Optional[float] = None, feedrate: Optional[int] = None) -> bool:
        """
        Move to absolute position.
        
        Args:
            x: X position in STEPS (None to keep current)
            y: Y position in STEPS (None to keep current)
            feedrate: Feedrate (None to use default)
            
        Returns:
            True if command sent successfully
        """
        print(f"  [GRBL] Building move command...")
        current_x_units = self.current_position.get('x', 0)
        current_y_units = self.current_position.get('y', 0)
        print(f"  [GRBL]   Current position (MPos units): X={current_x_units:.6f}, Y={current_y_units:.6f}")
        
        cmd_parts = ['G0']
        
        # IMPORTANT: x and y are in STEPS, but GRBL expects UNITS
        # GRBL calculates: actual_steps = units × $100 (or $101 for Y)
        # We want: actual_steps = x (in steps)
        # So we need: units = x / $100
        if x is not None:
            # Convert steps to units for GRBL
            x_units = x / self.grbl_x_steps_per_mm
            cmd_parts.append(f'X{x_units:.3f}')
            print(f"  [GRBL]   Target X: {x:.6f} steps")
            print(f"  [GRBL]   GRBL $100: {self.grbl_x_steps_per_mm:.6f}")
            print(f"  [GRBL]   Sending as units: {x_units:.6f} (steps / $100)")
            print(f"  [GRBL]   GRBL will calculate: {x_units:.6f} × {self.grbl_x_steps_per_mm:.6f} = {x_units * self.grbl_x_steps_per_mm:.6f} steps")
        if y is not None:
            # Convert steps to units for GRBL
            y_units = y / self.grbl_y_steps_per_mm
            cmd_parts.append(f'Y{y_units:.3f}')
            print(f"  [GRBL]   Target Y: {y:.6f} steps")
            print(f"  [GRBL]   GRBL $101: {self.grbl_y_steps_per_mm:.6f}")
            print(f"  [GRBL]   Sending as units: {y_units:.6f} (steps / $101)")
        if feedrate is not None:
            cmd_parts.append(f'F{feedrate}')
            print(f"  [GRBL]   Feedrate: {feedrate}")
        
        command = ' '.join(cmd_parts)
        print(f"  [GRBL]   Final command: {command}")
        return self.send_command(command)
    
    def reset_to_home(self) -> bool:
        """
        Move to home position.
        
        Note: This expects home_x and home_y to be in STEPS, not degrees!
        """
        home_x = self.config.get('home_position.x', 0)
        home_y = self.config.get('home_position.y', 0)
        return self.move_to(x=home_x, y=home_y)
    
    def set_current_position_as_origin(self) -> bool:
        """
        Set current GRBL position as origin (work coordinate offset).
        Uses G92 to set current position to (0, 0).
        
        Returns:
            True if command sent successfully
        """
        print(f"  [GRBL] Setting current position as origin (G92 X0 Y0)...")
        return self.send_command("G92 X0 Y0", wait_for_ok=True)
    
    def emergency_stop(self) -> None:
        """Send emergency stop command."""
        if self.serial and self.connected:
            try:
                self.serial.write(b'!')  # Feed hold
            except:
                pass
    
    def unlock(self) -> bool:
        """Unlock GRBL (clear alarm)."""
        return self.send_command('$X')
    
    def _read_loop(self) -> None:
        """Background thread to read responses from GRBL."""
        while self.running and self.serial and self.serial.is_open:
            try:
                if self.serial.in_waiting > 0:
                    line = self.serial.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        self._process_response(line)
                else:
                    time.sleep(0.01)
            except Exception as e:
                if self.running:
                    self._notify_status(f"Read error: {e}")
                break
    
    def _status_loop(self) -> None:
        """Background thread to poll GRBL status."""
        while self.running and self.serial and self.serial.is_open:
            try:
                self.serial.write(b'?')
                time.sleep(self.status_poll_interval)
            except Exception as e:
                if self.running:
                    self._notify_status(f"Status poll error: {e}")
                break
    
    def _process_response(self, line: str) -> None:
        """Process response from GRBL."""
        # Status report format: <Idle|Run|...>,MPos:X.xxx,Y.yyy,...
        if line.startswith('<') and 'MPos:' in line:
            self._parse_status_report(line)
        elif 'ok' in line.lower() or 'error' in line.lower():
            self.response_queue.put(line)
        elif line.startswith('$') and '=' in line:
            # GRBL settings response (e.g., "$100=8.888")
            self._parse_setting(line)
        else:
            # Other messages (alarms, info, etc.)
            self._notify_status(line)
    
    def _parse_status_report(self, status: str) -> None:
        """Parse GRBL status report."""
        old_state = self.machine_state
        old_position = self.current_position.copy()
        
        # Extract machine state
        state_match = re.search(r'<([^,>]+)', status)
        if state_match:
            state_str = state_match.group(1)
            try:
                self.machine_state = MachineState[state_str.upper()]
            except KeyError:
                self.machine_state = MachineState.UNKNOWN
        
        # Extract position - MPos is in "units" (steps / $100), not raw steps!
        pos_match = re.search(r'MPos:([0-9.-]+),([0-9.-]+)', status)
        if pos_match:
            try:
                old_x = self.current_position.get('x', 0.0)
                old_y = self.current_position.get('y', 0.0)
                # MPos is reported in "units" (which equals steps when $100=1.0)
                # If $100 != 1.0, MPos = steps / $100
                mpos_x_units = float(pos_match.group(1))
                mpos_y_units = float(pos_match.group(2))
                
                # Store as "units" - we'll need to know $100 to convert to steps
                self.current_position['x'] = mpos_x_units
                self.current_position['y'] = mpos_y_units
                
                # Log first position update or significant changes
                if old_x == 0.0 and old_y == 0.0 and (self.current_position['x'] != 0.0 or self.current_position['y'] != 0.0):
                    print(f"  [GRBL] Initial position from GRBL (MPos in units): X={self.current_position['x']:.6f}, Y={self.current_position['y']:.6f}")
                    print(f"  [GRBL] Note: MPos is in 'units', not raw steps. If $100=1.0, units = steps.")
            except ValueError:
                pass
        
        # Log state changes
        if old_state != self.machine_state:
            print(f"  [GRBL] State changed: {old_state.value} → {self.machine_state.value}")
        
        # Log position changes (only if significant) - console only, not UI
        pos_delta_x = abs(self.current_position['x'] - old_position.get('x', 0))
        pos_delta_y = abs(self.current_position['y'] - old_position.get('y', 0))
        if pos_delta_x > 0.001 or pos_delta_y > 0.001:
            print(f"  [GRBL] Position update (MPos in units): X={self.current_position['x']:.6f} ({pos_delta_x:+.6f}), "
                  f"Y={self.current_position['y']:.6f} ({pos_delta_y:+.6f})")
            # Convert to steps for debugging
            x_steps = self.current_position['x'] * self.grbl_x_steps_per_mm
            y_steps = self.current_position['y'] * self.grbl_y_steps_per_mm
            print(f"  [GRBL]   Converted to steps: X={x_steps:.6f}, Y={y_steps:.6f} (units × $100/$101)")
        
        # Log when movement completes (state changes from Run to Idle)
        if old_state == MachineState.RUN and self.machine_state == MachineState.IDLE:
            print(f"  [GRBL] ✓ Movement completed")
            print(f"  [GRBL] Final position (MPos in units): X={self.current_position['x']:.6f}, Y={self.current_position['y']:.6f}")
            # Calculate actual movement
            actual_x_delta_units = self.current_position['x'] - old_position.get('x', 0)
            actual_y_delta_units = self.current_position['y'] - old_position.get('y', 0)
            # Convert to steps (MPos is in units, so multiply by steps/mm to get actual steps)
            actual_x_delta_steps = actual_x_delta_units * self.grbl_x_steps_per_mm
            actual_y_delta_steps = actual_y_delta_units * self.grbl_y_steps_per_mm
            print(f"  [GRBL] Actual movement: X={actual_x_delta_units:+.6f} units ({actual_x_delta_steps:+.6f} steps), Y={actual_y_delta_units:+.6f} units ({actual_y_delta_steps:+.6f} steps)")
            print(f"  [GRBL] Note: MPos is in 'units'. With $100={self.grbl_x_steps_per_mm}, units × $100 = steps")
        
        # Notify callbacks
        for callback in self.status_callbacks:
            try:
                callback(self.machine_state, self.current_position)
            except:
                pass
    
    def register_status_callback(self, callback: Callable[[MachineState, Dict[str, float]], None]) -> None:
        """
        Register callback for status updates.
        
        Args:
            callback: Function(state, position) called on status updates
        """
        self.status_callbacks.append(callback)
    
    def _notify_status(self, message: str) -> None:
        """Notify status message (console only, not UI)."""
        print(f"[GRBL] {message}")
    
    def wait_for_idle(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for machine to become idle (movement complete).
        
        Args:
            timeout: Maximum time to wait in seconds. If None, uses estimated movement time + buffer.
            
        Returns:
            True if machine became idle, False if timeout
        """
        if not self.connected:
            return False
        
        start_time = time.time()
        
        # Default timeout: 30 seconds if not specified
        if timeout is None:
            timeout = 30.0
        
        print(f"  [GRBL] Waiting for movement to complete (timeout: {timeout:.1f}s)...")
        
        while time.time() - start_time < timeout:
            # Check machine state
            if self.machine_state == MachineState.IDLE:
                elapsed = time.time() - start_time
                print(f"  [GRBL] ✓ Movement completed in {elapsed:.2f}s")
                return True
            elif self.machine_state == MachineState.ALARM:
                print(f"  [GRBL] ✗ Machine in alarm state")
                return False
            
            # Small sleep to avoid busy-waiting
            time.sleep(0.05)  # 50ms polling interval
        
        # Timeout
        elapsed = time.time() - start_time
        print(f"  [GRBL] ✗ Timeout waiting for movement ({elapsed:.1f}s)")
        return False
    
    def is_moving(self) -> bool:
        """
        Check if machine is currently moving.
        
        Returns:
            True if machine is in RUN, JOG, or HOLD state
        """
        return self.machine_state in (MachineState.RUN, MachineState.JOG, MachineState.HOLD)
    
    def _parse_setting(self, line: str) -> None:
        """Parse a GRBL setting line and store it."""
        # Format: $100=8.888 or $100=8.888 (with description)
        try:
            if '=' in line:
                parts = line.split('=')
                setting_code = parts[0].strip().replace('$', '')
                value_str = parts[1].split()[0] if parts[1].split() else parts[1].strip()
                value = float(value_str)
                
                setting_key = f"${setting_code}"
                self.grbl_settings[setting_key] = value
                
                # Update steps/mm if this is $100 or $101
                if setting_code == '100':
                    self.grbl_x_steps_per_mm = value
                elif setting_code == '101':
                    self.grbl_y_steps_per_mm = value
                
                # Signal that we've received at least one setting
                if not self.settings_received.is_set():
                    self.settings_received.set()
        except (ValueError, IndexError):
            pass
    
    def _retrieve_and_display_settings(self) -> None:
        """Retrieve all GRBL settings and display with interpretation."""
        print(f"\n  [GRBL] ========================================")
        print(f"  [GRBL] Retrieving GRBL Settings...")
        print(f"  [GRBL] ========================================")
        
        # Clear previous settings
        self.grbl_settings = {}
        self.settings_received.clear()
        
        # Request all settings
        try:
            self.serial.write(b'$$\r\n')
            print(f"  [GRBL] Sent: $$ (request all settings)")
        except Exception as e:
            print(f"  [GRBL] ✗ Error requesting settings: {e}")
            return
        
        # Wait for first setting to arrive (indicates GRBL is responding)
        if self.settings_received.wait(timeout=3.0):
            # Wait additional time for all settings to arrive
            # GRBL sends settings sequentially, so we need time for all of them
            time.sleep(1.5)  # Give time for all settings to arrive
            self._display_settings_interpretation()
            # Check and update settings if needed
            self._check_and_update_grbl_settings()
        else:
            print(f"  [GRBL] ⚠️  Timeout waiting for settings response")
            print(f"  [GRBL]   GRBL may not be responding to $$ command")
            if self.grbl_settings:
                print(f"  [GRBL]   Displaying partial settings received:")
                self._display_settings_interpretation()
                # Check and update settings if needed (even with partial settings)
                self._check_and_update_grbl_settings()
            else:
                print(f"  [GRBL]   No settings received. Check GRBL connection.")
    
    def _display_settings_interpretation(self) -> None:
        """Display GRBL settings with detailed interpretation."""
        print(f"\n  [GRBL] ========================================")
        print(f"  [GRBL] All GRBL Settings with Interpretation")
        print(f"  [GRBL] ========================================")
        
        # All GRBL settings with descriptions
        all_settings = {
            # Step and direction settings
            '$0': ('Step Pulse Time', 'microseconds', 'Minimum step pulse width. Default: 10. Too long can cause overlap at high speeds.'),
            '$1': ('Step Idle Delay', 'milliseconds', 'Delay before disabling steppers after motion. 255 = keep enabled always.'),
            '$2': ('Step Port Invert', 'mask', 'Invert step pulse signal. 0=none, 1=X, 2=Y, 3=X+Y, 4=Z, 5=X+Z, 6=Y+Z, 7=all'),
            '$3': ('Direction Port Invert', 'mask', 'Invert direction signal. Same mask as $2.'),
            '$4': ('Step Enable Invert', 'boolean', 'Invert enable pin. 0=normal (low=enabled), 1=inverted (high=enabled)'),
            '$5': ('Limit Pins Invert', 'boolean', 'Invert limit switch logic. 0=normal (low=triggered), 1=inverted'),
            '$6': ('Probe Pin Invert', 'boolean', 'Invert probe pin logic. 0=normal (low=triggered), 1=inverted'),
            
            # Status and reporting
            '$10': ('Status Report Mask', 'mask', 'Status report options. 1=MPos, 2=Buffer data. Default: 1'),
            '$11': ('Junction Deviation', 'mm', 'Cornering speed. Higher=faster corners, lower=safer. Default: 0.010'),
            '$12': ('Arc Tolerance', 'mm', 'Arc rendering accuracy. Lower=more precise, higher=faster. Default: 0.002'),
            '$13': ('Report Inches', 'boolean', 'Report positions in inches. 0=mm (default), 1=inches'),
            
            # Safety and limits
            '$20': ('Soft Limits', 'boolean', 'Enable soft limits. Requires homing. 0=disabled, 1=enabled'),
            '$21': ('Hard Limits', 'boolean', 'Enable hard limit switches. 0=disabled, 1=enabled'),
            '$22': ('Homing Cycle', 'boolean', 'Enable homing cycle. 0=disabled, 1=enabled'),
            '$23': ('Homing Dir Invert', 'mask', 'Invert homing direction. Same mask as $2.'),
            '$24': ('Homing Feed Rate', 'mm/min', 'Slow feed rate for precise homing after switch found'),
            '$25': ('Homing Seek Rate', 'mm/min', 'Fast search rate to find limit switches'),
            '$26': ('Homing Debounce', 'milliseconds', 'Switch debounce delay. Typical: 5-25ms'),
            '$27': ('Homing Pull-off', 'mm', 'Distance to move off limit switch after homing'),
            
            # Spindle (not used for turntable but included for completeness)
            '$30': ('Max Spindle Speed', 'RPM', 'Maximum spindle RPM for 5V PWM output'),
            '$31': ('Min Spindle Speed', 'RPM', 'Minimum spindle RPM for 0.02V PWM output'),
            '$32': ('Laser Mode', 'boolean', 'Enable laser mode (continuous motion). 0=disabled, 1=enabled'),
            
            # Steps per unit (CRITICAL for turntable)
            '$100': ('X-axis Steps/Unit', 'steps/unit', 'CRITICAL: Should be 1.0 for direct step control'),
            '$101': ('Y-axis Steps/Unit', 'steps/unit', 'CRITICAL: Should be 1.0 for direct step control'),
            '$102': ('Z-axis Steps/Unit', 'steps/unit', 'Z-axis steps per unit (not used for turntable)'),
            
            # Max rates (CRITICAL - speed limits)
            '$110': ('X-axis Max Rate', 'steps/min', 'CRITICAL: Maximum speed limit. GRBL caps all speeds at this value'),
            '$111': ('Y-axis Max Rate', 'steps/min', 'CRITICAL: Maximum speed limit. GRBL caps all speeds at this value'),
            '$112': ('Z-axis Max Rate', 'steps/min', 'Z-axis max rate (not used for turntable)'),
            
            # Acceleration (CRITICAL - affects movement smoothness)
            '$120': ('X-axis Acceleration', 'steps/s²', 'CRITICAL: Acceleration rate. Affects how quickly speed is reached'),
            '$121': ('Y-axis Acceleration', 'steps/s²', 'CRITICAL: Acceleration rate. Affects how quickly speed is reached'),
            '$122': ('Z-axis Acceleration', 'steps/s²', 'Z-axis acceleration (not used for turntable)'),
            
            # Max travel (for soft limits)
            '$130': ('X-axis Max Travel', 'units', 'Maximum travel distance (for soft limits)'),
            '$131': ('Y-axis Max Travel', 'units', 'Maximum travel distance (for soft limits)'),
            '$132': ('Z-axis Max Travel', 'units', 'Z-axis max travel (not used for turntable)'),
        }
        
        # Group settings by category
        step_settings = ['$0', '$1', '$2', '$3', '$4', '$5', '$6']
        status_settings = ['$10', '$11', '$12', '$13']
        safety_settings = ['$20', '$21', '$22', '$23', '$24', '$25', '$26', '$27']
        spindle_settings = ['$30', '$31', '$32']
        motion_settings = ['$100', '$101', '$102', '$110', '$111', '$112', '$120', '$121', '$122', '$130', '$131', '$132']
        
        # Display all settings grouped by category
        categories = [
            ('Step & Direction Settings', step_settings),
            ('Status & Reporting', status_settings),
            ('Safety & Limits', safety_settings),
            ('Spindle Settings', spindle_settings),
            ('Motion Settings (CRITICAL)', motion_settings),
        ]
        
        for category_name, setting_keys in categories:
            print(f"\n  [GRBL] --- {category_name} ---")
            for setting_key in setting_keys:
                if setting_key in all_settings:
                    name, unit, description = all_settings[setting_key]
                    value = self.grbl_settings.get(setting_key)
                    if value is not None:
                        # Format boolean values
                        if unit == 'boolean':
                            value_str = 'Enabled' if value > 0 else 'Disabled'
                            print(f"  [GRBL] {setting_key:6} = {value_str:<20} - {name}")
                        # Format mask values
                        elif unit == 'mask' and setting_key in ['$2', '$3', '$23']:
                            mask_bits = []
                            if int(value) & 1: mask_bits.append('X')
                            if int(value) & 2: mask_bits.append('Y')
                            if int(value) & 4: mask_bits.append('Z')
                            mask_str = '+'.join(mask_bits) if mask_bits else 'None'
                            print(f"  [GRBL] {setting_key:6} = {int(value):<20} ({mask_str}) - {name}")
                        else:
                            print(f"  [GRBL] {setting_key:6} = {value:10.3f} {unit:12} - {name}")
                        print(f"  [GRBL]          {description}")
                    else:
                        print(f"  [GRBL] {setting_key:6} = {'NOT RECEIVED':<25} - {name}")
        
        # Display any settings not in our list
        known_keys = set(all_settings.keys())
        received_keys = set(self.grbl_settings.keys())
        unknown_keys = received_keys - known_keys
        if unknown_keys:
            print(f"\n  [GRBL] --- Other Settings ---")
            for setting_key in sorted(unknown_keys):
                value = self.grbl_settings[setting_key]
                print(f"  [GRBL] {setting_key:6} = {value:10.3f} - (Unknown setting)")
        
        # Get app config for comparison
        app_x_max_rate = GRBL_MAX_RATE  # Hardcoded value
        app_y_max_rate = GRBL_MAX_RATE  # Hardcoded value
        app_x_speed = self.config.get('motors.x_axis.speed', 0)
        app_y_speed = self.config.get('motors.y_axis.speed', 0)
        
        # Interpretation and warnings
        print(f"\n  [GRBL] ========================================")
        print(f"  [GRBL] Settings Interpretation")
        print(f"  [GRBL] ========================================")
        
        # Check steps/unit settings
        x_steps = self.grbl_settings.get('$100', 1.0)
        y_steps = self.grbl_settings.get('$101', 1.0)
        
        if abs(x_steps - 1.0) > 0.001:
            print(f"  [GRBL] ⚠️  WARNING: $100 = {x_steps:.3f} (should be 1.0)")
            print(f"  [GRBL]   This will cause incorrect positioning!")
            print(f"  [GRBL]   Fix: Send '$100=1.0' to GRBL")
        else:
            print(f"  [GRBL] ✓ $100 = {x_steps:.3f} (correct for direct step control)")
        
        if abs(y_steps - 1.0) > 0.001:
            print(f"  [GRBL] ⚠️  WARNING: $101 = {y_steps:.3f} (should be 1.0)")
            print(f"  [GRBL]   This will cause incorrect positioning!")
            print(f"  [GRBL]   Fix: Send '$101=1.0' to GRBL")
        else:
            print(f"  [GRBL] ✓ $101 = {y_steps:.3f} (correct for direct step control)")
        
        # Check max rate limits
        x_max_rate = self.grbl_settings.get('$110', 0)
        y_max_rate = self.grbl_settings.get('$111', 0)
        
        print(f"\n  [GRBL] Max Rate Limits (GRBL will cap speed at these values):")
        print(f"  [GRBL]   X-axis ($110): {x_max_rate:.1f} steps/min")
        print(f"  [GRBL]   Y-axis ($111): {y_max_rate:.1f} steps/min")
        
        if app_x_max_rate > 0:
            if app_x_max_rate > x_max_rate:
                print(f"  [GRBL] ⚠️  WARNING: Hardcoded max rate ({app_x_max_rate:.1f}) > GRBL $110 ({x_max_rate:.1f})")
                print(f"  [GRBL]   GRBL will limit X-axis to {x_max_rate:.1f} steps/min")
                print(f"  [GRBL]   To fix: Increase $110 (will be set to {app_x_max_rate:.1f} automatically)")
            else:
                print(f"  [GRBL] ✓ Hardcoded max rate ({app_x_max_rate:.1f}) <= GRBL $110 ({x_max_rate:.1f})")
        
        if app_x_speed > 0 and app_x_speed > x_max_rate:
            print(f"  [GRBL] ⚠️  WARNING: App X speed ({app_x_speed}) > GRBL $110 ({x_max_rate:.1f})")
            print(f"  [GRBL]   GRBL will limit X-axis to {x_max_rate:.1f} steps/min")
        
        if app_y_max_rate > 0:
            if app_y_max_rate > y_max_rate:
                print(f"  [GRBL] ⚠️  WARNING: Hardcoded max rate ({app_y_max_rate:.1f}) > GRBL $111 ({y_max_rate:.1f})")
                print(f"  [GRBL]   GRBL will limit Y-axis to {y_max_rate:.1f} steps/min")
                print(f"  [GRBL]   To fix: Increase $111 (will be set to {app_y_max_rate:.1f} automatically)")
            else:
                print(f"  [GRBL] ✓ Hardcoded max rate ({app_y_max_rate:.1f}) <= GRBL $111 ({y_max_rate:.1f})")
        
        if app_y_speed > 0 and app_y_speed > y_max_rate:
            print(f"  [GRBL] ⚠️  WARNING: App Y speed ({app_y_speed}) > GRBL $111 ({y_max_rate:.1f})")
            print(f"  [GRBL]   GRBL will limit Y-axis to {y_max_rate:.1f} steps/min")
        
        # Check acceleration settings
        x_accel = self.grbl_settings.get('$120', 0)
        y_accel = self.grbl_settings.get('$121', 0)
        
        print(f"\n  [GRBL] Acceleration Settings:")
        print(f"  [GRBL]   X-axis ($120): {x_accel:.1f} steps/s²")
        print(f"  [GRBL]   Y-axis ($121): {y_accel:.1f} steps/s²")
        
        if x_accel > 0:
            # Calculate minimum distance to reach max speed
            if x_max_rate > 0:
                min_distance_x = (x_max_rate / 60.0) ** 2 / (2 * x_accel)
                print(f"  [GRBL]   X-axis needs ~{min_distance_x:.1f} steps to reach max speed")
        
        if y_accel > 0:
            if y_max_rate > 0:
                min_distance_y = (y_max_rate / 60.0) ** 2 / (2 * y_accel)
                print(f"  [GRBL]   Y-axis needs ~{min_distance_y:.1f} steps to reach max speed")
        
        # Check step pulse limits (CPU bottleneck)
        print(f"\n  [GRBL] Step Pulse Limits (CPU Bottleneck):")
        print(f"  [GRBL]   Typical Arduino limit: ~30,000 steps/sec (1,800,000 steps/min)")
        
        if x_steps > 0:
            max_steps_per_sec_x = x_max_rate / 60.0
            print(f"  [GRBL]   X-axis at max rate: {max_steps_per_sec_x:.1f} steps/sec")
            if max_steps_per_sec_x > 30000:
                print(f"  [GRBL]   ⚠️  WARNING: X-axis may exceed CPU step generation limit!")
                print(f"  [GRBL]   Consider reducing $110 or $100")
            else:
                cpu_usage_x = (max_steps_per_sec_x / 30000.0) * 100
                print(f"  [GRBL]   CPU usage: ~{cpu_usage_x:.1f}% of theoretical max")
        
        if y_steps > 0:
            max_steps_per_sec_y = y_max_rate / 60.0
            print(f"  [GRBL]   Y-axis at max rate: {max_steps_per_sec_y:.1f} steps/sec")
            if max_steps_per_sec_y > 30000:
                print(f"  [GRBL]   ⚠️  WARNING: Y-axis may exceed CPU step generation limit!")
                print(f"  [GRBL]   Consider reducing $111 or $101")
            else:
                cpu_usage_y = (max_steps_per_sec_y / 30000.0) * 100
                print(f"  [GRBL]   CPU usage: ~{cpu_usage_y:.1f}% of theoretical max")
        
        print(f"\n  [GRBL] ========================================")
        print(f"  [GRBL] Settings Summary Complete")
        print(f"  [GRBL] ========================================\n")
    
    def _check_and_update_grbl_settings(self) -> None:
        """Check if GRBL settings match configuration and update if needed."""
        print(f"\n  [GRBL] ========================================")
        print(f"  [GRBL] Checking GRBL Settings Against Configuration...")
        print(f"  [GRBL] ========================================")
        
        # Use hardcoded max rate for both axes
        config_x_max_rate = GRBL_MAX_RATE
        config_y_max_rate = GRBL_MAX_RATE
        
        # Get configured acceleration from axis configs (always check if configured)
        config_x_accel = self.config.get('motors.x_axis.acceleration', None)
        config_y_accel = self.config.get('motors.y_axis.acceleration', None)
        
        # Skip if no settings need updating
        if not (config_x_accel or config_y_accel):
            # Still update max rates even if acceleration not configured
            pass
        
        # Get current GRBL settings
        grbl_x_max_rate = self.grbl_settings.get('$110', None)
        grbl_y_max_rate = self.grbl_settings.get('$111', None)
        grbl_x_accel = self.grbl_settings.get('$120', None)
        grbl_y_accel = self.grbl_settings.get('$121', None)
        
        settings_updated = False
        
        # Check and update X-axis max rate ($110) - always set to hardcoded value
        if grbl_x_max_rate is not None:
            if abs(grbl_x_max_rate - config_x_max_rate) > 0.1:  # Allow small floating point differences
                print(f"  [GRBL] ⚠️  X-axis max rate mismatch:")
                print(f"  [GRBL]   GRBL $110: {grbl_x_max_rate:.1f} steps/min")
                print(f"  [GRBL]   Target:   {config_x_max_rate:.1f} steps/min (hardcoded)")
                print(f"  [GRBL]   Updating GRBL $110 to {config_x_max_rate:.1f} steps/min...")
                
                if self.send_command(f"$110={config_x_max_rate:.1f}", wait_for_ok=True):
                    print(f"  [GRBL]   ✓ $110 updated successfully")
                    self.grbl_settings['$110'] = config_x_max_rate
                    settings_updated = True
                else:
                    print(f"  [GRBL]   ✗ Failed to update $110")
            else:
                print(f"  [GRBL] ✓ X-axis max rate ($110): {grbl_x_max_rate:.1f} steps/min (matches hardcoded value)")
        else:
            print(f"  [GRBL]   ⚠️  X-axis max rate ($110) not received from GRBL")
        
        # Check and update Y-axis max rate ($111) - always set to hardcoded value
        if grbl_y_max_rate is not None:
            if abs(grbl_y_max_rate - config_y_max_rate) > 0.1:  # Allow small floating point differences
                print(f"  [GRBL] ⚠️  Y-axis max rate mismatch:")
                print(f"  [GRBL]   GRBL $111: {grbl_y_max_rate:.1f} steps/min")
                print(f"  [GRBL]   Target:   {config_y_max_rate:.1f} steps/min (hardcoded)")
                print(f"  [GRBL]   Updating GRBL $111 to {config_y_max_rate:.1f} steps/min...")
                
                if self.send_command(f"$111={config_y_max_rate:.1f}", wait_for_ok=True):
                    print(f"  [GRBL]   ✓ $111 updated successfully")
                    self.grbl_settings['$111'] = config_y_max_rate
                    settings_updated = True
                else:
                    print(f"  [GRBL]   ✗ Failed to update $111")
            else:
                print(f"  [GRBL] ✓ Y-axis max rate ($111): {grbl_y_max_rate:.1f} steps/min (matches hardcoded value)")
        else:
            print(f"  [GRBL]   ⚠️  Y-axis max rate ($111) not received from GRBL")
        
        # Check and update X-axis acceleration ($120)
        if config_x_accel is not None and grbl_x_accel is not None:
            if abs(grbl_x_accel - config_x_accel) > 0.1:  # Allow small floating point differences
                print(f"  [GRBL] ⚠️  X-axis acceleration mismatch:")
                print(f"  [GRBL]   GRBL $120: {grbl_x_accel:.1f} steps/s²")
                print(f"  [GRBL]   Config:   {config_x_accel:.1f} steps/s²")
                print(f"  [GRBL]   Updating GRBL $120 to {config_x_accel:.1f} steps/s²...")
                
                if self.send_command(f"$120={config_x_accel:.1f}", wait_for_ok=True):
                    print(f"  [GRBL]   ✓ $120 updated successfully")
                    self.grbl_settings['$120'] = config_x_accel
                    settings_updated = True
                else:
                    print(f"  [GRBL]   ✗ Failed to update $120")
            else:
                print(f"  [GRBL] ✓ X-axis acceleration ($120): {grbl_x_accel:.1f} steps/s² (matches config)")
        elif config_x_accel is None:
            print(f"  [GRBL]   ℹ️  X-axis acceleration not configured (skipping check)")
        elif grbl_x_accel is None:
            print(f"  [GRBL]   ⚠️  X-axis acceleration ($120) not received from GRBL")
        
        # Check and update Y-axis acceleration ($121)
        if config_y_accel is not None and grbl_y_accel is not None:
            if abs(grbl_y_accel - config_y_accel) > 0.1:  # Allow small floating point differences
                print(f"  [GRBL] ⚠️  Y-axis acceleration mismatch:")
                print(f"  [GRBL]   GRBL $121: {grbl_y_accel:.1f} steps/s²")
                print(f"  [GRBL]   Config:   {config_y_accel:.1f} steps/s²")
                print(f"  [GRBL]   Updating GRBL $121 to {config_y_accel:.1f} steps/s²...")
                
                if self.send_command(f"$121={config_y_accel:.1f}", wait_for_ok=True):
                    print(f"  [GRBL]   ✓ $121 updated successfully")
                    self.grbl_settings['$121'] = config_y_accel
                    settings_updated = True
                else:
                    print(f"  [GRBL]   ✗ Failed to update $121")
            else:
                print(f"  [GRBL] ✓ Y-axis acceleration ($121): {grbl_y_accel:.1f} steps/s² (matches config)")
        elif config_y_accel is None:
            print(f"  [GRBL]   ℹ️  Y-axis acceleration not configured (skipping check)")
        elif grbl_y_accel is None:
            print(f"  [GRBL]   ⚠️  Y-axis acceleration ($121) not received from GRBL")
        
        if settings_updated:
            print(f"\n  [GRBL] Verifying updated settings...")
            time.sleep(0.5)  # Give GRBL time to process updates
            
            # Re-query the updated settings to verify
            verification_passed = True
            
            # Verify X-axis max rate
            if config_x_max_rate is not None:
                print(f"  [GRBL]   Querying $110 to verify X-axis max rate...")
                time.sleep(0.3)
                try:
                    # Query $110 directly
                    self.serial.write(f"$110\r\n".encode('utf-8'))
                    time.sleep(0.5)  # Wait for response
                    # The response will be processed by _parse_setting
                    # Check if it matches
                    verified_x_rate = self.grbl_settings.get('$110', None)
                    if verified_x_rate is not None:
                        if abs(verified_x_rate - config_x_max_rate) <= 0.1:
                            print(f"  [GRBL]   ✓ $110 verified: {verified_x_rate:.1f} steps/min (matches config)")
                        else:
                            print(f"  [GRBL]   ✗ $110 verification failed: {verified_x_rate:.1f} != {config_x_max_rate:.1f}")
                            verification_passed = False
                    else:
                        print(f"  [GRBL]   ⚠️  $110 response not received")
                except Exception as e:
                    print(f"  [GRBL]   ⚠️  Error verifying $110: {e}")
            
            # Verify Y-axis max rate
            if config_y_max_rate is not None:
                print(f"  [GRBL]   Querying $111 to verify Y-axis max rate...")
                time.sleep(0.3)
                try:
                    # Query $111 directly
                    self.serial.write(f"$111\r\n".encode('utf-8'))
                    time.sleep(0.5)  # Wait for response
                    # The response will be processed by _parse_setting
                    # Check if it matches
                    verified_y_rate = self.grbl_settings.get('$111', None)
                    if verified_y_rate is not None:
                        if abs(verified_y_rate - config_y_max_rate) <= 0.1:
                            print(f"  [GRBL]   ✓ $111 verified: {verified_y_rate:.1f} steps/min (matches config)")
                        else:
                            print(f"  [GRBL]   ✗ $111 verification failed: {verified_y_rate:.1f} != {config_y_max_rate:.1f}")
                            verification_passed = False
                    else:
                        print(f"  [GRBL]   ⚠️  $111 response not received")
                except Exception as e:
                    print(f"  [GRBL]   ⚠️  Error verifying $111: {e}")
            
            # Verify X-axis acceleration
            if config_x_accel is not None:
                print(f"  [GRBL]   Querying $120 to verify X-axis acceleration...")
                time.sleep(0.3)
                try:
                    # Query $120 directly
                    self.serial.write(f"$120\r\n".encode('utf-8'))
                    time.sleep(0.5)  # Wait for response
                    # The response will be processed by _parse_setting
                    # Check if it matches
                    verified_x_accel = self.grbl_settings.get('$120', None)
                    if verified_x_accel is not None:
                        if abs(verified_x_accel - config_x_accel) <= 0.1:
                            print(f"  [GRBL]   ✓ $120 verified: {verified_x_accel:.1f} steps/s² (matches config)")
                        else:
                            print(f"  [GRBL]   ✗ $120 verification failed: {verified_x_accel:.1f} != {config_x_accel:.1f}")
                            verification_passed = False
                    else:
                        print(f"  [GRBL]   ⚠️  $120 response not received")
                except Exception as e:
                    print(f"  [GRBL]   ⚠️  Error verifying $120: {e}")
            
            # Verify Y-axis acceleration
            if config_y_accel is not None:
                print(f"  [GRBL]   Querying $121 to verify Y-axis acceleration...")
                time.sleep(0.3)
                try:
                    # Query $121 directly
                    self.serial.write(f"$121\r\n".encode('utf-8'))
                    time.sleep(0.5)  # Wait for response
                    # The response will be processed by _parse_setting
                    # Check if it matches
                    verified_y_accel = self.grbl_settings.get('$121', None)
                    if verified_y_accel is not None:
                        if abs(verified_y_accel - config_y_accel) <= 0.1:
                            print(f"  [GRBL]   ✓ $121 verified: {verified_y_accel:.1f} steps/s² (matches config)")
                        else:
                            print(f"  [GRBL]   ✗ $121 verification failed: {verified_y_accel:.1f} != {config_y_accel:.1f}")
                            verification_passed = False
                    else:
                        print(f"  [GRBL]   ⚠️  $121 response not received")
                except Exception as e:
                    print(f"  [GRBL]   ⚠️  Error verifying $121: {e}")
            
            if verification_passed:
                print(f"\n  [GRBL] ✓ GRBL settings updated and verified successfully")
                print(f"  [GRBL]   Note: Settings are saved to GRBL's EEPROM automatically")
            else:
                print(f"\n  [GRBL] ⚠️  Settings updated but verification failed")
                print(f"  [GRBL]   You may need to manually verify GRBL settings")
        else:
            print(f"\n  [GRBL] ✓ All GRBL settings match configuration")
        
        print(f"  [GRBL] ========================================\n")

