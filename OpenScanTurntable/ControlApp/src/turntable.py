"""Turntable class for managing multiple axes."""

from typing import Optional, Tuple, Union, Callable
from src.grbl_controller import GRBLController
from src.axis import Axis, AxisConfig, GRBL_MAX_RATE
from src.utils.config import Config


class Turntable:
    """High-level API for controlling multiple axes."""
    
    # Axis constants
    AXIS_X = 0
    AXIS_Y = 1
    
    def __init__(self, grbl_controller: GRBLController, config: Config, 
                 message_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize turntable with axes.
        
        Args:
            grbl_controller: GRBL controller instance
            config: Application configuration
            message_callback: Optional callback function to receive log messages
        """
        self.grbl_controller = grbl_controller
        self.config = config
        self.message_callback = message_callback
        
        # Get GRBL steps/mm settings (will be updated when GRBL reports them)
        # Default to 1.0 initially, but will be updated via status callbacks
        # We need to access these dynamically, so we'll update configs when they change
        self.grbl_x_steps_per_mm = grbl_controller.grbl_x_steps_per_mm
        self.grbl_y_steps_per_mm = grbl_controller.grbl_y_steps_per_mm
        
        # Create X-axis configuration
        x_accel = config.get('motors.x_axis.acceleration', 50.0)
        x_gear_ratio = config.get('motors.x_axis.gear_ratio', 1.0)
        x_config = AxisConfig(
            step_angle=config.get('motors.x_axis.step_angle', 1.8),
            microsteps=config.get('motors.x_axis.microsteps', 0),
            min_angle=config.get('motors.x_axis.min_angle', 0),
            max_angle=config.get('motors.x_axis.max_angle', 360),
            speed=config.get('motors.x_axis.speed', int(GRBL_MAX_RATE)),  # Default to GRBL_MAX_RATE if not specified
            acceleration=x_accel,
            gear_ratio=x_gear_ratio,
            always_on=config.get('motors.x_axis.always_on', False),
            home_angle=config.get('home_position.x', 0),
            grbl_axis_letter='X',
            grbl_steps_per_mm=self.grbl_x_steps_per_mm
        )
        
        # Create Y-axis configuration
        y_accel = config.get('motors.y_axis.acceleration', 50.0)
        y_gear_ratio = config.get('motors.y_axis.gear_ratio', 1.0)
        y_config = AxisConfig(
            step_angle=config.get('motors.y_axis.step_angle', 1.8),
            microsteps=config.get('motors.y_axis.microsteps', 0),
            min_angle=config.get('motors.y_axis.min_angle', -90),
            max_angle=config.get('motors.y_axis.max_angle', 90),
            speed=config.get('motors.y_axis.speed', int(GRBL_MAX_RATE)),  # Default to GRBL_MAX_RATE if not specified
            acceleration=y_accel,
            gear_ratio=y_gear_ratio,
            always_on=config.get('motors.y_axis.always_on', True),
            home_angle=config.get('home_position.y', 0),
            grbl_axis_letter='Y',
            grbl_steps_per_mm=self.grbl_y_steps_per_mm
        )
        
        # Create axis instances (pass message callback to each)
        self.axes = [
            Axis('x', grbl_controller, x_config, message_callback=self.message_callback),  # Index 0
            Axis('y', grbl_controller, y_config, message_callback=self.message_callback)   # Index 1
        ]
        
        init_msg = f"[Turntable] Initialized with {len(self.axes)} axes"
        print(init_msg)
        if self.message_callback:
            self.message_callback(init_msg)
        
        x_msg = f"[Turntable]   X-axis: {x_config.min_angle}° to {x_config.max_angle}°"
        y_msg = f"[Turntable]   Y-axis: {y_config.min_angle}° to {y_config.max_angle}°"
        print(x_msg)
        print(y_msg)
        if self.message_callback:
            self.message_callback(x_msg)
            self.message_callback(y_msg)
    
    def _validate_axis(self, axis: int) -> None:
        """Validate axis index."""
        if axis not in (0, 1):
            raise ValueError(f"Invalid axis: {axis}. Must be 0 (X) or 1 (Y)")
    
    def rotate_to(self, axis: int, degrees: float) -> bool:
        """
        Rotate specified axis to absolute position.
        
        Args:
            axis: 0 for X-axis, 1 for Y-axis
            degrees: Target angle in degrees
            
        Returns:
            True if command sent successfully
            
        Raises:
            ValueError: If axis is not 0 or 1
        """
        self._validate_axis(axis)
        axis_name = "X" if axis == 0 else "Y"
        msg = f"[Turntable] rotate_to(axis={axis_name}, degrees={degrees}°)"
        print(msg)
        if self.message_callback:
            self.message_callback(msg)
        return self.axes[axis].rotate_to(degrees)
    
    def rotate_on(self, axis: int, degrees: float) -> bool:
        """
        Rotate specified axis relative to current position.
        
        Args:
            axis: 0 for X-axis, 1 for Y-axis
            degrees: Angle delta in degrees
            
        Returns:
            True if command sent successfully
            
        Raises:
            ValueError: If axis is not 0 or 1
        """
        self._validate_axis(axis)
        axis_name = "X" if axis == 0 else "Y"
        msg = f"[Turntable] rotate_on(axis={axis_name}, degrees={degrees:+.3f}°)"
        print(msg)
        if self.message_callback:
            self.message_callback(msg)
        return self.axes[axis].rotate_on(degrees)
    
    def reset(self) -> bool:
        """
        Reset all axes to home position.
        
        Returns:
            True if all axes reset successfully
        """
        reset_msg = "[Turntable] reset() called - Resetting all axes to home position..."
        print(reset_msg)
        if self.message_callback:
            self.message_callback(reset_msg)
        success_x = self.axes[0].reset()
        success_y = self.axes[1].reset()
        result = success_x and success_y
        if result:
            result_msg = "[Turntable] ✓ All axes reset successfully"
        else:
            result_msg = "[Turntable] ✗ Some axes failed to reset"
        print(result_msg)
        if self.message_callback:
            self.message_callback(result_msg)
        return result
    
    def current(self, axis: Optional[int] = None) -> Union[float, Tuple[float, float]]:
        """
        Get current position(s).
        
        Args:
            axis: 0 for X-axis, 1 for Y-axis, None for both
            
        Returns:
            Single angle (float) if axis specified, tuple (x, y) if None
            
        Raises:
            ValueError: If axis is not 0, 1, or None
        """
        if axis is None:
            return (self.axes[0].current(), self.axes[1].current())
        else:
            self._validate_axis(axis)
            return self.axes[axis].current()
    
    def num_axes(self) -> int:
        """
        Get number of available axes.
        
        Returns:
            Number of axes (2)
        """
        return len(self.axes)
    
    def get_axis(self, axis: int) -> Optional[Axis]:
        """
        Get axis instance (for advanced use cases).
        
        Args:
            axis: 0 for X-axis, 1 for Y-axis
            
        Returns:
            Axis instance or None if not found
            
        Raises:
            ValueError: If axis is not 0 or 1
        """
        self._validate_axis(axis)
        return self.axes[axis]
    
    def move_to_angles(self, x_angle: float, y_angle: float, 
                       synchronized: bool = True) -> bool:
        """
        Move both axes simultaneously to target angles.
        
        Args:
            x_angle: Target X-axis angle in degrees
            y_angle: Target Y-axis angle in degrees
            synchronized: If True, match speeds so axes finish together. If False, use configured speeds independently.
            
        Returns:
            True if command sent successfully
        """
        msg = f"[Turntable] move_to_angles(X={x_angle}°, Y={y_angle}°, synchronized={synchronized})"
        print(msg)
        if self.message_callback:
            self.message_callback(msg)
        
        # Validate both angles
        x_valid, x_error = self.axes[0].validate_angle(x_angle)
        y_valid, y_error = self.axes[1].validate_angle(y_angle)
        
        if not x_valid:
            error_msg = f"[Turntable] ✗ Invalid X angle: {x_error}"
            print(error_msg)
            if self.message_callback:
                self.message_callback(error_msg)
            return False
        
        if not y_valid:
            error_msg = f"[Turntable] ✗ Invalid Y angle: {y_error}"
            print(error_msg)
            if self.message_callback:
                self.message_callback(error_msg)
            return False
        
        # Get current positions
        x_current = self.axes[0].current()
        y_current = self.axes[1].current()
        
        x_degrees = abs(x_angle - x_current)
        y_degrees = abs(y_angle - y_current)
        
        # Handle X-axis wrapping for shortest path
        if self.axes[0].config.max_angle == 360.0:
            direct = x_degrees
            wraparound = 360.0 - direct
            x_degrees = min(direct, wraparound)
        
        # Calculate feedrates (always use speed from settings)
        if synchronized:
            # Calculate coordinated feedrates so both axes finish together
            x_feedrate, y_feedrate = self._calculate_synchronized_feedrates(
                x_degrees, y_degrees
            )
        else:
            # Use configured speed values
            x_feedrate = self.axes[0]._get_feedrate()
            y_feedrate = self.axes[1]._get_feedrate()
        
        # Convert to steps and GRBL units
        x_normalized = self.axes[0]._normalize_target_angle(x_angle)
        y_normalized = self.axes[1]._normalize_target_angle(y_angle)
        
        x_steps = self.axes[0]._degrees_to_steps(x_normalized)
        y_steps = self.axes[1]._degrees_to_steps(y_normalized)
        
        x_units = self.axes[0]._steps_to_grbl_units(x_steps)
        y_units = self.axes[1]._steps_to_grbl_units(y_steps)
        
        # Calculate feedrate (always use speed from settings)
        # Use the slower feedrate for combined movement (GRBL uses single F value)
        feedrate = min(x_feedrate, y_feedrate)
        
        # Ensure feedrate is valid
        if feedrate is None or feedrate <= 0:
            print(f"[Turntable]   ⚠️  Invalid feedrate: {feedrate}, using defaults")
            feedrate = min(int(GRBL_MAX_RATE), int(GRBL_MAX_RATE))
        
        # Build combined G-code command (always include F parameter)
        command = f"G0 X{x_units:.3f} Y{y_units:.3f} F{feedrate}"
        
        # Verify F parameter is in command
        if feedrate is not None and f"F{feedrate}" not in command:
            error_msg = f"[Turntable]   ⚠️  WARNING: F parameter missing from command!"
            print(error_msg)
            if self.message_callback:
                self.message_callback(error_msg)
            return False
        
        info_msg = f"[Turntable]   X: {x_current:.1f}° → {x_normalized:.1f}° ({x_degrees:.1f}° move, {x_feedrate} steps/min)"
        print(info_msg)
        if self.message_callback:
            self.message_callback(info_msg)
        
        info_msg = f"[Turntable]   Y: {y_current:.1f}° → {y_normalized:.1f}° ({y_degrees:.1f}° move, {y_feedrate} steps/min)"
        print(info_msg)
        if self.message_callback:
            self.message_callback(info_msg)
        
        if synchronized:
            info_msg = f"[Turntable]   Synchronized: using {feedrate} steps/min (both axes finish together)"
            print(info_msg)
            if self.message_callback:
                self.message_callback(info_msg)
        
        info_msg = f"[Turntable]   Command: {command}"
        print(info_msg)
        if self.message_callback:
            self.message_callback(info_msg)
        
        # Send command
        success = self.grbl_controller.send_command(command, wait_for_ok=True)
        
        if success:
            success_msg = "[Turntable] ✓ Concurrent movement command sent successfully"
            print(success_msg)
            if self.message_callback:
                self.message_callback(success_msg)
        else:
            error_msg = "[Turntable] ✗ Concurrent movement command failed"
            print(error_msg)
            if self.message_callback:
                self.message_callback(error_msg)
        
        return success
    
    def _calculate_synchronized_feedrates(self, x_degrees: float, y_degrees: float) -> Tuple[int, int]:
        """
        Calculate feedrates for both axes so they complete movement at the same time.
        
        Args:
            x_degrees: X-axis movement distance (absolute value, already shortest path)
            y_degrees: Y-axis movement distance (absolute value)
            
        Returns:
            Tuple of (x_feedrate, y_feedrate) in steps/min
        """
        # Calculate steps for each axis
        x_steps = self.axes[0]._degrees_to_steps(x_degrees)
        y_steps = self.axes[1]._degrees_to_steps(y_degrees)
        
        # Calculate time for each axis at max feedrate
        x_max_rate = int(GRBL_MAX_RATE)
        y_max_rate = int(GRBL_MAX_RATE)
        x_time_at_max = (x_steps / x_max_rate) * 60.0 if x_max_rate > 0 else 0
        y_time_at_max = (y_steps / y_max_rate) * 60.0 if y_max_rate > 0 else 0
        
        # Use the longer time as target (both axes must complete in this time)
        target_time = max(x_time_at_max, y_time_at_max)
        
        # If one axis has zero movement, use configured speed for the other
        if x_degrees == 0:
            y_feedrate = self.axes[1]._get_feedrate()
            return (x_max_rate, y_feedrate)
        
        if y_degrees == 0:
            x_feedrate = self.axes[0]._get_feedrate()
            return (x_feedrate, y_max_rate)
        
        # Calculate feedrates to match target time
        # Account for acceleration/deceleration overhead (~20%)
        accel_overhead = 0.2
        effective_time = target_time * (1 - accel_overhead)
        
        if effective_time <= 0:
            effective_time = target_time * 0.5  # Fallback
        
        x_feedrate = int((x_steps / effective_time) * 60.0) if effective_time > 0 else x_max_rate
        y_feedrate = int((y_steps / effective_time) * 60.0) if effective_time > 0 else y_max_rate
        
        # Clamp to max feedrates
        x_feedrate = min(x_feedrate, x_max_rate)
        y_feedrate = min(y_feedrate, y_max_rate)
        
        # Ensure minimum feedrates (at least 10% of max)
        x_min = max(1, int(x_max_rate * 0.1))
        y_min = max(1, int(y_max_rate * 0.1))
        x_feedrate = max(x_feedrate, x_min)
        y_feedrate = max(y_feedrate, y_min)
        
        return (x_feedrate, y_feedrate)
    
    def estimate_movement_time(self, from_x: float, from_y: float, 
                               to_x: float, to_y: float) -> float:
        """
        Estimate movement time for concurrent movement.
        
        Args:
            from_x: Starting X angle
            from_y: Starting Y angle
            to_x: Target X angle
            to_y: Target Y angle
            
        Returns:
            Estimated time in seconds (maximum of both axes)
        """
        x_time = self.axes[0].estimate_movement_time(from_x, to_x)
        y_time = self.axes[1].estimate_movement_time(from_y, to_y)
        
        # Both move concurrently, so time is maximum
        return max(x_time, y_time)
    
    def is_moving(self) -> bool:
        """
        Check if any axis is currently moving.
        
        Returns:
            True if any axis is moving, False if all are idle
        """
        return self.grbl_controller.is_moving()