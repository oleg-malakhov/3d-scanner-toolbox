"""GRBL controller for communication with GRBL firmware."""

import serial
import threading
import queue
import time
import re
import logging
from typing import Optional, Callable, Dict, Any, List
from enum import Enum

from src.utils.config import Config
from src.utils.serial_utils import find_grbl_device, list_serial_ports

# Hardcoded GRBL max rate (applied to both axes on connection)
GRBL_MAX_RATE = 15000.0  # steps/min

# Constants
RX_BUFFER_SIZE = 128  # GRBL's default receive buffer size
AVG_COMMAND_SIZE = 20  # Average command size for buffer accounting
RESPONSE_TIMEOUT = 5.0  # Timeout for waiting for OK response
MAX_CONSECUTIVE_ERRORS = 10  # Max errors before stopping status polling
STATUS_POLL_LOCK_TIMEOUT = 0.01  # 10ms timeout for status poll lock
POSITION_STABLE_THRESHOLD = 5  # Number of checks for position stability
POSITION_CHANGE_THRESHOLD = 0.001  # Minimum position change to consider movement


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
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Serial connection
        self.serial: Optional[serial.Serial] = None
        
        # Thread synchronization locks
        self._state_lock = threading.RLock()  # For connected, machine_state
        self._position_lock = threading.Lock()  # For current_position
        self.command_lock = threading.Lock()  # For command sending
        self._response_lock = threading.Lock()  # For response matching
        
        # State (protected by locks)
        self._connected = False
        self._machine_state = MachineState.UNKNOWN
        self._current_position = {'x': 0.0, 'y': 0.0}
        
        # Command/response tracking
        self.response_queue = queue.Queue()
        self.status_callbacks: List[Callable[[MachineState, Dict[str, float]], None]] = []
        
        # Response matching (CRITICAL for REST API reliability)
        self.command_sequence = 0
        self.pending_commands: Dict[int, Dict[str, Any]] = {}  # {seq: {'command': str, 'event': Event, 'result': bool}}
        
        # Buffer tracking (prevents overflow)
        self.rx_buffer_used = 0  # Characters currently in GRBL's RX buffer
        
        # GRBL settings (tracked from responses)
        self.grbl_x_steps_per_mm = 1.0  # Default, will be updated from GRBL
        self.grbl_y_steps_per_mm = 1.0  # Default, will be updated from GRBL
        self.grbl_settings: Dict[str, float] = {}  # Store all GRBL settings
        self.settings_received = threading.Event()  # Signal when settings are received
        
        # Threading
        self.read_thread: Optional[threading.Thread] = None
        self.status_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Configuration
        self.baud_rate = config.get('serial.baud_rate', 115200)
        self.timeout = config.get('serial.timeout', 1.0)
        self.status_poll_interval = config.get('grbl.status_poll_interval', 0.1)
        
        # Retry configuration
        retry_config = config.get('serial.command_retry', {})
        self.retry_enabled = retry_config.get('enabled', True)
        self.max_retries = retry_config.get('max_retries', 3)
        self.retry_delay = retry_config.get('retry_delay', 0.1)
    
    @property
    def connected(self) -> bool:
        """Get connection state (thread-safe)."""
        with self._state_lock:
            return self._connected
    
    @connected.setter
    def connected(self, value: bool) -> None:
        """Set connection state (thread-safe)."""
        with self._state_lock:
            self._connected = value
    
    @property
    def machine_state(self) -> MachineState:
        """Get machine state (thread-safe)."""
        with self._state_lock:
            return self._machine_state
    
    @machine_state.setter
    def machine_state(self, value: MachineState) -> None:
        """Set machine state (thread-safe)."""
        with self._state_lock:
            self._machine_state = value
    
    @property
    def current_position(self) -> Dict[str, float]:
        """Get current position (thread-safe copy)."""
        with self._position_lock:
            return self._current_position.copy()
    
    def _set_current_position(self, x: float, y: float) -> None:
        """Set current position (thread-safe)."""
        with self._position_lock:
            self._current_position['x'] = x
            self._current_position['y'] = y
    
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
            
            # Mark as connected (thread-safe)
            self.connected = True
            
            # Retrieve and display GRBL settings
            time.sleep(0.5)  # Give threads time to start
            self._retrieve_and_display_settings()
            
            # Configure GRBL for direct step control
            time.sleep(0.5)  # Give time for settings to be received
            self._configure_grbl_steps()
            
            self._notify_status(f"Connected to {port}")
            return True
            
        except (serial.SerialException, OSError) as e:
            self._notify_status(f"Connection error: {e}")
            if self.serial:
                try:
                    self.serial.close()
                except Exception as close_error:
                    self.logger.error(f"Error closing serial port: {close_error}")
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
            except Exception as e:
                self.logger.error(f"Error closing serial port during disconnect: {e}")
            self.serial = None
        
        # Clear pending commands
        with self._response_lock:
            self.pending_commands.clear()
        
        self._notify_status("Disconnected")
    
    def _initialize_grbl(self) -> None:
        """Send initialization commands to GRBL."""
        init_commands = self.config.get('grbl.init_commands', ['$X', 'G90', 'G21', 'G54'])
        
        # Command explanations
        command_explanations = {
            '$X': 'Kill Alarm Lock - Unlocks GRBL if it\'s in an alarm state',
            'G90': 'Absolute Positioning Mode - All coordinates are absolute',
            'G91': 'Incremental Positioning Mode - All coordinates are relative',
            'G20': 'Inch Units - Positions reported in inches',
            'G21': 'Millimeter Units - Positions reported in millimeters',
            'G54': 'Work Coordinate System 1 - Use work coordinate system G54',
            'G55': 'Work Coordinate System 2',
            'G56': 'Work Coordinate System 3',
            'G57': 'Work Coordinate System 4',
            'G58': 'Work Coordinate System 5',
            'G59': 'Work Coordinate System 6',
            'G92': 'Set Work Coordinate Offset - Sets current position as origin',
            'G28': 'Go to Predefined Position 1',
            'G30': 'Go to Predefined Position 2',
        }
        
        self.logger.info("Initializing GRBL...")
        for cmd in init_commands:
            try:
                explanation = command_explanations.get(cmd, 'Unknown command')
                self.logger.debug(f"Sending: {cmd} → {explanation}")
                self.serial.write(f"{cmd}\r\n".encode('utf-8'))
                time.sleep(0.2)  # Give GRBL time to process
            except Exception as e:
                self.logger.error(f"Error sending {cmd}: {e}")
        
        # Query GRBL settings
        self.logger.debug("Querying GRBL settings...")
        time.sleep(0.3)
        try:
            self.serial.write(b'$\r\n')  # Request all settings
            time.sleep(0.5)
        except Exception as e:
            self.logger.error(f"Error querying settings: {e}")
        
        # Query current position
        time.sleep(0.3)
        self.logger.debug("Querying initial position...")
        try:
            self.serial.write(b'?')
            time.sleep(0.5)
        except Exception as e:
            self.logger.error(f"Error querying position: {e}")
        
        # Align work coordinate system
        self.logger.debug("Aligning work coordinate system...")
        time.sleep(0.3)
        try:
            self.logger.debug("Sending: G92 X0 Y0 → Set Work Coordinate Offset")
            self.serial.write(b'G92 X0 Y0\r\n')
            time.sleep(0.2)
        except Exception as e:
            self.logger.error(f"Error aligning coordinate system: {e}")
        
        self.logger.info("GRBL initialization complete. Verify $100 and $101 are 1.0 for direct step control.")
    
    def _configure_grbl_steps(self) -> None:
        """Configure GRBL steps/mm settings for direct step control."""
        self.logger.info("Auto-configuring GRBL for direct step control...")
        time.sleep(0.3)
        
        success = True
        try:
            self.logger.debug("Setting $100=1.0 (X-axis: 1 step per unit)")
            if not self.send_command("$100=1.0", wait_for_ok=True):
                self.logger.warning("Failed to set $100")
                success = False
            time.sleep(0.3)
            
            self.logger.debug("Setting $101=1.0 (Y-axis: 1 step per unit)")
            if not self.send_command("$101=1.0", wait_for_ok=True):
                self.logger.warning("Failed to set $101")
                success = False
            time.sleep(0.3)
            
            # Verify settings
            self.logger.debug("Verifying settings...")
            time.sleep(0.3)
            self.send_command("$100", wait_for_ok=False)
            time.sleep(0.3)
            self.send_command("$101", wait_for_ok=False)
            time.sleep(0.3)
            self.send_command("$", wait_for_ok=False)
            time.sleep(0.8)
            
            if success:
                self.logger.info("GRBL configured for direct step control")
            else:
                self.logger.warning("Some settings may not have been applied")
        except Exception as e:
            self.logger.error(f"Error configuring GRBL: {e}")
    
    def send_command(self, command: str, wait_for_ok: bool = True) -> bool:
        """
        Send G-code command to GRBL with retry logic and response matching.
        
        Args:
            command: G-code command string
            wait_for_ok: If True, wait for OK response before returning
            
        Returns:
            True if command sent successfully (and OK received if wait_for_ok), False otherwise
        """
        with self.command_lock:
            if not self.serial or not self.serial.is_open:
                self.logger.error("Serial port not available, cannot send command")
                return False
            
            # Check if GRBL is in alarm state
            current_state = self.machine_state
            if current_state == MachineState.ALARM and not command.strip().startswith('$X'):
                self.logger.warning(f"GRBL is in alarm state, command may be rejected: {command.strip()}")
                return False
            
            # Add line ending if not present
            raw_command = command
            if not command.endswith('\r\n'):
                command = command.rstrip() + '\r\n'
            
            # Calculate command size for buffer tracking
            command_size = len(command.encode('utf-8'))
            
            # Check buffer space (with safety margin)
            if self.rx_buffer_used + command_size > RX_BUFFER_SIZE - 10:
                self.logger.warning("Buffer nearly full, waiting briefly...")
                time.sleep(0.05)
                # Re-check
                if self.rx_buffer_used + command_size > RX_BUFFER_SIZE - 10:
                    self.logger.warning("Buffer still nearly full")
            
            # Get sequence number for response matching
            seq = None
            response_event = None
            if wait_for_ok:
                with self._response_lock:
                    seq = self.command_sequence
                    self.command_sequence += 1
                    response_event = threading.Event()
                    self.pending_commands[seq] = {
                        'command': raw_command.strip(),
                        'event': response_event,
                        'result': None,
                        'timestamp': time.time()
                    }
            
            # Retry loop for write operations
            max_attempts = self.max_retries + 1 if self.retry_enabled else 1
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    if attempt > 1:
                        self.logger.debug(f"Retry attempt {attempt}/{max_attempts} for command: {raw_command.strip()}")
                        time.sleep(self.retry_delay)
                    
                    self.logger.debug(f"Sending command: {raw_command.strip()}")
                    
                    bytes_written = self.serial.write(command.encode('utf-8'))
                    self.rx_buffer_used += command_size
                    
                    # Wait for response if needed
                    if wait_for_ok and response_event:
                        self.logger.debug("Waiting for OK response (timeout: 5s)...")
                        if response_event.wait(timeout=RESPONSE_TIMEOUT):
                            # Response received
                            with self._response_lock:
                                result = self.pending_commands.get(seq, {}).get('result', False)
                                if seq in self.pending_commands:
                                    del self.pending_commands[seq]
                            
                            # Decrease buffer usage (command processed)
                            self.rx_buffer_used = max(0, self.rx_buffer_used - AVG_COMMAND_SIZE)
                            
                            if result:
                                self.logger.debug("Command acknowledged")
                                return True
                            else:
                                self.logger.warning("Command error response")
                                return False
                        else:
                            # Timeout
                            self.logger.warning("Timeout waiting for response")
                            with self._response_lock:
                                if seq in self.pending_commands:
                                    del self.pending_commands[seq]
                            return False
                    
                    # Command sent without waiting for response
                    self.logger.debug("Command sent (not waiting for response)")
                    return True
                    
                except serial.SerialTimeoutException as e:
                    last_exception = e
                    self.logger.warning(f"Write timeout on attempt {attempt}/{max_attempts}: {e}")
                    if attempt < max_attempts:
                        continue
                    else:
                        self._notify_status(f"Error sending command after {max_attempts} attempts: Write timeout")
                        return False
                        
                except serial.SerialException as e:
                    last_exception = e
                    self.logger.error(f"Serial error on attempt {attempt}/{max_attempts}: {e}")
                    if attempt < max_attempts and self.retry_enabled:
                        continue
                    else:
                        self._notify_status(f"Error sending command: Serial error: {e}")
                        return False
                        
                except Exception as e:
                    last_exception = e
                    self.logger.error(f"Exception on attempt {attempt}/{max_attempts}: {e}", exc_info=True)
                    if attempt < max_attempts and self.retry_enabled:
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        self._notify_status(f"Error sending command: {e}")
                        return False
            
            # Cleanup on failure
            if wait_for_ok and seq is not None:
                with self._response_lock:
                    if seq in self.pending_commands:
                        del self.pending_commands[seq]
            
            if last_exception:
                self.logger.error(f"Final exception: {last_exception}")
                self._notify_status(f"Error sending command: {last_exception}")
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
        self.logger.debug("Building move command...")
        current_pos = self.current_position
        self.logger.debug(f"Current position (MPos units): X={current_pos.get('x', 0):.6f}, Y={current_pos.get('y', 0):.6f}")
        
        cmd_parts = ['G0']
        
        # Convert steps to units for GRBL
        if x is not None:
            if self.grbl_x_steps_per_mm == 0:
                self.logger.error("GRBL X steps/mm is zero - cannot convert")
                return False
            x_units = x / self.grbl_x_steps_per_mm
            cmd_parts.append(f'X{x_units:.3f}')
            self.logger.debug(f"Target X: {x:.6f} steps → {x_units:.6f} units")
        
        if y is not None:
            if self.grbl_y_steps_per_mm == 0:
                self.logger.error("GRBL Y steps/mm is zero - cannot convert")
                return False
            y_units = y / self.grbl_y_steps_per_mm
            cmd_parts.append(f'Y{y_units:.3f}')
            self.logger.debug(f"Target Y: {y:.6f} steps → {y_units:.6f} units")
        
        if feedrate is not None:
            cmd_parts.append(f'F{feedrate}')
        
        command = ' '.join(cmd_parts)
        self.logger.debug(f"Final command: {command}")
        return self.send_command(command)
    
    def reset_to_home(self) -> bool:
        """Move to home position."""
        home_x = self.config.get('home_position.x', 0)
        home_y = self.config.get('home_position.y', 0)
        return self.move_to(x=home_x, y=home_y)
    
    def set_current_position_as_origin(self) -> bool:
        """Set current GRBL position as origin (work coordinate offset)."""
        self.logger.debug("Setting current position as origin (G92 X0 Y0)...")
        return self.send_command("G92 X0 Y0", wait_for_ok=True)
    
    def emergency_stop(self) -> None:
        """Send emergency stop command and handle aftermath."""
        if self.serial and self.connected:
            try:
                # Emergency stop bypasses the command lock - write directly to serial
                self.serial.write(b'!')  # Feed hold
                time.sleep(0.1)
                
                time.sleep(0.2)  # Give GRBL time to update state
                
                # Query status (bypass lock for emergency)
                status_info = self.query_status(bypass_lock=True)
                if status_info:
                    self._notify_status(f"Emergency stop: GRBL state = {status_info['state']}")
                
                if self.machine_state == MachineState.ALARM:
                    self._notify_status("GRBL in alarm state after emergency stop, unlocking...")
                    if self.unlock():
                        self._notify_status("GRBL unlocked successfully")
                        time.sleep(0.2)
                        self.query_status(bypass_lock=True)
                    else:
                        self._notify_status("Failed to unlock GRBL")
                
                # Resync position
                self.query_status(bypass_lock=True)
                pos = self.current_position
                self._notify_status(f"Position after emergency stop: X={pos.get('x', 0):.3f}, Y={pos.get('y', 0):.3f}")
            except Exception as e:
                self.logger.error(f"Error during emergency stop: {e}", exc_info=True)
                self._notify_status(f"Error during emergency stop: {e}")
    
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
                    self.logger.error(f"Read error: {e}", exc_info=True)
                    self._notify_status(f"Read error: {e}")
                break
    
    def _status_loop(self) -> None:
        """Background thread to poll GRBL status."""
        consecutive_errors = 0
        
        while self.running and self.serial and self.serial.is_open:
            try:
                # Try to acquire lock with short timeout
                if self.command_lock.acquire(timeout=STATUS_POLL_LOCK_TIMEOUT):
                    try:
                        self.serial.write(b'?')
                        consecutive_errors = 0  # Reset error count on success
                    finally:
                        self.command_lock.release()
                time.sleep(self.status_poll_interval)
            except serial.SerialTimeoutException as e:
                consecutive_errors += 1
                if self.running:
                    if consecutive_errors <= 3:
                        self.logger.warning(f"Status poll write timeout (attempt {consecutive_errors}): {e}")
                    time.sleep(self.status_poll_interval * 2)
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    if self.running:
                        self._notify_status(f"Status poll stopped after {MAX_CONSECUTIVE_ERRORS} consecutive timeouts")
                    break
            except serial.SerialException as e:
                consecutive_errors += 1
                if self.running:
                    self.logger.error(f"Status poll serial error: {e}")
                    self._notify_status(f"Status poll serial error: {e}")
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    break
            except Exception as e:
                consecutive_errors += 1
                if self.running:
                    self.logger.error(f"Status poll error: {e}", exc_info=True)
                    self._notify_status(f"Status poll error: {e}")
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    break
    
    def _process_response(self, line: str) -> None:
        """Process response from GRBL."""
        # Status report format: <Idle|Run|...>,MPos:X.xxx,Y.yyy,...
        if line.startswith('<') and 'MPos:' in line:
            self._parse_status_report(line)
        elif 'ok' in line.lower() or 'error' in line.lower():
            # Match response to pending command (FIFO)
            with self._response_lock:
                if self.pending_commands:
                    # Get oldest pending command
                    seq = min(self.pending_commands.keys())
                    cmd_info = self.pending_commands[seq]
                    
                    if 'ok' in line.lower():
                        cmd_info['result'] = True
                    else:
                        cmd_info['result'] = False
                        self._notify_status(f"GRBL error: {line}")
                    
                    # Wake up waiting thread
                    cmd_info['event'].set()
                else:
                    # No pending command, just log
                    self.response_queue.put(line)
        elif line.startswith('$') and '=' in line:
            # GRBL settings response
            self._parse_setting(line)
        else:
            # Other messages
            self._notify_status(line)
    
    def _parse_status_report(self, status: str) -> None:
        """Parse GRBL status report."""
        old_state = self.machine_state
        
        # Extract machine state
        state_match = re.search(r'<([^|>]+)', status)
        if state_match:
            state_str = state_match.group(1).strip()
            if ':' in state_str:
                state_str = state_str.split(':')[0].strip()
            try:
                new_state = MachineState[state_str.upper()]
                self.machine_state = new_state
            except KeyError:
                self.logger.warning(f"Unknown state in status report: '{state_str}'")
                self.machine_state = MachineState.UNKNOWN
        else:
            self.logger.warning(f"Could not parse state from status report: {status.strip()}")
            self.machine_state = MachineState.UNKNOWN
        
        # Log state changes
        if old_state != self.machine_state:
            self.logger.debug(f"State changed: {old_state.value} → {self.machine_state.value}")
            if old_state == MachineState.RUN and self.machine_state == MachineState.IDLE:
                self.logger.info("Movement completed (detected via status report)")
        
        # Extract position
        pos_match = re.search(r'MPos:([0-9.-]+),([0-9.-]+)', status)
        if pos_match:
            try:
                mpos_x_units = float(pos_match.group(1))
                mpos_y_units = float(pos_match.group(2))
                self._set_current_position(mpos_x_units, mpos_y_units)
                
                # Log first position update
                if mpos_x_units != 0.0 or mpos_y_units != 0.0:
                    if not hasattr(self, '_position_logged'):
                        self.logger.info(f"Initial position from GRBL: X={mpos_x_units:.6f}, Y={mpos_y_units:.6f}")
                        self._position_logged = True
            except ValueError:
                pass
        
        # Notify callbacks
        for callback in self.status_callbacks:
            try:
                callback(self.machine_state, self.current_position)
            except Exception as e:
                self.logger.error(f"Error in status callback: {e}", exc_info=True)
    
    def register_status_callback(self, callback: Callable[[MachineState, Dict[str, float]], None]) -> None:
        """Register callback for status updates."""
        self.status_callbacks.append(callback)
    
    def _notify_status(self, message: str) -> None:
        """Notify status message (console only, not UI)."""
        self.logger.info(message)
    
    def wait_for_idle(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for machine to become idle (movement complete).
        
        Args:
            timeout: Maximum time to wait in seconds. If None, uses 30 seconds.
            
        Returns:
            True if machine became idle, False if timeout
        """
        if not self.connected:
            self.logger.warning("wait_for_idle: Not connected")
            return False
        
        start_time = time.time()
        if timeout is None:
            timeout = 30.0
        
        self.logger.debug(f"Waiting for movement to complete (timeout: {timeout:.1f}s)...")
        
        # Get initial state
        initial_state = self.machine_state
        self.logger.debug(f"Current machine state: {initial_state.value}")
        
        # If already IDLE, wait briefly to see if movement starts
        if initial_state == MachineState.IDLE:
            wait_for_start_timeout = 1.0
            wait_start = time.time()
            
            while time.time() - wait_start < wait_for_start_timeout:
                current_state = self.machine_state
                if current_state != MachineState.IDLE:
                    self.logger.debug(f"Movement started (state: {initial_state.value} → {current_state.value})")
                    break
                time.sleep(0.05)
            else:
                # Still IDLE after waiting
                time.sleep(0.2)
                if self.machine_state == MachineState.IDLE:
                    elapsed = time.time() - start_time
                    self.logger.debug(f"Machine remained IDLE (no movement) in {elapsed:.2f}s")
                    return True
        
        # Wait for machine to become IDLE
        last_position = self.current_position
        position_stable_count = 0
        last_log_time = time.time()
        
        while time.time() - start_time < timeout:
            current_state = self.machine_state
            current_position = self.current_position
            
            # Check position stability
            pos_changed = (abs(current_position.get('x', 0) - last_position.get('x', 0)) > POSITION_CHANGE_THRESHOLD or
                          abs(current_position.get('y', 0) - last_position.get('y', 0)) > POSITION_CHANGE_THRESHOLD)
            
            if pos_changed:
                position_stable_count = 0
                last_position = current_position
            else:
                position_stable_count += 1
                # If position stable and IDLE, movement complete
                if position_stable_count >= POSITION_STABLE_THRESHOLD and current_state == MachineState.IDLE:
                    elapsed = time.time() - start_time
                    self.logger.debug(f"Movement completed (position stable + IDLE) in {elapsed:.2f}s")
                    return True
            
            # Check machine state
            if current_state == MachineState.IDLE:
                # Verify IDLE for a brief moment
                time.sleep(0.1)
                if self.machine_state == MachineState.IDLE:
                    elapsed = time.time() - start_time
                    self.logger.debug(f"Movement completed in {elapsed:.2f}s")
                    return True
            elif current_state == MachineState.ALARM:
                self.logger.warning("Machine in alarm state")
                return False
            
            # Log periodically
            if time.time() - last_log_time >= 2.0:
                elapsed = time.time() - start_time
                self.logger.debug(f"Still waiting... (elapsed: {elapsed:.1f}s, state: {current_state.value})")
                last_log_time = time.time()
            
            time.sleep(0.05)  # 50ms polling interval
        
        # Timeout
        elapsed = time.time() - start_time
        self.logger.warning(f"Timeout waiting for movement ({elapsed:.1f}s)")
        return False
    
    def is_moving(self) -> bool:
        """Check if machine is currently moving."""
        return self.machine_state in (MachineState.RUN, MachineState.JOG, MachineState.HOLD)
    
    def query_status(self, bypass_lock: bool = False) -> Optional[Dict[str, Any]]:
        """
        Explicitly query GRBL status and return current state.
        
        Args:
            bypass_lock: If True, bypasses the command lock (for emergency operations)
        
        Returns:
            Dictionary with status information, or None if query failed
        """
        if not self.connected or not self.serial or not self.serial.is_open:
            return None
        
        lock_context = None if bypass_lock else self.command_lock
        
        try:
            if lock_context:
                lock_context.acquire()
            
            try:
                # Clear any pending responses
                while not self.response_queue.empty():
                    try:
                        self.response_queue.get_nowait()
                    except queue.Empty:
                        break
                
                # Send status query
                self.serial.write(b'?')
                time.sleep(0.1)
                
                # Try to read status report
                if self.serial.in_waiting > 0:
                    response = self.serial.readline().decode('utf-8', errors='ignore').strip()
                    if response.startswith('<'):
                        self._process_response(response)
                        return {
                            'state': self.machine_state.value,
                            'is_moving': self.is_moving(),
                            'position': self.current_position,
                            'raw_status': response
                        }
            finally:
                if lock_context:
                    lock_context.release()
        except Exception as e:
            self.logger.error(f"Error querying status: {e}", exc_info=True)
            if lock_context:
                try:
                    lock_context.release()
                except Exception:
                    pass
        
        return None
    
    def _parse_setting(self, line: str) -> None:
        """Parse a GRBL setting line and store it."""
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
        except (ValueError, IndexError) as e:
            self.logger.debug(f"Error parsing setting line '{line}': {e}")
    
    def _retrieve_and_display_settings(self) -> None:
        """Retrieve all GRBL settings and display with interpretation."""
        self.logger.info("Retrieving GRBL Settings...")
        
        # Clear previous settings
        self.grbl_settings = {}
        self.settings_received.clear()
        
        # Request all settings
        try:
            self.send_command("$$", wait_for_ok=False)
        except Exception as e:
            self.logger.error(f"Error requesting settings: {e}")
            return
        
        # Wait for first setting to arrive
        if self.settings_received.wait(timeout=3.0):
            time.sleep(1.5)  # Give time for all settings to arrive
            self._display_settings_interpretation()
            self._check_and_update_grbl_settings()
        else:
            self.logger.warning("Timeout waiting for settings response")
            if self.grbl_settings:
                self._display_settings_interpretation()
                self._check_and_update_grbl_settings()
            else:
                self.logger.warning("No settings received. Check GRBL connection.")
    
    def _display_settings_interpretation(self) -> None:
        """Display GRBL settings with detailed interpretation."""
        self.logger.info("All GRBL Settings with Interpretation")
        
        # All GRBL settings with descriptions (abbreviated for brevity)
        all_settings = {
            '$0': ('Step Pulse Time', 'microseconds', 'Minimum step pulse width'),
            '$1': ('Step Idle Delay', 'milliseconds', 'Delay before disabling steppers'),
            '$100': ('X-axis Steps/Unit', 'steps/unit', 'CRITICAL: Should be 1.0'),
            '$101': ('Y-axis Steps/Unit', 'steps/unit', 'CRITICAL: Should be 1.0'),
            '$110': ('X-axis Max Rate', 'steps/min', 'CRITICAL: Maximum speed limit'),
            '$111': ('Y-axis Max Rate', 'steps/min', 'CRITICAL: Maximum speed limit'),
            '$120': ('X-axis Acceleration', 'steps/s²', 'CRITICAL: Acceleration rate'),
            '$121': ('Y-axis Acceleration', 'steps/s²', 'CRITICAL: Acceleration rate'),
        }
        
        # Display critical settings
        self.logger.info("Critical Settings:")
        for setting_key in ['$100', '$101', '$110', '$111', '$120', '$121']:
            if setting_key in all_settings:
                name, unit, description = all_settings[setting_key]
                value = self.grbl_settings.get(setting_key)
                if value is not None:
                    self.logger.info(f"  {setting_key:6} = {value:10.3f} {unit:12} - {name}")
                    self.logger.info(f"          {description}")
        
        # Check steps/unit settings
        x_steps = self.grbl_settings.get('$100', 1.0)
        y_steps = self.grbl_settings.get('$101', 1.0)
        
        if abs(x_steps - 1.0) > 0.001:
            self.logger.warning(f"$100 = {x_steps:.3f} (should be 1.0) - This will cause incorrect positioning!")
        else:
            self.logger.info(f"$100 = {x_steps:.3f} (correct)")
        
        if abs(y_steps - 1.0) > 0.001:
            self.logger.warning(f"$101 = {y_steps:.3f} (should be 1.0) - This will cause incorrect positioning!")
        else:
            self.logger.info(f"$101 = {y_steps:.3f} (correct)")
    
    def _check_and_update_grbl_settings(self) -> None:
        """Check if GRBL settings match configuration and update if needed."""
        self.logger.info("Checking GRBL Settings Against Configuration...")
        
        config_x_max_rate = GRBL_MAX_RATE
        config_y_max_rate = GRBL_MAX_RATE
        config_x_accel = self.config.get('motors.x_axis.acceleration', None)
        config_y_accel = self.config.get('motors.y_axis.acceleration', None)
        
        grbl_x_max_rate = self.grbl_settings.get('$110', None)
        grbl_y_max_rate = self.grbl_settings.get('$111', None)
        grbl_x_accel = self.grbl_settings.get('$120', None)
        grbl_y_accel = self.grbl_settings.get('$121', None)
        
        settings_updated = False
        
        # Check and update X-axis max rate
        if grbl_x_max_rate is not None:
            if abs(grbl_x_max_rate - config_x_max_rate) > 0.1:
                self.logger.info(f"Updating $110 from {grbl_x_max_rate:.1f} to {config_x_max_rate:.1f}")
                if self.send_command(f"$110={config_x_max_rate:.1f}", wait_for_ok=True):
                    self.grbl_settings['$110'] = config_x_max_rate
                    settings_updated = True
            else:
                self.logger.debug(f"$110 matches: {grbl_x_max_rate:.1f}")
        
        # Check and update Y-axis max rate
        if grbl_y_max_rate is not None:
            if abs(grbl_y_max_rate - config_y_max_rate) > 0.1:
                self.logger.info(f"Updating $111 from {grbl_y_max_rate:.1f} to {config_y_max_rate:.1f}")
                if self.send_command(f"$111={config_y_max_rate:.1f}", wait_for_ok=True):
                    self.grbl_settings['$111'] = config_y_max_rate
                    settings_updated = True
            else:
                self.logger.debug(f"$111 matches: {grbl_y_max_rate:.1f}")
        
        # Check and update accelerations
        if config_x_accel is not None and grbl_x_accel is not None:
            if abs(grbl_x_accel - config_x_accel) > 0.1:
                self.logger.info(f"Updating $120 from {grbl_x_accel:.1f} to {config_x_accel:.1f}")
                if self.send_command(f"$120={config_x_accel:.1f}", wait_for_ok=True):
                    self.grbl_settings['$120'] = config_x_accel
                    settings_updated = True
        
        if config_y_accel is not None and grbl_y_accel is not None:
            if abs(grbl_y_accel - config_y_accel) > 0.1:
                self.logger.info(f"Updating $121 from {grbl_y_accel:.1f} to {config_y_accel:.1f}")
                if self.send_command(f"$121={config_y_accel:.1f}", wait_for_ok=True):
                    self.grbl_settings['$121'] = config_y_accel
                    settings_updated = True
        
        if settings_updated:
            self.logger.info("GRBL settings updated successfully")
        else:
            self.logger.info("All GRBL settings match configuration")
