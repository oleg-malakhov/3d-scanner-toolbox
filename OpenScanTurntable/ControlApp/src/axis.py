"""Axis class for handling individual axis operations and conversions."""

from dataclasses import dataclass
from typing import Tuple, Optional, Callable
from src.grbl_controller import GRBLController

# Hardcoded GRBL max rate (applied to both axes on connection)
GRBL_MAX_RATE = 15000.0  # steps/min


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


class Axis:
    """Handles all operations for a single axis."""
    
    def __init__(self, name: str, grbl_controller: GRBLController, config: AxisConfig, 
                 message_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize axis.
        
        Args:
            name: Axis name ('x' or 'y')
            grbl_controller: GRBL controller instance
            config: Axis configuration
            message_callback: Optional callback function to receive log messages
        """
        self.name = name.lower()
        self.grbl_controller = grbl_controller
        self.config = config
        self.message_callback = message_callback
        
        # Calculate steps per degree
        self._steps_per_degree = self._calculate_steps_per_degree()
        
        # Current position in degrees (cached from GRBL updates)
        self._current_angle = config.home_angle
        
        # Register for GRBL status updates
        self.grbl_controller.register_status_callback(self._on_grbl_status_update)
    
    def _log(self, message: str) -> None:
        """Log a message (print to console and send to callback if available)."""
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
    
    def _get_grbl_steps_per_mm(self) -> float:
        """Get current GRBL steps/mm setting (may be updated from GRBL)."""
        # Get from controller (which updates from GRBL responses)
        if self.name == 'x':
            return self.grbl_controller.grbl_x_steps_per_mm
        else:  # y
            return self.grbl_controller.grbl_y_steps_per_mm
    
    def _steps_to_grbl_units(self, steps: float) -> float:
        """Convert steps to GRBL units (accounting for $100/$101)."""
        # GRBL calculates: actual_steps = units × $100 (or $101)
        # We want: actual_steps = steps
        # So: units = steps / $100
        grbl_steps_per_mm = self._get_grbl_steps_per_mm()
        return steps / grbl_steps_per_mm
    
    def _grbl_units_to_steps(self, units: float) -> float:
        """Convert GRBL units to steps (accounting for $100/$101)."""
        # GRBL reports MPos in units
        # actual_steps = units × $100 (or $101)
        grbl_steps_per_mm = self._get_grbl_steps_per_mm()
        return units * grbl_steps_per_mm
    
    def _on_grbl_status_update(self, state, position: dict) -> None:
        """Update internal position from GRBL status."""
        # Get position in units from GRBL (MPos)
        # Position dict contains 'x' and 'y' keys with unit values
        if self.name == 'x':
            grbl_units = position.get('x', 0.0)
        else:  # y
            grbl_units = position.get('y', 0.0)
        
        # Convert GRBL units to steps, then to degrees
        steps = self._grbl_units_to_steps(grbl_units)
        self._current_angle = self._steps_to_degrees(steps)
    
    def _calculate_shortest_path(self, current_angle: float, target_angle: float) -> float:
        """
        Calculate shortest path to target angle, handling 360° wrapping.
        
        For axes with full 360° range, calculates the shortest angular path.
        Example: 350° → 10° should go +20° (not -340°).
        
        Args:
            current_angle: Current angle in degrees
            target_angle: Target angle in degrees
            
        Returns:
            Adjusted target angle that represents shortest path
        """
        # Only apply shortest path for full 360° range
        if self.config.max_angle == 360.0 and self.config.min_angle == 0.0:
            degrees_to_move = target_angle - current_angle
            
            # Normalize to -180° to +180° range
            if degrees_to_move > 180.0:
                degrees_to_move -= 360.0  # Go backwards instead
                adjusted_target = current_angle + degrees_to_move
                self._log(f"[Axis {self.name.upper()}]   Shortest path: {target_angle}° → {adjusted_target}° (wrapped -{360 - (target_angle - current_angle)}°)")
            elif degrees_to_move < -180.0:
                degrees_to_move += 360.0  # Go forwards instead
                adjusted_target = current_angle + degrees_to_move
                self._log(f"[Axis {self.name.upper()}]   Shortest path: {target_angle}° → {adjusted_target}° (wrapped +{360 + (target_angle - current_angle)}°)")
            else:
                adjusted_target = target_angle
            
            # Normalize result to 0-360 range
            return adjusted_target % 360.0
        
        # For limited range axes, return target as-is
        return target_angle
    
    def _normalize_target_angle(self, desired_angle: float) -> float:
        """
        Normalize target angle to valid range, applying shortest path if applicable.
        
        Args:
            desired_angle: Desired target angle
            
        Returns:
            Normalized target angle
        """
        min_limit = self.config.min_angle
        max_limit = self.config.max_angle
        
        # Full 360° range: use modulo and shortest path
        if min_limit == 0.0 and max_limit == 360.0:
            normalized = desired_angle % 360.0
            # Apply shortest path calculation
            current = self.current()
            return self._calculate_shortest_path(current, normalized)
        
        # Limited range: clamp to limits
        if desired_angle < min_limit:
            return min_limit
        elif desired_angle > max_limit:
            return max_limit
        
        return desired_angle
    
    def rotate_to(self, degrees: float, feedrate: Optional[int] = None) -> bool:
        """
        Rotate to absolute position in degrees.
        
        Args:
            degrees: Target angle in degrees
            feedrate: Optional feedrate override (steps/min). If None, uses configured speed value.
            
        Returns:
            True if command sent successfully
        """
        self._log(f"[Axis {self.name.upper()}] rotate_to({degrees}°) called")
        
        # Normalize angle (applies shortest path for 360° axes)
        normalized_degrees = self._normalize_target_angle(degrees)
        if normalized_degrees != degrees:
            self._log(f"[Axis {self.name.upper()}]   Normalized: {degrees}° → {normalized_degrees}°")
        
        # Validate normalized angle
        is_valid, error_msg = self.validate_angle(normalized_degrees)
        if not is_valid:
            self._log(f"[Axis {self.name.upper()}] ✗ Invalid angle: {error_msg}")
            return False
        
        # Get current position
        current_angle = self.current()
        self._log(f"[Axis {self.name.upper()}]   Current position: {current_angle:.3f}°")
        
        # Ensure work coordinate system is aligned with current physical position
        # This is critical for accurate absolute positioning (G90)
        # Get current position in GRBL units
        current_grbl_units = self._steps_to_grbl_units(self._degrees_to_steps(current_angle))
        
        # Calculate what GRBL thinks the current position should be in work coordinates
        # If there's a mismatch, we need to realign
        # For now, we'll ensure alignment by setting work origin to current position
        # This ensures G90 absolute commands work correctly
        if self.name == 'x':
            align_cmd = f"G92 X{current_grbl_units:.3f}"
        else:  # y
            align_cmd = f"G92 Y{current_grbl_units:.3f}"
        
        self._log(f"[Axis {self.name.upper()}]   Aligning work coordinate system: {align_cmd}")
        self.grbl_controller.send_command(align_cmd, wait_for_ok=True)
        
        # Convert target to steps (use normalized angle)
        target_steps = self._degrees_to_steps(normalized_degrees)
        
        # Convert to GRBL units
        target_units = self._steps_to_grbl_units(target_steps)
        grbl_steps_per_mm = self._get_grbl_steps_per_mm()
        
        # Calculate feedrate (always use speed from settings)
        if feedrate is None:
            # Use configured speed value
            feedrate = self._get_feedrate()
        else:
            # Use provided feedrate, but clamp to hardcoded max rate
            max_rate = int(GRBL_MAX_RATE)
            feedrate = min(feedrate, max_rate)
        
        # Ensure feedrate is valid
        if feedrate is None or feedrate <= 0:
            self._log(f"[Axis {self.name.upper()}]   ⚠️  Invalid feedrate: {feedrate}, using default")
            feedrate = self._get_feedrate()
        
        # Build G-code command (absolute positioning, always include F parameter)
        if self.name == 'x':
            command = f"G0 X{target_units:.3f} F{feedrate}"
        else:  # y
            command = f"G0 Y{target_units:.3f} F{feedrate}"
        
        self._log(f"[Axis {self.name.upper()}]   Target: {normalized_degrees}° ({target_steps:.6f} steps)")
        self._log(f"[Axis {self.name.upper()}]   GRBL $100/$101: {grbl_steps_per_mm:.6f}")
        self._log(f"[Axis {self.name.upper()}]   GRBL units: {target_units:.6f}")
        max_rate = int(GRBL_MAX_RATE)
        self._log(f"[Axis {self.name.upper()}]   Speed: {feedrate} steps/min (max: {max_rate})")
        self._log(f"[Axis {self.name.upper()}]   Sending: {command}")
        
        # Verify F parameter is in command
        if feedrate is not None and f"F{feedrate}" not in command:
            self._log(f"[Axis {self.name.upper()}]   ⚠️  WARNING: F parameter missing from command!")
            return False
        
        # Send command
        success = self.grbl_controller.send_command(command, wait_for_ok=True)
        if success:
            self._log(f"[Axis {self.name.upper()}]   ✓ Command sent successfully")
        else:
            self._log(f"[Axis {self.name.upper()}]   ✗ Command failed")
        
        return success
    
    def rotate_on(self, degrees: float) -> bool:
        """
        Rotate relative to current position.
        
        Args:
            degrees: Angle delta in degrees (positive or negative)
            
        Returns:
            True if command sent successfully
        """
        self._log(f"[Axis {self.name.upper()}] rotate_on({degrees:+.3f}°) called")
        current_angle = self.current()
        target_angle = current_angle + degrees
        self._log(f"[Axis {self.name.upper()}]   Current: {current_angle:.3f}°, Target: {target_angle:.3f}°")
        return self.rotate_to(target_angle)
    
    def reset(self) -> bool:
        """
        Return to home position.
        
        Returns:
            True if command sent successfully
        """
        self._log(f"[Axis {self.name.upper()}] reset() called")
        self._log(f"[Axis {self.name.upper()}]   Home position: {self.config.home_angle}°")
        return self.rotate_to(self.config.home_angle)
    
    def current(self) -> float:
        """
        Get current position in degrees.
        
        Returns:
            Current angle in degrees
        """
        # Don't log current() calls as they're called frequently for UI updates
        return self._current_angle
    
    def validate_angle(self, degrees: float) -> Tuple[bool, Optional[str]]:
        """
        Validate if angle is within limits.
        
        Args:
            degrees: Angle to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # For X-axis, allow wrapping (continuous rotation)
        if self.name == 'x':
            min_angle = self.config.min_angle
            max_angle = self.config.max_angle
            
            # If max_angle is 360, allow wrapping
            if max_angle == 360:
                # Normalize to 0-360 range
                normalized = degrees % 360
                self._log(f"[Axis {self.name.upper()}]   Validation: {degrees}° → {normalized}° (wrapped)")
                return True, None
            
            if degrees < min_angle or degrees > max_angle:
                return False, f"X-axis angle must be between {min_angle}° and {max_angle}°"
            self._log(f"[Axis {self.name.upper()}]   Validation: {degrees}° is within range [{min_angle}°, {max_angle}°]")
            return True, None
        
        # For Y-axis, strict limits
        elif self.name == 'y':
            min_angle = self.config.min_angle
            max_angle = self.config.max_angle
            
            if degrees < min_angle or degrees > max_angle:
                return False, f"Y-axis angle must be between {min_angle}° and {max_angle}°"
            self._log(f"[Axis {self.name.upper()}]   Validation: {degrees}° is within range [{min_angle}°, {max_angle}°]")
            return True, None
        
        return False, f"Invalid axis: {self.name}"
    
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
        degrees_to_move = abs(to_angle - from_angle)
        
        # For X-axis with wrapping, use shortest path
        if self.config.max_angle == 360.0:
            direct = degrees_to_move
            wraparound = 360.0 - direct
            degrees_to_move = min(direct, wraparound)
        
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
        return self.grbl_controller.is_moving()
