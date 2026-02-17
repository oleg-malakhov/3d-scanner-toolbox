"""Unit tests for axis angle normalization logic."""

import pytest
from src.axis import XAxis, YAxis, AxisConfig
from src.grbl.command_sender_interface import GRBLCommandSenderInterface
from src.grbl.constants import MachineState


class MockCommandSender(GRBLCommandSenderInterface):
    """Mock command sender for testing."""
    
    def __init__(self):
        self.connected = True
        self.grbl_x_steps_per_mm = 1.0
        self.grbl_y_steps_per_mm = 1.0
        self.machine_state = MachineState.IDLE
        self._callbacks = []
    
    def send_command(self, command: str, wait_for_ok: bool = True) -> bool:
        return True
    
    def is_connected(self) -> bool:
        return self.connected
    
    def wait_for_idle(self, timeout=None) -> bool:
        return True
    
    def unlock(self) -> bool:
        return True
    
    def get_machine_state(self):
        return self.machine_state
    
    def register_status_callback(self, callback) -> None:
        self._callbacks.append(callback)
    
    def get_grbl_x_steps_per_mm(self) -> float:
        return self.grbl_x_steps_per_mm
    
    def get_grbl_y_steps_per_mm(self) -> float:
        return self.grbl_y_steps_per_mm
    
    def is_moving(self) -> bool:
        return False


@pytest.fixture
def x_axis():
    """Create X-axis for testing."""
    config = AxisConfig(
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
    axis = XAxis(MockCommandSender(), config)
    return axis


@pytest.fixture
def y_axis():
    """Create Y-axis for testing."""
    config = AxisConfig(
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
    axis = YAxis(MockCommandSender(), config)
    return axis


class TestXAxisShortestPath:
    """Test X-axis shortest path calculation."""
    
    def test_same_angle_no_movement(self, x_axis):
        """Test that same angle (different representations) requires no movement."""
        x_axis._current_angle = 10.0
        
        # All these should return the target as-is (no movement needed)
        # The normalized angles are the same, so shortest path returns target
        result1 = x_axis._calculate_shortest_path(10.0, 10.0)
        assert abs(result1 - 10.0) < 0.001 or abs(((result1 % 360) + 360) % 360 - 10.0) < 0.001
        
        result2 = x_axis._calculate_shortest_path(10.0, 370.0)
        # 370° normalizes to 10°, so should return 370° (or 10° if same)
        assert abs(result2 - 370.0) < 0.001 or abs(((result2 % 360) + 360) % 360 - 10.0) < 0.001
        
        result3 = x_axis._calculate_shortest_path(10.0, -350.0)
        # -350° normalizes to 10°, so should return -350° (or 10° if same)
        assert abs(result3 - (-350.0)) < 0.001 or abs(((result3 % 360) + 360) % 360 - 10.0) < 0.001
    
    def test_shortest_path_10_to_350(self, x_axis):
        """Test: 10° → 350° should choose -20° path."""
        x_axis._current_angle = 10.0
        result = x_axis._calculate_shortest_path(10.0, 350.0)
        # Should be -10° (10° + (-20°) = -10°, which is 350° normalized)
        # Movement distance should be 20° (shortest path)
        movement = abs(result - 10.0)
        assert movement < 180.0  # Should be less than 180° (shortest path)
        # Normalized result should be 350°
        result_norm = ((result % 360) + 360) % 360
        assert abs(result_norm - 350.0) < 0.001 or abs(result - (-10.0)) < 0.001
    
    def test_shortest_path_350_to_10(self, x_axis):
        """Test: 350° → 10° should choose +20° path."""
        x_axis._current_angle = 350.0
        result = x_axis._calculate_shortest_path(350.0, 10.0)
        # Should be 370° (350° + 20° = 370°, which is 10° normalized)
        # Movement distance should be 20° (shortest path)
        movement = abs(result - 350.0)
        assert movement < 180.0  # Should be less than 180° (shortest path)
        # Normalized result should be 10°
        result_norm = ((result % 360) + 360) % 360
        assert abs(result_norm - 10.0) < 0.001 or abs(result - 370.0) < 0.001
    
    def test_shortest_path_45_to_315(self, x_axis):
        """Test: 45° → 315° should choose -90° path."""
        x_axis._current_angle = 45.0
        result = x_axis._calculate_shortest_path(45.0, 315.0)
        # Should be -45° (45° + (-90°) = -45°, which is 315° normalized)
        # Movement distance should be 90° (shortest path, not 270°)
        movement = abs(result - 45.0)
        assert movement < 180.0  # Should be less than 180° (shortest path)
        assert abs(movement - 90.0) < 0.1  # Should be approximately 90°
        # Normalized result should be 315° (-45° normalizes to 315°)
        result_norm = ((result % 360) + 360) % 360
        assert abs(result_norm - 315.0) < 0.001
    
    def test_shortest_path_315_to_45(self, x_axis):
        """Test: 315° → 45° should choose +90° path."""
        x_axis._current_angle = 315.0
        result = x_axis._calculate_shortest_path(315.0, 45.0)
        # Should be 405° (315° + 90° = 405°, which is 45° normalized)
        # Movement distance should be 90° (shortest path, not 270°)
        movement = abs(result - 315.0)
        assert movement < 180.0  # Should be less than 180° (shortest path)
        assert abs(movement - 90.0) < 0.1  # Should be approximately 90°
        # Normalized result should be 45° (405° normalizes to 45°)
        result_norm = ((result % 360) + 360) % 360
        assert abs(result_norm - 45.0) < 0.001
    
    def test_shortest_path_5_to_355(self, x_axis):
        """Test: 5° → 355° should choose -10° path."""
        x_axis._current_angle = 5.0
        result = x_axis._calculate_shortest_path(5.0, 355.0)
        # Should be -5° (5° + (-10°) = -5°, which is 355° normalized)
        # Movement distance should be 10° (shortest path, not 350°)
        movement = abs(result - 5.0)
        assert movement < 180.0  # Should be less than 180° (shortest path)
        assert abs(movement - 10.0) < 0.1  # Should be approximately 10°
        # Normalized result should be 355° (-5° normalizes to 355°)
        result_norm = ((result % 360) + 360) % 360
        assert abs(result_norm - 355.0) < 0.001
    
    def test_shortest_path_355_to_5(self, x_axis):
        """Test: 355° → 5° should choose +10° path."""
        x_axis._current_angle = 355.0
        result = x_axis._calculate_shortest_path(355.0, 5.0)
        # Should be 365° (355° + 10° = 365°, which is 5° normalized)
        # Movement distance should be 10° (shortest path, not 350°)
        movement = abs(result - 355.0)
        assert movement < 180.0  # Should be less than 180° (shortest path)
        assert abs(movement - 10.0) < 0.1  # Should be approximately 10°
        # Normalized result should be 5° (365° normalizes to 5°)
        result_norm = ((result % 360) + 360) % 360
        assert abs(result_norm - 5.0) < 0.001
    
    def test_shortest_path_180_to_0(self, x_axis):
        """Test: 180° → 0° (either direction, same distance)."""
        x_axis._current_angle = 180.0
        result = x_axis._calculate_shortest_path(180.0, 0.0)
        # Should be 0° or 360° (either way, same distance)
        assert abs(result - 0.0) < 0.001 or abs(result - 360.0) < 0.001
    
    def test_shortest_path_negative_angles(self, x_axis):
        """Test shortest path with negative angles."""
        x_axis._current_angle = 10.0
        # -350° normalizes to 10°, so no movement (returns target as-is)
        result = x_axis._calculate_shortest_path(10.0, -350.0)
        result_norm = ((result % 360) + 360) % 360
        assert abs(result_norm - 10.0) < 0.001
        
        x_axis._current_angle = -10.0
        # -10° = 350°, -350° = 10°, so shortest path is +20°
        result = x_axis._calculate_shortest_path(-10.0, -350.0)
        # -10° + 20° = 10° (or 370°), which normalizes to 10°
        result_norm = ((result % 360) + 360) % 360
        assert abs(result_norm - 10.0) < 0.001
        # Movement should be 20° (shortest path)
        movement = abs(result - (-10.0))
        assert movement < 180.0
    
    def test_shortest_path_4_95_to_neg29(self, x_axis):
        """Test the specific case from the bug report: 4.95° → -29°."""
        x_axis._current_angle = 4.95
        result = x_axis._calculate_shortest_path(4.95, -29.0)
        # Should use shortest path: -33.95° (not +326.05°)
        # Result should be 4.95 + (-33.95) = -29.0
        movement = abs(result - 4.95)
        assert movement < 180.0  # Should be less than 180° (shortest path)
        assert abs(movement - 33.95) < 0.1  # Should be approximately 33.95°
        # Final target should be -29.0° (or close to it)
        assert abs(result - (-29.0)) < 0.1
    
    def test_shortest_path_large_angles(self, x_axis):
        """Test shortest path with angles > 360."""
        x_axis._current_angle = 10.0
        # 370° normalizes to 10°, so no movement (returns target as-is)
        result = x_axis._calculate_shortest_path(10.0, 370.0)
        result_norm = ((result % 360) + 360) % 360
        assert abs(result_norm - 10.0) < 0.001
        
        x_axis._current_angle = 10.0
        # 730° normalizes to 10°, so no movement (returns target as-is)
        result = x_axis._calculate_shortest_path(10.0, 730.0)
        result_norm = ((result % 360) + 360) % 360
        assert abs(result_norm - 10.0) < 0.001


class TestXAxisNormalization:
    """Test X-axis angle normalization."""
    
    def test_normalize_with_shortest_path(self, x_axis):
        """Test that normalization applies shortest path."""
        x_axis._current_angle = 10.0
        normalized = x_axis._normalize_target_angle(350.0)
        # Should use shortest path: 10° + (-20°) = -10°
        # Movement distance should be 20° (shortest path, not 340°)
        movement = abs(normalized - 10.0)
        assert movement < 180.0  # Should be less than 180° (shortest path)
        # Normalized result should be 350° (-10° normalizes to 350°)
        result_norm = ((normalized % 360) + 360) % 360
        assert abs(result_norm - 350.0) < 0.001
    
    def test_normalize_negative_angle(self, x_axis):
        """Test normalization of negative angles."""
        x_axis._current_angle = 0.0
        normalized = x_axis._normalize_target_angle(-45.0)
        # Should use shortest path: 0° + (-45°) = -45°
        # Movement distance should be 45° (shortest path, not 315°)
        movement = abs(normalized - 0.0)
        assert movement < 180.0  # Should be less than 180° (shortest path)
        # Normalized result should be 315° (-45° normalizes to 315°)
        result_norm = ((normalized % 360) + 360) % 360
        assert abs(result_norm - 315.0) < 0.001
    
    def test_normalize_angle_greater_than_360(self, x_axis):
        """Test normalization of angles > 360."""
        x_axis._current_angle = 0.0
        normalized = x_axis._normalize_target_angle(405.0)
        # 405° normalizes to 45°
        assert abs(normalized - 45.0) < 0.001


class TestYAxisClamping:
    """Test Y-axis angle clamping."""
    
    def test_clamp_above_90(self, y_axis):
        """Test clamping angles above 90°."""
        y_axis._current_angle = 0.0
        normalized = y_axis._normalize_target_angle(91.0)
        assert abs(normalized - 90.0) < 0.001
        
        normalized = y_axis._normalize_target_angle(100.0)
        assert abs(normalized - 90.0) < 0.001
        
        normalized = y_axis._normalize_target_angle(180.0)
        assert abs(normalized - 90.0) < 0.001
    
    def test_clamp_below_neg90(self, y_axis):
        """Test clamping angles below -90°."""
        y_axis._current_angle = 0.0
        normalized = y_axis._normalize_target_angle(-91.0)
        assert abs(normalized - (-90.0)) < 0.001
        
        normalized = y_axis._normalize_target_angle(-100.0)
        assert abs(normalized - (-90.0)) < 0.001
        
        normalized = y_axis._normalize_target_angle(-180.0)
        assert abs(normalized - (-90.0)) < 0.001
    
    def test_no_clamp_within_range(self, y_axis):
        """Test that angles within range are not clamped."""
        y_axis._current_angle = 0.0
        
        test_cases = [-90.0, -45.0, 0.0, 45.0, 90.0]
        for angle in test_cases:
            normalized = y_axis._normalize_target_angle(angle)
            assert abs(normalized - angle) < 0.001
    
    def test_clamp_boundary_values(self, y_axis):
        """Test clamping at boundary values."""
        y_axis._current_angle = 0.0
        
        # Exactly at boundaries should not be clamped
        assert abs(y_axis._normalize_target_angle(90.0) - 90.0) < 0.001
        assert abs(y_axis._normalize_target_angle(-90.0) - (-90.0)) < 0.001
        
        # Just outside boundaries should be clamped
        assert abs(y_axis._normalize_target_angle(90.001) - 90.0) < 0.001
        assert abs(y_axis._normalize_target_angle(-90.001) - (-90.0)) < 0.001
