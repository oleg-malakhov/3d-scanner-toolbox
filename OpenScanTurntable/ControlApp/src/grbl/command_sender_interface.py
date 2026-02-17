"""Interface for sending commands to GRBL (mockable for tests)."""

from abc import ABC, abstractmethod
from typing import Optional


class GRBLCommandSenderInterface(ABC):
    """Interface for sending commands to GRBL (mockable for tests)."""
    
    @abstractmethod
    def send_command(self, command: str, wait_for_ok: bool = True) -> bool:
        """
        Send G-code command to GRBL.
        
        Args:
            command: G-code command string
            wait_for_ok: If True, wait for OK response before returning
            
        Returns:
            True if command sent successfully (and OK received if wait_for_ok), False otherwise
        """
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if connected to GRBL.
        
        Returns:
            True if connected, False otherwise
        """
        pass
    
    @abstractmethod
    def wait_for_idle(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for machine to become idle (movement complete).
        
        Args:
            timeout: Maximum time to wait in seconds. If None, uses default timeout.
            
        Returns:
            True if machine became idle, False if timeout
        """
        pass
    
    @abstractmethod
    def unlock(self) -> bool:
        """
        Unlock GRBL (clear alarm).
        
        Returns:
            True if unlock command sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def get_machine_state(self):
        """
        Get current machine state.
        
        Returns:
            MachineState enum value
        """
        pass
    
    @abstractmethod
    def register_status_callback(self, callback) -> None:
        """
        Register callback for status updates.
        
        Args:
            callback: Function(state, position) called on status updates
        """
        pass
    
    @abstractmethod
    def get_grbl_x_steps_per_mm(self) -> float:
        """
        Get GRBL X steps/mm setting.
        
        Returns:
            Steps per mm for X-axis
        """
        pass
    
    @abstractmethod
    def get_grbl_y_steps_per_mm(self) -> float:
        """
        Get GRBL Y steps/mm setting.
        
        Returns:
            Steps per mm for Y-axis
        """
        pass
    
    @abstractmethod
    def is_moving(self) -> bool:
        """
        Check if machine is currently moving.
        
        Returns:
            True if machine is moving, False if idle
        """
        pass
