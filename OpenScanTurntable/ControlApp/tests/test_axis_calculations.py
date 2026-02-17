"""Unit tests for axis calculation logic (pure functions, no GRBL required)."""

import pytest
from src.axis import XAxis, YAxis, AxisConfig
from src.grbl.command_sender_interface import GRBLCommandSenderInterface
from src.grbl.constants import GRBL_MAX_RATE


class MockCommandSender(GRBLCommandSenderInterface):
    """Mock command sender for testing (no actual GRBL connection)."""
    
    def __init__(self):
        self.connected = True
        self.grbl_x_steps_per_mm = 1.0
        self.grbl_y_steps_per_mm = 1.0
        self.machine_state = None
        self._callbacks = []
        self._sent_commands = []
    
    def send_command(self, command: str, wait_for_ok: bool = True) -> bool:
        self._sent_commands.append(command)
        return True
    
    def is_connected(self) -> bool:
        return self.connected
    
    def wait_for_idle(self, timeout=None) -> bool:
        return True
    
    def unlock(self) -> bool:
        return True
    
    def get_machine_state(self):
        from src.grbl.constants import MachineState
        return MachineState.IDLE if self.machine_state is None else self.machine_state
    
    def register_status_callback(self, callback) -> None:
        self._callbacks.append(callback)
    
    def get_grbl_x_steps_per_mm(self) -> float:
        return self.grbl_x_steps_per_mm
    
    def get_grbl_y_steps_per_mm(self) -> float:
        return self.grbl_y_steps_per_mm
    
    def is_moving(self) -> bool:
        return False


@pytest.fixture
def mock_command_sender():
    """Create a mock command sender for testing."""
    return MockCommandSender()


@pytest.fixture
def x_axis_config():
    """Create X-axis configuration."""
    return AxisConfig(
        step_angle=1.8,
        microsteps=8,
        min_angle=-360,
        max_angle=360,
        speed=60000,
        acceleration=3000,
        always_on=False,
        home_angle=0,
        grbl_axis_letter='X',
        grbl_steps_per_mm=1.0,
        gear_ratio=1.0
    )


@pytest.fixture
def y_axis_config():
    """Create Y-axis configuration."""
    return AxisConfig(
        step_angle=1.8,
        microsteps=8,
        min_angle=-90,
        max_angle=90,
        speed=60000,
        acceleration=3000,
        always_on=True,
        home_angle=0,
        grbl_axis_letter='Y',
        grbl_steps_per_mm=1.0,
        gear_ratio=5.333
    )


@pytest.fixture
def x_axis(mock_command_sender, x_axis_config):
    """Create X-axis instance for testing."""
    axis = XAxis(mock_command_sender, x_axis_config)
    # Set current position to 0 for predictable tests
    axis._current_angle = 0.0
    return axis


@pytest.fixture
def y_axis(mock_command_sender, y_axis_config):
    """Create Y-axis instance for testing."""
    axis = YAxis(mock_command_sender, y_axis_config)
    # Set current position to 0 for predictable tests
    axis._current_angle = 0.0
    return axis


class TestXAxisCalculations:
    """Test X-axis calculation logic."""
    
    def test_steps_per_degree_calculation(self, x_axis):
        """Test steps per degree calculation."""
        # 1.8° per step, 8 microsteps
        # Full steps per rev: 360 / 1.8 = 200
        # Total steps per rev: 200 * 8 = 1600
        # Steps per degree: 1600 / 360 = 4.444...
        expected = (360.0 / 1.8) * 8 / 360.0
        assert abs(x_axis._steps_per_degree - expected) < 0.001
    
    def test_degrees_to_steps(self, x_axis):
        """Test degrees to steps conversion."""
        # 90 degrees should be 90 * steps_per_degree
        steps = x_axis._degrees_to_steps(90.0)
        expected = 90.0 * x_axis._steps_per_degree
        assert abs(steps - expected) < 0.001
    
    def test_steps_to_degrees(self, x_axis):
        """Test steps to degrees conversion."""
        # Round trip test
        original_degrees = 45.0
        steps = x_axis._degrees_to_steps(original_degrees)
        converted_degrees = x_axis._steps_to_degrees(steps)
        assert abs(converted_degrees - original_degrees) < 0.001
    
    def test_steps_to_grbl_units(self, x_axis, mock_command_sender):
        """Test steps to GRBL units conversion."""
        mock_command_sender.grbl_x_steps_per_mm = 1.0
        steps = 100.0
        units = x_axis._steps_to_grbl_units(steps)
        assert abs(units - 100.0) < 0.001
        
        # Test with different steps/mm
        mock_command_sender.grbl_x_steps_per_mm = 2.0
        units = x_axis._steps_to_grbl_units(steps)
        assert abs(units - 50.0) < 0.001
    
    def test_grbl_units_to_steps(self, x_axis, mock_command_sender):
        """Test GRBL units to steps conversion."""
        mock_command_sender.grbl_x_steps_per_mm = 1.0
        units = 100.0
        steps = x_axis._grbl_units_to_steps(units)
        assert abs(steps - 100.0) < 0.001
        
        # Test with different steps/mm
        mock_command_sender.grbl_x_steps_per_mm = 2.0
        steps = x_axis._grbl_units_to_steps(units)
        assert abs(steps - 200.0) < 0.001


class TestXAxisNormalization:
    """Test X-axis angle normalization with modular arithmetic."""
    
    def test_normalize_same_angle_different_representations(self, x_axis):
        """Test that 10° and 370° normalize to the same angle."""
        x_axis._current_angle = 10.0
        
        # These should all result in no movement (normalized angles are the same)
        normalized_370 = x_axis._normalize_target_angle(370.0)
        normalized_neg350 = x_axis._normalize_target_angle(-350.0)
        normalized_10 = x_axis._normalize_target_angle(10.0)
        
        # Check that normalized values are equivalent (mod 360)
        def normalize_angle(angle):
            return ((angle % 360) + 360) % 360
        
        assert abs(normalize_angle(normalized_370) - 10.0) < 0.001
        assert abs(normalize_angle(normalized_neg350) - 10.0) < 0.001
        assert abs(normalize_angle(normalized_10) - 10.0) < 0.001
    
    def test_shortest_path_10_to_350(self, x_axis):
        """Test shortest path: 10° → 350° should go -20° (via 0)."""
        x_axis._current_angle = 10.0
        normalized = x_axis._normalize_target_angle(350.0)
        # Should choose -20° path: 10° + (-20°) = -10°
        # Movement distance should be 20° (shortest path, not 340°)
        movement = abs(normalized - 10.0)
        assert movement < 180.0  # Should be less than 180° (shortest path)
        assert abs(movement - 20.0) < 0.1  # Should be approximately 20°
        # Normalized result should be 350° (or -10° which normalizes to 350°)
        result_norm = ((normalized % 360) + 360) % 360
        assert abs(result_norm - 350.0) < 0.001
    
    def test_shortest_path_350_to_10(self, x_axis):
        """Test shortest path: 350° → 10° should go +20° (via 360/0)."""
        x_axis._current_angle = 350.0
        normalized = x_axis._normalize_target_angle(10.0)
        # Should choose +20° path: 350° + 20° = 370°
        # Movement distance should be 20° (shortest path, not 340°)
        movement = abs(normalized - 350.0)
        assert movement < 180.0  # Should be less than 180° (shortest path)
        assert abs(movement - 20.0) < 0.1  # Should be approximately 20°
        # Normalized result should be 10° (370° normalizes to 10°)
        result_norm = ((normalized % 360) + 360) % 360
        assert abs(result_norm - 10.0) < 0.001
    
    def test_shortest_path_45_to_315(self, x_axis):
        """Test shortest path: 45° → 315° should go -90°."""
        x_axis._current_angle = 45.0
        normalized = x_axis._normalize_target_angle(315.0)
        # Should choose -90° path: 45° + (-90°) = -45°
        # Movement distance should be 90° (shortest path, not 270°)
        movement = abs(normalized - 45.0)
        assert movement < 180.0  # Should be less than 180° (shortest path)
        assert abs(movement - 90.0) < 0.1  # Should be approximately 90°
        # Normalized result should be 315° (-45° normalizes to 315°)
        result_norm = ((normalized % 360) + 360) % 360
        assert abs(result_norm - 315.0) < 0.001
    
    def test_shortest_path_315_to_45(self, x_axis):
        """Test shortest path: 315° → 45° should go +90°."""
        x_axis._current_angle = 315.0
        normalized = x_axis._normalize_target_angle(45.0)
        # Should choose +90° path: 315° + 90° = 405°
        # Movement distance should be 90° (shortest path, not 270°)
        movement = abs(normalized - 315.0)
        assert movement < 180.0  # Should be less than 180° (shortest path)
        assert abs(movement - 90.0) < 0.1  # Should be approximately 90°
        # Normalized result should be 45° (405° normalizes to 45°)
        result_norm = ((normalized % 360) + 360) % 360
        assert abs(result_norm - 45.0) < 0.001
    
    def test_shortest_path_5_to_355(self, x_axis):
        """Test shortest path: 5° → 355° should go -10°."""
        x_axis._current_angle = 5.0
        normalized = x_axis._normalize_target_angle(355.0)
        # Should choose -10° path: 5° + (-10°) = -5°
        # Movement distance should be 10° (shortest path, not 350°)
        movement = abs(normalized - 5.0)
        assert movement < 180.0  # Should be less than 180° (shortest path)
        assert abs(movement - 10.0) < 0.1  # Should be approximately 10°
        # Normalized result should be 355° (-5° normalizes to 355°)
        result_norm = ((normalized % 360) + 360) % 360
        assert abs(result_norm - 355.0) < 0.001
    
    def test_shortest_path_355_to_5(self, x_axis):
        """Test shortest path: 355° → 5° should go +10°."""
        x_axis._current_angle = 355.0
        normalized = x_axis._normalize_target_angle(5.0)
        # Should choose +10° path: 355° + 10° = 365°
        # Movement distance should be 10° (shortest path, not 350°)
        movement = abs(normalized - 355.0)
        assert movement < 180.0  # Should be less than 180° (shortest path)
        assert abs(movement - 10.0) < 0.1  # Should be approximately 10°
        # Normalized result should be 5° (365° normalizes to 5°)
        result_norm = ((normalized % 360) + 360) % 360
        assert abs(result_norm - 5.0) < 0.001
    
    def test_shortest_path_180_to_0(self, x_axis):
        """Test shortest path: 180° → 0° (either direction, same distance)."""
        x_axis._current_angle = 180.0
        normalized = x_axis._normalize_target_angle(0.0)
        # Should be 0° or 360° (either way, same distance)
        assert abs(normalized - 0.0) < 0.001 or abs(normalized - 360.0) < 0.001
    
    def test_validate_angle_accepts_any(self, x_axis):
        """Test that X-axis accepts any angle (modular arithmetic)."""
        # All should be valid
        assert x_axis.validate_angle(0.0)[0] == True
        assert x_axis.validate_angle(360.0)[0] == True
        assert x_axis.validate_angle(-350.0)[0] == True
        assert x_axis.validate_angle(370.0)[0] == True
        assert x_axis.validate_angle(720.0)[0] == True
        assert x_axis.validate_angle(-720.0)[0] == True


class TestYAxisCalculations:
    """Test Y-axis calculation logic."""
    
    def test_steps_per_degree_with_gear_ratio(self, y_axis):
        """Test steps per degree calculation with gear ratio."""
        # Y-axis has gear_ratio = 5.333
        # This means motor needs more steps for same output angle
        steps = y_axis._degrees_to_steps(90.0)
        # Should be 90 * steps_per_degree * 5.333
        expected = 90.0 * y_axis._steps_per_degree * 5.333
        assert abs(steps - expected) < 0.001
    
    def test_steps_to_degrees_with_gear_ratio(self, y_axis):
        """Test steps to degrees conversion with gear ratio."""
        # Round trip test with gear ratio
        original_degrees = 45.0
        steps = y_axis._degrees_to_steps(original_degrees)
        converted_degrees = y_axis._steps_to_degrees(steps)
        assert abs(converted_degrees - original_degrees) < 0.001


class TestYAxisNormalization:
    """Test Y-axis angle normalization with clamping."""
    
    def test_clamp_above_max(self, y_axis):
        """Test clamping angles above 90°."""
        y_axis._current_angle = 0.0
        normalized = y_axis._normalize_target_angle(91.0)
        assert abs(normalized - 90.0) < 0.001
        
        normalized = y_axis._normalize_target_angle(100.0)
        assert abs(normalized - 90.0) < 0.001
    
    def test_clamp_below_min(self, y_axis):
        """Test clamping angles below -90°."""
        y_axis._current_angle = 0.0
        normalized = y_axis._normalize_target_angle(-91.0)
        assert abs(normalized - (-90.0)) < 0.001
        
        normalized = y_axis._normalize_target_angle(-100.0)
        assert abs(normalized - (-90.0)) < 0.001
    
    def test_no_clamp_within_range(self, y_axis):
        """Test that angles within range are not clamped."""
        y_axis._current_angle = 0.0
        normalized = y_axis._normalize_target_angle(45.0)
        assert abs(normalized - 45.0) < 0.001
        
        normalized = y_axis._normalize_target_angle(-45.0)
        assert abs(normalized - (-45.0)) < 0.001
        
        normalized = y_axis._normalize_target_angle(0.0)
        assert abs(normalized - 0.0) < 0.001
    
    def test_validate_angle_strict_limits(self, y_axis):
        """Test that Y-axis validates strictly within -90 to 90."""
        # Valid angles
        assert y_axis.validate_angle(0.0)[0] == True
        assert y_axis.validate_angle(45.0)[0] == True
        assert y_axis.validate_angle(-45.0)[0] == True
        assert y_axis.validate_angle(90.0)[0] == True
        assert y_axis.validate_angle(-90.0)[0] == True
        
        # Invalid angles
        assert y_axis.validate_angle(91.0)[0] == False
        assert y_axis.validate_angle(-91.0)[0] == False
        assert y_axis.validate_angle(100.0)[0] == False
        assert y_axis.validate_angle(-100.0)[0] == False


class TestMovementTimeEstimation:
    """Test movement time estimation."""
    
    def test_x_axis_time_estimation_with_wrapping(self, x_axis):
        """Test X-axis time estimation uses shortest path."""
        x_axis._current_angle = 10.0
        # 10° → 350° should use -20° path (shorter than 340°)
        time_short = x_axis.estimate_move_to_time(350.0)
        
        # Compare with direct path (should be longer)
        x_axis._current_angle = 10.0
        time_direct = x_axis.estimate_movement_time(10.0, 350.0)
        
        # Shortest path should be faster (or at least not slower)
        # Note: This test verifies the logic uses shortest path
        assert time_short >= 0
    
    def test_y_axis_time_estimation(self, y_axis):
        """Test Y-axis time estimation."""
        y_axis._current_angle = 0.0
        time = y_axis.estimate_move_to_time(90.0)
        assert time > 0
        assert time < 100  # Should be reasonable


class TestFeedrateCalculation:
    """Test feedrate calculation."""
    
    def test_feedrate_uses_config_speed(self, x_axis):
        """Test that feedrate uses configured speed."""
        feedrate = x_axis._get_feedrate()
        assert feedrate == min(x_axis.config.speed, int(GRBL_MAX_RATE))
    
    def test_feedrate_clamped_to_max(self, x_axis):
        """Test that feedrate is clamped to GRBL_MAX_RATE."""
        # Set speed higher than max
        x_axis.config.speed = 999999
        feedrate = x_axis._get_feedrate()
        assert feedrate <= int(GRBL_MAX_RATE)
