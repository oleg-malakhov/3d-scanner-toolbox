"""Status polling and parsing for GRBL."""

import threading
import time
import re
import logging
import serial
from typing import Optional, Dict, Any, Callable, List

from src.grbl.constants import MachineState, MAX_CONSECUTIVE_ERRORS, STATUS_POLL_LOCK_TIMEOUT
from src.grbl.state_manager import StateManager
from src.grbl.serial_connection import SerialConnection
from src.grbl.command_sender import CommandSender


class StatusManager:
    """Manages status polling and parsing."""
    
    def __init__(self, serial_connection: SerialConnection, 
                 command_sender: CommandSender,
                 state_manager: StateManager,
                 poll_interval: float):
        """
        Initialize status manager.
        
        Args:
            serial_connection: SerialConnection instance
            command_sender: CommandSender instance
            state_manager: StateManager instance
            poll_interval: Status polling interval in seconds
        """
        self.serial_connection = serial_connection
        self.command_sender = command_sender
        self.state_manager = state_manager
        self.poll_interval = poll_interval
        
        self.logger = logging.getLogger(__name__)
        self.status_thread: Optional[threading.Thread] = None
        self.running = False
        self.status_callbacks: List[Callable[[MachineState, Dict[str, float]], None]] = []
        self._position_logged = False
        self._polling_paused = False
    
    def pause_polling(self) -> None:
        """Temporarily stop sending ? status queries (reduces serial contention)."""
        self._polling_paused = True
    
    def resume_polling(self) -> None:
        """Resume ? status queries after pause_polling()."""
        self._polling_paused = False
    
    def start(self) -> None:
        """Start status polling thread."""
        if self.running:
            return
        self.running = True
        self.status_thread = threading.Thread(target=self._status_loop, daemon=True)
        self.status_thread.start()
        self.logger.debug("Status polling started")
    
    def stop(self) -> None:
        """Stop status polling thread."""
        self.running = False
        if self.status_thread and self.status_thread.is_alive():
            self.status_thread.join(timeout=1.0)
        self.logger.debug("Status polling stopped")
    
    def register_callback(self, callback: Callable[[MachineState, Dict[str, float]], None]) -> None:
        """
        Register callback for status updates.
        
        Args:
            callback: Function(state, position) called on status updates
        """
        self.status_callbacks.append(callback)
    
    def _status_loop(self) -> None:
        """Background thread to poll GRBL status."""
        consecutive_errors = 0
        
        while self.running and self.serial_connection.is_connected():
            try:
                if self._polling_paused:
                    time.sleep(self.poll_interval)
                    continue

                # Try to acquire lock with short timeout
                if self.command_sender.command_lock.acquire(timeout=STATUS_POLL_LOCK_TIMEOUT):
                    try:
                        self.serial_connection.write(b'?')
                        consecutive_errors = 0  # Reset error count on success
                    finally:
                        self.command_sender.command_lock.release()
                
                time.sleep(self.poll_interval)
                
            except serial.SerialTimeoutException as e:
                consecutive_errors += 1
                if self.running:
                    if consecutive_errors <= 3:
                        self.logger.warning(f"Status poll write timeout (attempt {consecutive_errors}): {e}")
                    time.sleep(self.poll_interval * 2)
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    if self.running:
                        self.logger.error(f"Status poll stopped after {MAX_CONSECUTIVE_ERRORS} consecutive timeouts")
                    break
            except serial.SerialException as e:
                consecutive_errors += 1
                if self.running:
                    self.logger.error(f"Status poll serial error: {e}")
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    break
            except Exception as e:
                consecutive_errors += 1
                if self.running:
                    self.logger.error(f"Status poll error: {e}", exc_info=True)
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    break
    
    def parse_status_report(self, status: str) -> None:
        """
        Parse GRBL status report.
        
        Args:
            status: Status report string from GRBL
        """
        old_state = self.state_manager.machine_state
        
        # Extract machine state
        state_match = re.search(r'<([^|>]+)', status)
        if state_match:
            state_str = state_match.group(1).strip()
            if ':' in state_str:
                state_str = state_str.split(':')[0].strip()
            try:
                new_state = MachineState[state_str.upper()]
                self.state_manager.machine_state = new_state
            except KeyError:
                self.logger.warning(f"Unknown state in status report: '{state_str}'")
                self.state_manager.machine_state = MachineState.UNKNOWN
        else:
            self.logger.warning(f"Could not parse state from status report: {status.strip()}")
            self.state_manager.machine_state = MachineState.UNKNOWN
        
        # Log state changes
        if old_state != self.state_manager.machine_state:
            self.logger.debug(f"State changed: {old_state.value} → {self.state_manager.machine_state.value}")
            if old_state == MachineState.RUN and self.state_manager.machine_state == MachineState.IDLE:
                self.logger.info("Movement completed (detected via status report)")
        
        # Extract position
        pos_match = re.search(r'MPos:([0-9.-]+),([0-9.-]+)', status)
        if pos_match:
            try:
                mpos_x_units = float(pos_match.group(1))
                mpos_y_units = float(pos_match.group(2))
                self.state_manager.set_position(mpos_x_units, mpos_y_units)
                
                # Log first position update
                if (mpos_x_units != 0.0 or mpos_y_units != 0.0) and not self._position_logged:
                    self.logger.info(f"Initial position from GRBL: X={mpos_x_units:.6f}, Y={mpos_y_units:.6f}")
                    self._position_logged = True
            except ValueError:
                pass
        
        # Notify callbacks
        for callback in self.status_callbacks:
            try:
                callback(self.state_manager.machine_state, self.state_manager.current_position)
            except Exception as e:
                self.logger.error(f"Error in status callback: {e}", exc_info=True)
