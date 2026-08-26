"""Axis classes for handling individual axis operations and conversions."""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Tuple, Optional, Callable, Dict
from src.grbl.command_sender_interface import GRBLCommandSenderInterface
from src.grbl.command_builder import GRBLCommandBuilder
from src.grbl.constants import MachineState, GRBL_MAX_RATE


@dataclass
class AxisConfig:
    """Configuration for an axis."""
    step_angle: float              # Degrees per full step (e.g., 1.8)
    microsteps: int                # Microsteps per full step (0 = disabled, 8, 16, etc.)
    min_angle: float               # Minimum angle in degrees
    max_angle: float               # Maximum angle in degrees
    speed: int                     # Movement speed/feedrate (steps/min)
    acceleration: float            # GRBL acceleration setting ($120/$121)
    always_on: bool                # Keep motor energized
    home_angle: float              # Home position in degrees (default: 0)
    grbl_axis_letter: str          # GRBL axis letter ('X' or 'Y')
    grbl_steps_per_mm: float       # GRBL's $100 or $101 setting (default: 1.0)
    gear_ratio: float = 1.0        # Gear ratio multiplier (motor steps multiplier)


class BaseAxis(ABC):
    """Abstract base class for all axes with shared logic."""
    
    def __init__(self, 
                 command_sender: GRBLCommandSenderInterface,
                 config: AxisConfig, 
                 message_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize axis.
        
        Args:
            command_sender: GRBL command sender interface (mockable for tests)
            config: Axis configuration
            message_callback: Optional callback function to receive log messages
        """
        self.command_sender = command_sender
        self.config = config
        self.message_callback = message_callback
        
        # Calculate steps per degree
        self._steps_per_degree = self._calculate_steps_per_degree()
        
        # Current position in degrees (cached from GRBL updates)
        self._current_angle = config.home_angle
        
        # Register for GRBL status updates
        self.command_sender.register_status_callback(self._on_grbl_status_update)
    
    # Abstract properties (must be implemented by subclasses)
    
    @property
    @abstractmethod
    def grbl_axis_letter(self) -> str:
        """GRBL axis letter ('X' or 'Y')."""
        pass
    
    @property
    @abstractmethod
    def position_key(self) -> str:
        """Key for position dict ('x' or 'y')."""
        pass
    
    @property
    def grbl_steps_per_mm(self) -> float:
        """Get GRBL steps/mm setting for this axis."""
        if self.grbl_axis_letter == 'X':
            return self.command_sender.get_grbl_x_steps_per_mm()
        else:
            return self.command_sender.get_grbl_y_steps_per_mm()
    
    # Abstract methods (must be implemented by subclasses)
    
    @abstractmethod
    def _normalize_target_angle(self, desired_angle: float) -> float:
        """
        Normalize target angle to valid range (axis-specific).
        
        Args:
            desired_angle: Desired target angle
            
        Returns:
            Normalized target angle
        """
        pass
    
    @abstractmethod
    def validate_angle(self, degrees: float) -> Tuple[bool, Optional[str]]:
        """
        Validate if angle is within limits (axis-specific).
        
        Args:
            degrees: Angle to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        pass
    
    # Default implementation (can be overridden)
    
    def _calculate_shortest_path(self, current_angle: float, target_angle: float) -> float:
        """
        Calculate shortest path to target angle (default: no wrapping).
        
        Args:
            current_angle: Current angle in degrees
            target_angle: Target angle in degrees
            
        Returns:
            Target angle (no modification for limited range axes)
        """
        return target_angle
    
    # Shared calculation methods (pure functions, testable)
    
    def _log(self, message: str) -> None:
        """Log a message (print to console and send to callback if available)."""
        axis_name = self.grbl_axis_letter
        print(message)
        if self.message_callback:
            self.message_callback(message)
    
    def _calculate_steps_per_degree(self) -> float:
        """Calculate steps per degree based on step_angle and microsteps."""
        # If microsteps is 0 or less, microstepping is disabled (use full steps only)
        if self.config.microsteps <= 0:
            microsteps = 1
        else:
            microsteps = self.config.microsteps
        
        # Calculation: (360 / step_angle) * microsteps / 360
        full_steps_per_rev = 360.0 / self.config.step_angle
        total_steps_per_rev = full_steps_per_rev * microsteps
        steps_per_degree = total_steps_per_rev / 360.0
        
        return steps_per_degree
    
    def _degrees_to_steps(self, degrees: float) -> float:
        """Convert degrees to motor steps (accounting for gear ratio)."""
        # Multiply by gear_ratio: if gear_ratio > 1, motor needs more steps
        # Example: gear_ratio = 5.333 means motor turns 5.333x for same output angle
        return degrees * self._steps_per_degree * self.config.gear_ratio
    
    def _steps_to_degrees(self, steps: float) -> float:
        """Convert motor steps to degrees (accounting for gear ratio)."""
        # Divide by gear_ratio: if gear_ratio > 1, fewer degrees per step
        return steps / (self._steps_per_degree * self.config.gear_ratio)
    
    def _steps_to_grbl_units(self, steps: float) -> float:
        """Convert steps to GRBL units (accounting for $100/$101)."""
        # GRBL calculates: actual_steps = units × $100 (or $101)
        # We want: actual_steps = steps
        # So: units = steps / $100
        grbl_steps_per_mm = self.grbl_steps_per_mm
        return steps / grbl_steps_per_mm
    
    def _grbl_units_to_steps(self, units: float) -> float:
        """Convert GRBL units to steps (accounting for $100/$101)."""
        # GRBL reports MPos in units
        # actual_steps = units × $100 (or $101)
        grbl_steps_per_mm = self.grbl_steps_per_mm
        return units * grbl_steps_per_mm
    
    def _on_grbl_status_update(self, state, position: Dict[str, float]) -> None:
        """Update internal position from GRBL status."""
        # Get position in units from GRBL (MPos)
        # Position dict contains 'x' and 'y' keys with unit values
        grbl_units = position.get(self.position_key, 0.0)
        
        # Convert GRBL units to steps, then to degrees
        steps = self._grbl_units_to_steps(grbl_units)
        self._current_angle = self._steps_to_degrees(steps)
    
    # Command building methods (pure functions, testable)
    
    def _build_move_command(self, target_units: float, feedrate: int) -> str:
        """Build G0 move command using command builder."""
        return GRBLCommandBuilder.build_move_command(
            self.grbl_axis_letter,
            target_units,
            feedrate
        )
    
    def _build_work_offset_command(self, offset_units: float) -> str:
        """Build G92 work offset command using command builder."""
        return GRBLCommandBuilder.build_work_offset_command(
            self.grbl_axis_letter,
            offset_units
        )
    
    # Movement methods (use command sender interface)
    
    def rotate_to(self, degrees: float, feedrate: Optional[int] = None) -> bool:
        """
        Rotate to absolute position in degrees.
        
        Args:
            degrees: Target angle in degrees
            feedrate: Optional feedrate override (steps/min). If None, uses configured speed value.
            
        Returns:
            True if command sent successfully
        """
        axis_name = self.grbl_axis_letter
        self._log(f"[Axis {axis_name}] rotate_to({degrees}°) called")
        
        # 1. CALCULATION: Normalize angle (applies shortest path for 360° axes)
        normalized_degrees = self._normalize_target_angle(degrees)
        if normalized_degrees != degrees:
            self._log(f"[Axis {axis_name}]   Normalized: {degrees}° → {normalized_degrees}°")
        
        # 2. VALIDATION: Validate normalized angle
        is_valid, error_msg = self.validate_angle(normalized_degrees)
        if not is_valid:
            self._log(f"[Axis {axis_name}] ✗ Invalid angle: {error_msg}")
            return False
        
        # 3. CHECK STATE: Check if GRBL is in a valid state to accept commands
        if self.command_sender.get_machine_state() == MachineState.ALARM:
            self._log(f"[Axis {axis_name}]   ⚠️  GRBL is in alarm state, attempting to unlock...")
            if not self.command_sender.unlock():
                self._log(f"[Axis {axis_name}]   ✗ Failed to unlock GRBL, aborting movement")
                return False
            # Wait a moment for GRBL to process unlock
            time.sleep(0.2)
            # Re-check state
            if self.command_sender.get_machine_state() == MachineState.ALARM:
                self._log(f"[Axis {axis_name}]   ✗ GRBL still in alarm state after unlock attempt, aborting")
                return False
        
        # 4. CALCULATION: Get current position
        current_angle = self.current()
        self._log(f"[Axis {axis_name}]   Current position: {current_angle:.3f}°")
        
        # 5. CALCULATION: Ensure work coordinate system is aligned
        current_grbl_units = self._steps_to_grbl_units(self._degrees_to_steps(current_angle))
        
        # 6. COMMAND BUILDING: Build alignment command
        align_cmd = self._build_work_offset_command(current_grbl_units)
        self._log(f"[Axis {axis_name}]   Aligning work coordinate system: {align_cmd}")
        
        # 7. COMMAND SENDING: Retry G92 command if it fails
        align_success = False
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            align_success = self.command_sender.send_command(align_cmd, wait_for_ok=True)
            if align_success:
                break
            if attempt < max_retries:
                self._log(f"[Axis {axis_name}]   ⚠️  G92 alignment failed (attempt {attempt}/{max_retries}), retrying...")
                time.sleep(0.2)  # Brief delay before retry
        
        if not align_success:
            self._log(f"[Axis {axis_name}]   ⚠️  G92 alignment command failed after {max_retries} attempts, aborting movement")
            # Check if GRBL is in alarm state
            if self.command_sender.get_machine_state() == MachineState.ALARM:
                self._log(f"[Axis {axis_name}]   GRBL is in alarm state - may need manual intervention")
            return False
        
        # 8. CALCULATION: Convert target to steps and GRBL units
        target_steps = self._degrees_to_steps(normalized_degrees)
        target_units = self._steps_to_grbl_units(target_steps)
        grbl_steps_per_mm = self.grbl_steps_per_mm
        
        # 9. CALCULATION: Calculate feedrate
        if feedrate is None:
            feedrate = self._get_feedrate()
        else:
            max_rate = int(GRBL_MAX_RATE)
            feedrate = min(feedrate, max_rate)
        
        # Ensure feedrate is valid
        if feedrate is None or feedrate <= 0:
            self._log(f"[Axis {axis_name}]   ⚠️  Invalid feedrate: {feedrate}, using default")
            feedrate = self._get_feedrate()
        
        # 10. COMMAND BUILDING: Build G-code command
        command = self._build_move_command(target_units, feedrate)
        
        self._log(f"[Axis {axis_name}]   Target: {normalized_degrees}° ({target_steps:.6f} steps)")
        self._log(f"[Axis {axis_name}]   GRBL $100/$101: {grbl_steps_per_mm:.6f}")
        self._log(f"[Axis {axis_name}]   GRBL units: {target_units:.6f}")
        max_rate = int(GRBL_MAX_RATE)
        self._log(f"[Axis {axis_name}]   Speed: {feedrate} steps/min (max: {max_rate})")
        self._log(f"[Axis {axis_name}]   Sending: {command}")
        
        # 11. VALIDATION: Verify F parameter is in command
        if feedrate is not None and f"F{feedrate}" not in command:
            self._log(f"[Axis {axis_name}]   ⚠️  WARNING: F parameter missing from command!")
            return False
        
        # 12. COMMAND SENDING: Send command
        success = self.command_sender.send_command(command, wait_for_ok=True)
        if success:
            self._log(f"[Axis {axis_name}]   ✓ Command sent successfully")
        else:
            self._log(f"[Axis {axis_name}]   ✗ Command failed")
        
        return success
    
    def rotate_on(self, degrees: float) -> bool:
        """
        Rotate relative to current position.
        
        Args:
            degrees: Angle delta in degrees (positive or negative)
            
        Returns:
            True if command sent successfully
        """
        axis_name = self.grbl_axis_letter
        self._log(f"[Axis {axis_name}] rotate_on({degrees:+.3f}°) called")
        current_angle = self.current()
        target_angle = current_angle + degrees
        self._log(f"[Axis {axis_name}]   Current: {current_angle:.3f}°, Target: {target_angle:.3f}°")
        return self.rotate_to(target_angle)
    
    def reset(self) -> bool:
        """
        Return to home position.
        
        Returns:
            True if command sent successfully
        """
        axis_name = self.grbl_axis_letter
        self._log(f"[Axis {axis_name}] reset() called")
        self._log(f"[Axis {axis_name}]   Home position: {self.config.home_angle}°")
        return self.rotate_to(self.config.home_angle)
    
    def current(self) -> float:
        """
        Get current position in degrees.
        
        Returns:
            Current angle in degrees
        """
        # Don't log current() calls as they're called frequently for UI updates
        return self._current_angle
    
    def _get_feedrate(self) -> int:
        """Get feedrate for this axis (uses configured speed, clamped to GRBL_MAX_RATE)."""
        # Use configured speed, but ensure it doesn't exceed hardcoded max rate
        max_rate = int(GRBL_MAX_RATE)
        speed = min(self.config.speed, max_rate)
        return speed
    
    def estimate_movement_time(self, from_angle: float, to_angle: float) -> float:
        """
        Estimate movement time in seconds.
        
        Args:
            from_angle: Starting angle in degrees
            to_angle: Target angle in degrees
            
        Returns:
            Estimated time in seconds
        """
        # Calculate movement distance (will be overridden for X-axis with wrapping)
        degrees_to_move = abs(to_angle - from_angle)
        
        steps = self._degrees_to_steps(degrees_to_move)
        
        # Use configured speed for estimation
        feedrate = self._get_feedrate()
        
        # Simple calculation: time = distance / speed
        # GRBL uses feedrate in steps/min, convert to steps/sec
        time_seconds = (steps / feedrate) * 60.0
        
        # Add overhead for acceleration/deceleration (rough estimate)
        time_seconds *= 1.2  # 20% buffer
        
        return time_seconds
    
    def estimate_move_to_time(self, target_angle: float) -> float:
        """
        Estimate time to move to target from current position.
        
        Args:
            target_angle: Target angle in degrees
            
        Returns:
            Estimated time in seconds
        """
        current = self.current()
        return self.estimate_movement_time(current, target_angle)
    
    def is_moving(self) -> bool:
        """
        Check if this axis is currently moving.
        
        Returns:
            True if axis is moving, False if idle
        """
        return self.command_sender.is_moving()


class XAxis(BaseAxis):
    """X-axis: continuous rotation with 360° modular arithmetic."""
    
    @property
    def grbl_axis_letter(self) -> str:
        """GRBL axis letter for X-axis."""
        return 'X'
    
    @property
    def position_key(self) -> str:
        """Position dict key for X-axis."""
        return 'x'
    
    def _normalize_target_angle(self, desired_angle: float) -> float:
        """
        Normalize target angle with modular arithmetic and shortest path.
        
        Args:
            desired_angle: Desired target angle (may be negative or >360)
            
        Returns:
            Target angle (may be negative or >360) using shortest path
            This preserves cumulative rotation for GRBL absolute positioning
        """
        current = self.current()
        return self._calculate_shortest_path(current, desired_angle)
    
    def _calculate_shortest_path(self, current_angle: float, target_angle: float) -> float:
        """
        Calculate shortest path for continuous rotation.
        
        Examples:
            - 10° → 350°: should go -20° (via 0) = -10° absolute
            - 350° → 10°: should go +20° (via 360/0) = 370° absolute
            - 10° → -350°: normalize -350° to 10°, no movement
            - 10° → 370°: normalize 370° to 10°, no movement
        
        Args:
            current_angle: Current angle in degrees
            target_angle: Target angle in degrees (may be negative or >360)
            
        Returns:
            Target angle (may be negative or >360) representing shortest path
            This preserves the cumulative rotation for GRBL absolute positioning
        """
        # Normalize both angles to 0-360 range for comparison
        current_norm = ((current_angle % 360) + 360) % 360
        target_norm = ((target_angle % 360) + 360) % 360
        
        # If normalized angles are equal, no movement needed
        if abs(current_norm - target_norm) < 0.001:
            # Return target as-is to preserve any cumulative rotation
            return target_angle
        
        # Calculate direct path distance
        direct_delta = target_norm - current_norm
        
        # Calculate wraparound paths
        if direct_delta > 0:
            # Target is ahead, check backward wrap
            backward_wrap_delta = direct_delta - 360
            # Choose shorter path
            if abs(backward_wrap_delta) < abs(direct_delta):
                # Use backward wrap: add negative delta to current angle
                final_target = current_angle + backward_wrap_delta
            else:
                # Use direct path: calculate target from current + delta
                final_target = current_angle + direct_delta
        else:  # direct_delta < 0
            # Target is behind, check forward wrap
            forward_wrap_delta = direct_delta + 360
            # Choose shorter path
            if abs(forward_wrap_delta) < abs(direct_delta):
                # Use forward wrap: add positive delta to current angle
                final_target = current_angle + forward_wrap_delta
            else:
                # Use direct path: calculate target from current + delta
                final_target = current_angle + direct_delta
        
        return final_target
    
    def validate_angle(self, degrees: float) -> Tuple[bool, Optional[str]]:
        """
        Validate angle for X-axis (accepts any angle, uses modular arithmetic).
        
        Args:
            degrees: Angle to validate
            
        Returns:
            Tuple of (True, None) - always valid due to modular arithmetic
        """
        # Normalize to 0-360 range for logging
        normalized = ((degrees % 360) + 360) % 360
        if abs(normalized - degrees) > 0.001:
            self._log(f"[Axis X]   Validation: {degrees}° → {normalized}° (wrapped)")
        return True, None
    
    def estimate_movement_time(self, from_angle: float, to_angle: float) -> float:
        """
        Estimate movement time in seconds (with shortest path for X-axis).
        
        Args:
            from_angle: Starting angle in degrees
            to_angle: Target angle in degrees
            
        Returns:
            Estimated time in seconds
        """
        # Use shortest path for X-axis
        current_norm = ((from_angle % 360) + 360) % 360
        target_norm = ((to_angle % 360) + 360) % 360
        
        direct = abs(target_norm - current_norm)
        wraparound = 360.0 - direct
        degrees_to_move = min(direct, wraparound)
        
        steps = self._degrees_to_steps(degrees_to_move)
        feedrate = self._get_feedrate()
        time_seconds = (steps / feedrate) * 60.0
        time_seconds *= 1.2  # 20% buffer
        
        return time_seconds


class YAxis(BaseAxis):
    """Y-axis: limited range -90° to 90°."""
    
    @property
    def grbl_axis_letter(self) -> str:
        """GRBL axis letter for Y-axis."""
        return 'Y'
    
    @property
    def position_key(self) -> str:
        """Position dict key for Y-axis."""
        return 'y'
    
    def _normalize_target_angle(self, desired_angle: float) -> float:
        """
        Clamp target angle to limits.
        
        Args:
            desired_angle: Desired target angle
            
        Returns:
            Clamped angle within [-90, 90] range
        """
        min_limit = self.config.min_angle  # -90
        max_limit = self.config.max_angle  # 90
        return max(min_limit, min(desired_angle, max_limit))
    
    def validate_angle(self, degrees: float) -> Tuple[bool, Optional[str]]:
        """
        Validate angle for Y-axis (strict limits).
        
        Args:
            degrees: Angle to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        min_angle = self.config.min_angle
        max_angle = self.config.max_angle
        
        if degrees < min_angle or degrees > max_angle:
            return False, f"Y-axis angle must be between {min_angle}° and {max_angle}°"
        
        return True, None


# Keep old Axis class as factory function for backward compatibility during migration
def Axis(name: str, command_sender_or_controller, config: AxisConfig, 
         message_callback: Optional[Callable[[str], None]] = None):
    """
    Factory function for backward compatibility.
    
    This will be removed after migration is complete.
    """
    from src.grbl.grbl_command_sender_adapter import GRBLCommandSenderAdapter
    from src.grbl.grbl_controller import GRBLController
    
    # Handle both old (GRBLController) and new (GRBLCommandSenderInterface) signatures
    if isinstance(command_sender_or_controller, GRBLController):
        command_sender = GRBLCommandSenderAdapter(command_sender_or_controller)
    else:
        command_sender = command_sender_or_controller
    
    if name.lower() == 'x':
        return XAxis(command_sender, config, message_callback)
    elif name.lower() == 'y':
        return YAxis(command_sender, config, message_callback)
    else:
        raise ValueError(f"Invalid axis name: {name}")
