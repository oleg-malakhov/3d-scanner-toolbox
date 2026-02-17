"""Unit tests for GRBL command building (pure functions, no GRBL required)."""

import pytest
from src.grbl.command_builder import GRBLCommandBuilder


class TestGRBLCommandBuilder:
    """Test GRBL command builder pure functions."""
    
    def test_build_move_command_x_axis(self):
        """Test building G0 move command for X-axis."""
        command = GRBLCommandBuilder.build_move_command('X', 123.456, 60000)
        assert command == "G0 X123.456 F60000"
    
    def test_build_move_command_y_axis(self):
        """Test building G0 move command for Y-axis."""
        command = GRBLCommandBuilder.build_move_command('Y', 45.789, 50000)
        assert command == "G0 Y45.789 F50000"
    
    def test_build_move_command_precision(self):
        """Test that command builder uses correct precision."""
        command = GRBLCommandBuilder.build_move_command('X', 123.456789, 60000)
        # Should be rounded to 3 decimal places
        assert "X123.457" in command or "X123.456" in command
        assert "F60000" in command
    
    def test_build_move_command_zero_position(self):
        """Test building command with zero position."""
        command = GRBLCommandBuilder.build_move_command('X', 0.0, 60000)
        assert command == "G0 X0.000 F60000"
    
    def test_build_move_command_negative_position(self):
        """Test building command with negative position."""
        command = GRBLCommandBuilder.build_move_command('Y', -45.123, 60000)
        assert command == "G0 Y-45.123 F60000"
    
    def test_build_combined_move_command_both_axes(self):
        """Test building combined move command with both axes."""
        command = GRBLCommandBuilder.build_combined_move_command(123.456, 45.789, 60000)
        assert "G0" in command
        assert "X123.456" in command
        assert "Y45.789" in command
        assert "F60000" in command
        # Check order (should be G0 X... Y... F...)
        parts = command.split()
        assert parts[0] == "G0"
        assert "X" in parts[1]
        assert "Y" in parts[2]
        assert "F" in parts[3]
    
    def test_build_combined_move_command_x_only(self):
        """Test building combined move command with X-axis only."""
        command = GRBLCommandBuilder.build_combined_move_command(123.456, None, 60000)
        assert "G0" in command
        assert "X123.456" in command
        assert "Y" not in command
        assert "F60000" in command
    
    def test_build_combined_move_command_y_only(self):
        """Test building combined move command with Y-axis only."""
        command = GRBLCommandBuilder.build_combined_move_command(None, 45.789, 60000)
        assert "G0" in command
        assert "Y45.789" in command
        assert "X" not in command
        assert "F60000" in command
    
    def test_build_combined_move_command_zero_feedrate(self):
        """Test building command with zero feedrate (edge case)."""
        command = GRBLCommandBuilder.build_combined_move_command(123.456, 45.789, 0)
        assert "F0" in command
    
    def test_build_work_offset_command_x_axis(self):
        """Test building G92 work offset command for X-axis."""
        command = GRBLCommandBuilder.build_work_offset_command('X', 0.0)
        assert command == "G92 X0.000"
    
    def test_build_work_offset_command_y_axis(self):
        """Test building G92 work offset command for Y-axis."""
        command = GRBLCommandBuilder.build_work_offset_command('Y', 123.456)
        assert command == "G92 Y123.456"
    
    def test_build_work_offset_command_negative(self):
        """Test building work offset command with negative value."""
        command = GRBLCommandBuilder.build_work_offset_command('X', -45.123)
        assert command == "G92 X-45.123"
    
    def test_build_work_offset_command_precision(self):
        """Test that work offset command uses correct precision."""
        command = GRBLCommandBuilder.build_work_offset_command('Y', 123.456789)
        # Should be rounded to 3 decimal places
        assert "Y123.457" in command or "Y123.456" in command


class TestCommandBuilderEdgeCases:
    """Test edge cases for command building."""
    
    def test_very_large_values(self):
        """Test building commands with very large values."""
        command = GRBLCommandBuilder.build_move_command('X', 999999.999, 999999)
        assert "X" in command
        assert "F999999" in command
    
    def test_very_small_values(self):
        """Test building commands with very small values."""
        command = GRBLCommandBuilder.build_move_command('Y', 0.001, 1)
        assert "Y0.001" in command or "Y0.000" in command
        assert "F1" in command
    
    def test_command_format_consistency(self):
        """Test that command format is consistent."""
        commands = [
            GRBLCommandBuilder.build_move_command('X', 100.0, 60000),
            GRBLCommandBuilder.build_move_command('Y', 50.0, 60000),
            GRBLCommandBuilder.build_combined_move_command(100.0, 50.0, 60000),
        ]
        
        # All should start with G0
        for cmd in commands:
            assert cmd.startswith("G0")
        
        # All should have F parameter
        for cmd in commands:
            assert "F" in cmd
    
    def test_command_no_whitespace_issues(self):
        """Test that commands don't have extra whitespace."""
        command = GRBLCommandBuilder.build_combined_move_command(100.0, 50.0, 60000)
        # Should not have double spaces
        assert "  " not in command
        # Should not start/end with space
        assert not command.startswith(" ")
        assert not command.endswith(" ")
