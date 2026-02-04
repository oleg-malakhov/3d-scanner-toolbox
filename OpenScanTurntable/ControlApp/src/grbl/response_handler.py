"""Response parsing and matching for GRBL commands."""

import threading
import logging
import time
from typing import Optional, Dict, Any, Callable, List

from src.grbl.constants import MachineState


class ResponseWaiter:
    """Waits for a command response."""
    
    def __init__(self, sequence: int):
        """
        Initialize response waiter.
        
        Args:
            sequence: Command sequence number
        """
        self.sequence = sequence
        self.event = threading.Event()
        self.result: Optional[bool] = None
    
    def wait(self, timeout: float) -> bool:
        """
        Wait for response.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if response received, False if timeout
        """
        return self.event.wait(timeout=timeout)
    
    def set_result(self, result: bool) -> None:
        """
        Set result and wake waiting thread.
        
        Args:
            result: True for OK, False for error
        """
        self.result = result
        self.event.set()
    
    def get_result(self) -> bool:
        """
        Get result (call after wait returns True).
        
        Returns:
            True if OK, False if error
        """
        return self.result if self.result is not None else False


class ResponseHandler:
    """Handles response parsing and matching to commands."""
    
    def __init__(self):
        """Initialize response handler."""
        self.logger = logging.getLogger(__name__)
        
        self._response_lock = threading.Lock()
        self.command_sequence = 0
        self.pending_commands: Dict[int, Dict[str, Any]] = {}
    
    def create_response_waiter(self) -> ResponseWaiter:
        """
        Create a response waiter for a command.
        
        Returns:
            ResponseWaiter instance that can be used to wait for response
        """
        with self._response_lock:
            seq = self.command_sequence
            self.command_sequence += 1
            
            waiter = ResponseWaiter(seq)
            self.pending_commands[seq] = {
                'command': '',
                'waiter': waiter,
                'timestamp': time.time()
            }
            return waiter
    
    def register_command(self, sequence: int, command: str) -> None:
        """
        Register a command with its sequence number.
        
        Args:
            sequence: Command sequence number
            command: Command string
        """
        with self._response_lock:
            if sequence in self.pending_commands:
                self.pending_commands[sequence]['command'] = command
    
    def process_response(self, line: str) -> Optional[bool]:
        """
        Process a response line from GRBL.
        
        Args:
            line: Response line from GRBL
            
        Returns:
            True if OK response matched, False if error matched, None if not matched
        """
        if 'ok' in line.lower() or 'error' in line.lower():
            # Match to pending command (FIFO)
            with self._response_lock:
                if self.pending_commands:
                    # Get oldest pending command
                    seq = min(self.pending_commands.keys())
                    cmd_info = self.pending_commands[seq]
                    waiter = cmd_info['waiter']
                    
                    if 'ok' in line.lower():
                        result = True
                    else:
                        result = False
                        self.logger.warning(f"GRBL error: {line}")
                    
                    waiter.set_result(result)
                    del self.pending_commands[seq]
                    return result
                else:
                    # No pending command, just log
                    self.logger.debug(f"Response received but no pending command: {line}")
        elif line.startswith('$') and '=' in line:
            # Settings response - return None, handled by SettingsManager
            return None
        else:
            # Other messages (status reports, etc.) - return None
            return None
        
        return None
    
    def clear_pending(self) -> None:
        """Clear all pending commands (used on disconnect)."""
        with self._response_lock:
            self.pending_commands.clear()
