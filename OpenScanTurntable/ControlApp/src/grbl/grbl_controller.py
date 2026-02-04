"""GRBL controller - coordinates all components."""

import threading
import time
import logging
from typing import Optional, Callable, Dict

from src.grbl.constants import MachineState, GRBL_MAX_RATE, POSITION_STABLE_THRESHOLD, POSITION_CHANGE_THRESHOLD
from src.grbl.state_manager import StateManager
from src.grbl.serial_connection import SerialConnection
from src.grbl.command_sender import CommandSender
from src.grbl.response_handler import ResponseHandler
from src.grbl.status_manager import StatusManager
from src.grbl.settings_manager import SettingsManager
from src.utils.config import Config


class GRBLController:
    """
    Main GRBL controller - coordinates all components.
    
    This class acts as a facade, maintaining the public API while delegating
    to specialized components for better maintainability.
    """
    
    def __init__(self, config: Config):
        """
        Initialize GRBL controller with all components.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.state_manager = StateManager()
        self.serial_connection = SerialConnection(config)
        self.response_handler = ResponseHandler()
        self.command_sender = CommandSender(
            self.serial_connection,
            config.get('serial.command_retry', {}),
            self.response_handler
        )
        self.status_manager = StatusManager(
            self.serial_connection,
            self.command_sender,
            self.state_manager,
            config.get('grbl.status_poll_interval', 0.1)
        )
        self.settings_manager = SettingsManager(
            self.command_sender,
            self.response_handler,
            config
        )
        
        # Read thread for processing responses
        self.read_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Connect response handler to read loop
        # (responses will be processed in _read_loop)
    
    # Public API - Properties (maintains backward compatibility)
    
    @property
    def connected(self) -> bool:
        """Get connection state."""
        return self.state_manager.connected
    
    @property
    def machine_state(self) -> MachineState:
        """Get machine state."""
        return self.state_manager.machine_state
    
    @property
    def current_position(self) -> Dict[str, float]:
        """Get current position."""
        return self.state_manager.current_position
    
    @property
    def grbl_x_steps_per_mm(self) -> float:
        """Get GRBL X steps/mm."""
        return self.settings_manager.grbl_x_steps_per_mm
    
    @property
    def grbl_y_steps_per_mm(self) -> float:
        """Get GRBL Y steps/mm."""
        return self.settings_manager.grbl_y_steps_per_mm
    
    # Public API - Connection Management
    
    def connect(self, port: Optional[str] = None, auto_detect: bool = True) -> bool:
        """
        Connect to GRBL device.
        
        Args:
            port: Serial port name. If None and auto_detect is True, will auto-detect.
            auto_detect: If True, automatically find GRBL device.
            
        Returns:
            True if connected successfully, False otherwise
        """
        if self.serial_connection.connect(port, auto_detect):
            self.state_manager.connected = True
            self._initialize_grbl()
            
            # Start read thread
            self.running = True
            self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.read_thread.start()
            
            # Start status polling
            self.status_manager.start()
            
            # Retrieve and configure settings
            time.sleep(0.5)  # Give threads time to start
            self.settings_manager.retrieve_settings()
            time.sleep(0.5)  # Give time for settings to be received
            self._configure_grbl_steps()
            
            return True
        return False
    
    def disconnect(self) -> None:
        """Disconnect from GRBL device."""
        self.running = False
        self.status_manager.stop()
        
        # Wait for read thread
        if self.read_thread and self.read_thread.is_alive():
            self.read_thread.join(timeout=1.0)
        
        self.serial_connection.disconnect()
        self.state_manager.connected = False
        self.response_handler.clear_pending()
    
    def _initialize_grbl(self) -> None:
        """Send initialization commands to GRBL."""
        init_commands = self.config.get('grbl.init_commands', ['$X', 'G90', 'G21', 'G54'])
        
        command_explanations = {
            '$X': 'Kill Alarm Lock',
            'G90': 'Absolute Positioning Mode',
            'G91': 'Incremental Positioning Mode',
            'G20': 'Inch Units',
            'G21': 'Millimeter Units',
            'G54': 'Work Coordinate System 1',
            'G92': 'Set Work Coordinate Offset',
        }
        
        self.logger.info("Initializing GRBL...")
        for cmd in init_commands:
            try:
                explanation = command_explanations.get(cmd, 'Unknown command')
                self.logger.debug(f"Sending: {cmd} → {explanation}")
                self.serial_connection.write(f"{cmd}\r\n".encode('utf-8'))
                time.sleep(0.2)
            except Exception as e:
                self.logger.error(f"Error sending {cmd}: {e}")
        
        # Query settings
        self.logger.debug("Querying GRBL settings...")
        time.sleep(0.3)
        try:
            self.serial_connection.write(b'$\r\n')
            time.sleep(0.5)
        except Exception as e:
            self.logger.error(f"Error querying settings: {e}")
        
        # Query position
        time.sleep(0.3)
        self.logger.debug("Querying initial position...")
        try:
            self.serial_connection.write(b'?')
            time.sleep(0.5)
        except Exception as e:
            self.logger.error(f"Error querying position: {e}")
        
        # Align coordinate system
        self.logger.debug("Aligning work coordinate system...")
        time.sleep(0.3)
        try:
            self.logger.debug("Sending: G92 X0 Y0 → Set Work Coordinate Offset")
            self.serial_connection.write(b'G92 X0 Y0\r\n')
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
    
    # Public API - Command Sending
    
    def send_command(self, command: str, wait_for_ok: bool = True) -> bool:
        """
        Send G-code command to GRBL.
        
        Args:
            command: G-code command string
            wait_for_ok: If True, wait for OK response before returning
            
        Returns:
            True if command sent successfully (and OK received if wait_for_ok), False otherwise
        """
        # Check if GRBL is in alarm state
        current_state = self.state_manager.machine_state
        if current_state == MachineState.ALARM and not command.strip().startswith('$X'):
            self.logger.warning(f"GRBL is in alarm state, command may be rejected: {command.strip()}")
            return False
        
        if wait_for_ok:
            waiter = self.response_handler.create_response_waiter()
            self.response_handler.register_command(waiter.sequence, command)
            return self.command_sender.send_command(command, True, waiter)
        else:
            return self.command_sender.send_command(command, False)
    
    # Public API - Movement Commands
    
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
        current_pos = self.state_manager.current_position
        self.logger.debug(f"Current position (MPos units): X={current_pos.get('x', 0):.6f}, Y={current_pos.get('y', 0):.6f}")
        
        cmd_parts = ['G0']
        
        # Convert steps to units for GRBL
        if x is not None:
            if self.settings_manager.grbl_x_steps_per_mm == 0:
                self.logger.error("GRBL X steps/mm is zero - cannot convert")
                return False
            x_units = x / self.settings_manager.grbl_x_steps_per_mm
            cmd_parts.append(f'X{x_units:.3f}')
            self.logger.debug(f"Target X: {x:.6f} steps → {x_units:.6f} units")
        
        if y is not None:
            if self.settings_manager.grbl_y_steps_per_mm == 0:
                self.logger.error("GRBL Y steps/mm is zero - cannot convert")
                return False
            y_units = y / self.settings_manager.grbl_y_steps_per_mm
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
        if self.serial_connection.is_connected():
            try:
                # Emergency stop bypasses the command lock - write directly to serial
                self.serial_connection.write(b'!')  # Feed hold
                time.sleep(0.1)
                
                time.sleep(0.2)  # Give GRBL time to update state
                
                # Query status (bypass lock for emergency)
                status_info = self.query_status(bypass_lock=True)
                if status_info:
                    self.logger.info(f"Emergency stop: GRBL state = {status_info['state']}")
                
                if self.state_manager.machine_state == MachineState.ALARM:
                    self.logger.info("GRBL in alarm state after emergency stop, unlocking...")
                    if self.unlock():
                        self.logger.info("GRBL unlocked successfully")
                        time.sleep(0.2)
                        self.query_status(bypass_lock=True)
                    else:
                        self.logger.warning("Failed to unlock GRBL")
                
                # Resync position
                self.query_status(bypass_lock=True)
                pos = self.state_manager.current_position
                self.logger.info(f"Position after emergency stop: X={pos.get('x', 0):.3f}, Y={pos.get('y', 0):.3f}")
            except Exception as e:
                self.logger.error(f"Error during emergency stop: {e}", exc_info=True)
    
    def unlock(self) -> bool:
        """Unlock GRBL (clear alarm)."""
        return self.send_command('$X')
    
    # Public API - Status and Callbacks
    
    def register_status_callback(self, callback: Callable[[MachineState, Dict[str, float]], None]) -> None:
        """
        Register callback for status updates.
        
        Args:
            callback: Function(state, position) called on status updates
        """
        self.status_manager.register_callback(callback)
    
    def wait_for_idle(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for machine to become idle (movement complete).
        
        Args:
            timeout: Maximum time to wait in seconds. If None, uses 30 seconds.
            
        Returns:
            True if machine became idle, False if timeout
        """
        if not self.state_manager.connected:
            self.logger.warning("wait_for_idle: Not connected")
            return False
        
        start_time = time.time()
        if timeout is None:
            timeout = 30.0
        
        self.logger.debug(f"Waiting for movement to complete (timeout: {timeout:.1f}s)...")
        
        # Get initial state
        initial_state = self.state_manager.machine_state
        self.logger.debug(f"Current machine state: {initial_state.value}")
        
        # If already IDLE, wait briefly to see if movement starts
        if initial_state == MachineState.IDLE:
            wait_for_start_timeout = 1.0
            wait_start = time.time()
            
            while time.time() - wait_start < wait_for_start_timeout:
                current_state = self.state_manager.machine_state
                if current_state != MachineState.IDLE:
                    self.logger.debug(f"Movement started (state: {initial_state.value} → {current_state.value})")
                    break
                time.sleep(0.05)
            else:
                # Still IDLE after waiting
                time.sleep(0.2)
                if self.state_manager.machine_state == MachineState.IDLE:
                    elapsed = time.time() - start_time
                    self.logger.debug(f"Machine remained IDLE (no movement) in {elapsed:.2f}s")
                    return True
        
        # Wait for machine to become IDLE
        last_position = self.state_manager.current_position
        position_stable_count = 0
        last_log_time = time.time()
        
        while time.time() - start_time < timeout:
            current_state = self.state_manager.machine_state
            current_position = self.state_manager.current_position
            
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
                if self.state_manager.machine_state == MachineState.IDLE:
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
        return self.state_manager.machine_state in (MachineState.RUN, MachineState.JOG, MachineState.HOLD)
    
    def query_status(self, bypass_lock: bool = False) -> Optional[Dict[str, Any]]:
        """
        Explicitly query GRBL status and return current state.
        
        Args:
            bypass_lock: If True, bypasses the command lock (for emergency operations)
        
        Returns:
            Dictionary with status information, or None if query failed
        """
        if not self.state_manager.connected or not self.serial_connection.is_connected():
            return None
        
        lock_context = None if bypass_lock else self.command_sender.command_lock
        
        try:
            if lock_context:
                lock_context.acquire()
            
            try:
                # Send status query
                self.serial_connection.write(b'?')
                time.sleep(0.1)
                
                # Try to read status report
                response = self.serial_connection.readline()
                if response and response.startswith('<'):
                    # Process the status report
                    self.status_manager.parse_status_report(response)
                    return {
                        'state': self.state_manager.machine_state.value,
                        'is_moving': self.is_moving(),
                        'position': self.state_manager.current_position,
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
    
    # Internal Methods
    
    def _read_loop(self) -> None:
        """Background thread to read responses from GRBL."""
        while self.running and self.serial_connection.is_connected():
            try:
                line = self.serial_connection.readline()
                if line:
                    self._process_response(line)
                else:
                    time.sleep(0.01)
            except Exception as e:
                if self.running:
                    self.logger.error(f"Read error: {e}", exc_info=True)
                break
    
    def _process_response(self, line: str) -> None:
        """Process response from GRBL."""
        # Status report
        if line.startswith('<') and 'MPos:' in line:
            self.status_manager.parse_status_report(line)
        # Settings response
        elif line.startswith('$') and '=' in line:
            self.settings_manager.parse_setting(line)
        # OK/Error response
        else:
            result = self.response_handler.process_response(line)
            if result is None:
                # Other messages
                self.logger.info(line)
