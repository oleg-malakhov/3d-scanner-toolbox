"""Coordinate system conversion between angles and GRBL positions."""

from typing import Tuple, Optional
from src.utils.config import Config


class CoordinateSystem:
    """Handles conversion between angles (degrees) and GRBL coordinates."""
    
    def __init__(self, config: Config):
        """
        Initialize coordinate system.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self._x_steps_per_degree = None
        self._y_steps_per_degree = None
        self._update_steps_per_degree()
    
    def _update_steps_per_degree(self) -> None:
        """Update steps per degree calculations from configuration."""
        # X-axis
        x_step_angle = self.config.get('motors.x_axis.step_angle', 1.8)
        x_microsteps = self.config.get('motors.x_axis.microsteps', 0)
        # If microsteps is 0 or less, microstepping is disabled (use full steps only)
        if x_microsteps <= 0:
            x_microsteps = 1  # Use 1 for calculation (no microstepping)
            x_microsteps_enabled = False
        else:
            x_microsteps_enabled = True
        
        # Calculation: (360 / step_angle) * microsteps / 360
        # = full_steps_per_rev * microsteps / degrees_per_rev
        # If microstepping disabled: (360 / 1.8) * 1 / 360 = 200 / 360
        x_full_steps_per_rev = 360.0 / x_step_angle
        x_total_steps_per_rev = x_full_steps_per_rev * x_microsteps
        self._x_steps_per_degree = x_total_steps_per_rev / 360.0
        
        # Y-axis
        y_step_angle = self.config.get('motors.y_axis.step_angle', 1.8)
        y_microsteps = self.config.get('motors.y_axis.microsteps', 0)
        # If microsteps is 0 or less, microstepping is disabled (use full steps only)
        if y_microsteps <= 0:
            y_microsteps = 1  # Use 1 for calculation (no microstepping)
            y_microsteps_enabled = False
        else:
            y_microsteps_enabled = True
        
        y_full_steps_per_rev = 360.0 / y_step_angle
        y_total_steps_per_rev = y_full_steps_per_rev * y_microsteps
        self._y_steps_per_degree = y_total_steps_per_rev / 360.0
        
        # Print calculated values with detailed breakdown
        print(f"Coordinate System Configuration:")
        print(f"  X-axis:")
        print(f"    Step angle: {x_step_angle}° per full step")
        if x_microsteps_enabled:
            print(f"    Microsteps: {x_microsteps} per full step (enabled)")
        else:
            print(f"    Microsteps: disabled (using full steps only)")
        print(f"    Full steps per revolution: {x_full_steps_per_rev:.1f} (360° / {x_step_angle}°)")
        print(f"    Total steps per revolution: {x_total_steps_per_rev:.1f} ({x_full_steps_per_rev:.1f} × {x_microsteps})")
        print(f"    Steps per degree: {self._x_steps_per_degree:.6f} ({x_total_steps_per_rev:.1f} / 360°)")
        print(f"  Y-axis:")
        print(f"    Step angle: {y_step_angle}° per full step")
        if y_microsteps_enabled:
            print(f"    Microsteps: {y_microsteps} per full step (enabled)")
        else:
            print(f"    Microsteps: disabled (using full steps only)")
        print(f"    Full steps per revolution: {y_full_steps_per_rev:.1f} (360° / {y_step_angle}°)")
        print(f"    Total steps per revolution: {y_total_steps_per_rev:.1f} ({y_full_steps_per_rev:.1f} × {y_microsteps})")
        print(f"    Steps per degree: {self._y_steps_per_degree:.6f} ({y_total_steps_per_rev:.1f} / 360°)")
    
    def angle_to_position(self, axis: str, angle: float) -> float:
        """
        Convert angle (degrees) to GRBL position.
        
        Args:
            axis: 'x' or 'y'
            angle: Angle in degrees
            
        Returns:
            Position value for GRBL
        """
        if axis.lower() == 'x':
            step_angle = self.config.get('motors.x_axis.step_angle', 1.8)
            microsteps_config = self.config.get('motors.x_axis.microsteps', 0)
            microsteps = microsteps_config if microsteps_config > 0 else 1
            microsteps_enabled = microsteps_config > 0
            steps_per_degree = self._x_steps_per_degree
            
            # Detailed calculation breakdown
            full_steps_per_rev = 360.0 / step_angle
            total_steps_per_rev = full_steps_per_rev * microsteps
            position = angle * steps_per_degree
            steps = int(position)
            remainder = position - steps
            
            print(f"        Detailed calculation:")
            print(f"          Full steps per revolution: {full_steps_per_rev:.1f} (360° / {step_angle}°)")
            if microsteps_enabled:
                print(f"          Microsteps: {microsteps} per full step (enabled)")
                print(f"          Total steps per revolution: {total_steps_per_rev:.1f} ({full_steps_per_rev:.1f} × {microsteps})")
                step_type = "microsteps"
            else:
                print(f"          Microsteps: disabled (using full steps only)")
                print(f"          Total steps per revolution: {total_steps_per_rev:.1f} (full steps only)")
                step_type = "full steps"
            print(f"          Steps per degree: {steps_per_degree:.6f} ({total_steps_per_rev:.1f} / 360°)")
            print(f"          For {angle}°: {angle}° × {steps_per_degree:.6f} = {position:.6f} steps")
            print(f"          Breakdown: {steps} {step_type} + {remainder:.6f} fractional {step_type}")
            return position
        elif axis.lower() == 'y':
            step_angle = self.config.get('motors.y_axis.step_angle', 1.8)
            microsteps_config = self.config.get('motors.y_axis.microsteps', 0)
            microsteps = microsteps_config if microsteps_config > 0 else 1
            microsteps_enabled = microsteps_config > 0
            steps_per_degree = self._y_steps_per_degree
            
            # Detailed calculation breakdown
            full_steps_per_rev = 360.0 / step_angle
            total_steps_per_rev = full_steps_per_rev * microsteps
            position = angle * steps_per_degree
            steps = int(position)
            remainder = position - steps
            
            print(f"        Detailed calculation:")
            print(f"          Full steps per revolution: {full_steps_per_rev:.1f} (360° / {step_angle}°)")
            if microsteps_enabled:
                print(f"          Microsteps: {microsteps} per full step (enabled)")
                print(f"          Total steps per revolution: {total_steps_per_rev:.1f} ({full_steps_per_rev:.1f} × {microsteps})")
                step_type = "microsteps"
            else:
                print(f"          Microsteps: disabled (using full steps only)")
                print(f"          Total steps per revolution: {total_steps_per_rev:.1f} (full steps only)")
                step_type = "full steps"
            print(f"          Steps per degree: {steps_per_degree:.6f} ({total_steps_per_rev:.1f} / 360°)")
            print(f"          For {angle}°: {angle}° × {steps_per_degree:.6f} = {position:.6f} steps")
            print(f"          Breakdown: {steps} {step_type} + {remainder:.6f} fractional {step_type}")
            return position
        else:
            raise ValueError(f"Invalid axis: {axis}. Must be 'x' or 'y'")
    
    def position_to_angle(self, axis: str, position: float) -> float:
        """
        Convert GRBL position to angle (degrees).
        
        Args:
            axis: 'x' or 'y'
            position: Position value from GRBL
            
        Returns:
            Angle in degrees
        """
        if axis.lower() == 'x':
            return position / self._x_steps_per_degree
        elif axis.lower() == 'y':
            return position / self._y_steps_per_degree
        else:
            raise ValueError(f"Invalid axis: {axis}. Must be 'x' or 'y'")
    
    def validate_angle(self, axis: str, angle: float) -> Tuple[bool, Optional[str]]:
        """
        Validate if angle is within allowed range.
        
        Args:
            axis: 'x' or 'y'
            angle: Angle in degrees to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if axis.lower() == 'x':
            min_angle = self.config.get('motors.x_axis.min_angle', 0)
            max_angle = self.config.get('motors.x_axis.max_angle', 360)
            
            # X-axis can wrap around, but validate basic range
            if angle < min_angle or angle > max_angle:
                # Allow wrapping for continuous rotation
                if max_angle == 360:
                    # Normalize to 0-360 range
                    angle = angle % 360
                    return True, None
                return False, f"X-axis angle must be between {min_angle}° and {max_angle}°"
            return True, None
            
        elif axis.lower() == 'y':
            min_angle = self.config.get('motors.y_axis.min_angle', -90)
            max_angle = self.config.get('motors.y_axis.max_angle', 90)
            
            if angle < min_angle or angle > max_angle:
                return False, f"Y-axis angle must be between {min_angle}° and {max_angle}°"
            return True, None
        else:
            return False, f"Invalid axis: {axis}"
    
    def get_feedrate(self, axis: str) -> int:
        """
        Get maximum feedrate for an axis.
        
        Args:
            axis: 'x' or 'y'
            
        Returns:
            Maximum feedrate
        """
        # Use hardcoded max rate
        from src.axis import GRBL_MAX_RATE
        return int(GRBL_MAX_RATE)
    
    def get_home_position(self) -> Tuple[float, float]:
        """
        Get home position in degrees.
        
        Returns:
            Tuple of (x_angle, y_angle)
        """
        x = self.config.get('home_position.x', 0)
        y = self.config.get('home_position.y', 0)
        return (x, y)

