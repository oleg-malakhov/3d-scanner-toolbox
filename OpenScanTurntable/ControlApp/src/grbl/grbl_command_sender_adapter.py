"""Adapter to make GRBLController implement GRBLCommandSenderInterface."""

from typing import Optional, Callable, Dict
from src.grbl.command_sender_interface import GRBLCommandSenderInterface
from src.grbl.grbl_controller import GRBLController
from src.grbl.constants import MachineState


class GRBLCommandSenderAdapter(GRBLCommandSenderInterface):
    """Adapter to make GRBLController implement GRBLCommandSenderInterface."""
    
    def __init__(self, grbl_controller: GRBLController):
        """
        Initialize adapter.
        
        Args:
            grbl_controller: GRBLController instance to wrap
        """
        self.grbl_controller = grbl_controller
    
    def send_command(self, command: str, wait_for_ok: bool = True) -> bool:
        """Send G-code command to GRBL."""
        return self.grbl_controller.send_command(command, wait_for_ok)
    
    def is_connected(self) -> bool:
        """Check if connected to GRBL."""
        return self.grbl_controller.connected
    
    def wait_for_idle(self, timeout: Optional[float] = None) -> bool:
        """Wait for machine to become idle."""
        return self.grbl_controller.wait_for_idle(timeout)
    
    def unlock(self) -> bool:
        """Unlock GRBL (clear alarm)."""
        return self.grbl_controller.unlock()
    
    def get_machine_state(self) -> MachineState:
        """Get current machine state."""
        return self.grbl_controller.machine_state
    
    def register_status_callback(self, callback: Callable[[MachineState, Dict[str, float]], None]) -> None:
        """Register callback for status updates."""
        self.grbl_controller.register_status_callback(callback)
    
    def get_grbl_x_steps_per_mm(self) -> float:
        """Get GRBL X steps/mm setting."""
        return self.grbl_controller.grbl_x_steps_per_mm
    
    def get_grbl_y_steps_per_mm(self) -> float:
        """Get GRBL Y steps/mm setting."""
        return self.grbl_controller.grbl_y_steps_per_mm
    
    def is_moving(self) -> bool:
        """Check if machine is currently moving."""
        return self.grbl_controller.is_moving()
