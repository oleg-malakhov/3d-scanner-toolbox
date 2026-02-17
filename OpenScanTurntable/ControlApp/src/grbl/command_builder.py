"""Pure functions for building G-code commands (testable without GRBL)."""

from typing import Optional


class GRBLCommandBuilder:
    """Pure functions for building G-code commands (testable without GRBL)."""
    
    @staticmethod
    def build_move_command(
        axis_letter: str,
        target_units: float,
        feedrate: int
    ) -> str:
        """
        Build G0 move command.
        
        Args:
            axis_letter: GRBL axis letter ('X' or 'Y')
            target_units: Target position in GRBL units
            feedrate: Feedrate in steps/min
            
        Returns:
            G-code command string, e.g., 'G0 X123.456 F60000'
        """
        return f"G0 {axis_letter}{target_units:.3f} F{feedrate}"
    
    @staticmethod
    def build_combined_move_command(
        x_units: Optional[float],
        y_units: Optional[float],
        feedrate: int
    ) -> str:
        """
        Build combined G0 move command for multiple axes.
        
        Args:
            x_units: X-axis target position in GRBL units (None to omit)
            y_units: Y-axis target position in GRBL units (None to omit)
            feedrate: Feedrate in steps/min
            
        Returns:
            G-code command string, e.g., 'G0 X123.456 Y45.789 F60000'
        """
        parts = ['G0']
        if x_units is not None:
            parts.append(f'X{x_units:.3f}')
        if y_units is not None:
            parts.append(f'Y{y_units:.3f}')
        parts.append(f'F{feedrate}')
        return ' '.join(parts)
    
    @staticmethod
    def build_work_offset_command(
        axis_letter: str,
        offset_units: float
    ) -> str:
        """
        Build G92 work offset command.
        
        Args:
            axis_letter: GRBL axis letter ('X' or 'Y')
            offset_units: Offset value in GRBL units
            
        Returns:
            G-code command string, e.g., 'G92 X0.000'
        """
        return f"G92 {axis_letter}{offset_units:.3f}"
