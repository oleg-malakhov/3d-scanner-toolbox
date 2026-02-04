"""Thread-safe state management for GRBL controller."""

import threading
from typing import Dict
from src.grbl.constants import MachineState


class StateManager:
    """
    Manages thread-safe access to GRBL state.
    
    Encapsulates all shared state with proper locking to prevent race conditions.
    This ensures thread safety across all GRBL operations.
    """
    
    def __init__(self):
        """Initialize state manager with default values."""
        # Use RLock for state (allows recursive locking)
        self._state_lock = threading.RLock()
        # Use regular Lock for position (simpler, faster)
        self._position_lock = threading.Lock()
        
        # Initial state
        self._connected = False
        self._machine_state = MachineState.UNKNOWN
        self._current_position = {'x': 0.0, 'y': 0.0}
    
    @property
    def connected(self) -> bool:
        """
        Get connection state (thread-safe).
        
        Returns:
            True if connected, False otherwise
        """
        with self._state_lock:
            return self._connected
    
    @connected.setter
    def connected(self, value: bool) -> None:
        """
        Set connection state (thread-safe).
        
        Args:
            value: True if connected, False otherwise
        """
        with self._state_lock:
            self._connected = value
    
    @property
    def machine_state(self) -> MachineState:
        """
        Get machine state (thread-safe).
        
        Returns:
            Current machine state
        """
        with self._state_lock:
            return self._machine_state
    
    @machine_state.setter
    def machine_state(self, value: MachineState) -> None:
        """
        Set machine state (thread-safe).
        
        Args:
            value: New machine state
        """
        with self._state_lock:
            self._machine_state = value
    
    @property
    def current_position(self) -> Dict[str, float]:
        """
        Get current position (thread-safe copy).
        
        Returns:
            Dictionary with 'x' and 'y' keys containing position in units
        """
        with self._position_lock:
            # Return a copy to prevent external modification
            return self._current_position.copy()
    
    def set_position(self, x: float, y: float) -> None:
        """
        Set current position (thread-safe).
        
        Args:
            x: X position in units
            y: Y position in units
        """
        with self._position_lock:
            self._current_position['x'] = x
            self._current_position['y'] = y
    
    def reset(self) -> None:
        """Reset state to initial values (thread-safe)."""
        with self._state_lock:
            self._connected = False
            self._machine_state = MachineState.UNKNOWN
        
        with self._position_lock:
            self._current_position = {'x': 0.0, 'y': 0.0}
