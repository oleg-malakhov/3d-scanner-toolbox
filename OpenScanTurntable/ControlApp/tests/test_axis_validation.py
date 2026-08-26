"""Unit tests for axis angle validation logic."""

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
    return XAxis(MockCommandSender(), config)


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
    return YAxis(MockCommandSender(), config)


class TestXAxisValidation:
    """Test X-axis angle validation (accepts any angle)."""
    
    def test_validate_any_angle(self, x_axis):
        """Test that X-axis accepts any angle."""
        # All should be valid
        test_angles = [
            0.0, 45.0, 90.0, 180.0, 270.0, 360.0,
            -45.0, -90.0, -180.0, -270.0, -360.0,
            370.0, 720.0, -350.0, -720.0,
            1000.0, -1000.0
        ]
        
        for angle in test_angles:
            is_valid, error_msg = x_axis.validate_angle(angle)
            assert is_valid == True, f"Angle {angle} should be valid"
            assert error_msg is None
    
    def test_validate_normalizes_angles(self, x_axis):
        """Test that validation normalizes angles (for logging)."""
        # Validation should work (no error), but may log normalization
        is_valid, error_msg = x_axis.validate_angle(370.0)
        assert is_valid == True
        assert error_msg is None
        
        is_valid, error_msg = x_axis.validate_angle(-350.0)
        assert is_valid == True
        assert error_msg is None


class TestYAxisValidation:
    """Test Y-axis angle validation (strict limits)."""
    
    def test_validate_within_range(self, y_axis):
        """Test validation of angles within valid range."""
        valid_angles = [-90.0, -45.0, 0.0, 45.0, 90.0]
        
        for angle in valid_angles:
            is_valid, error_msg = y_axis.validate_angle(angle)
            assert is_valid == True, f"Angle {angle} should be valid"
            assert error_msg is None
    
    def test_validate_boundary_values(self, y_axis):
        """Test validation at boundary values."""
        # Exactly at boundaries should be valid
        assert y_axis.validate_angle(90.0)[0] == True
        assert y_axis.validate_angle(-90.0)[0] == True
    
    def test_validate_above_max(self, y_axis):
        """Test validation rejects angles above 90°."""
        invalid_angles = [91.0, 100.0, 180.0, 360.0]
        
        for angle in invalid_angles:
            is_valid, error_msg = y_axis.validate_angle(angle)
            assert is_valid == False, f"Angle {angle} should be invalid"
            assert error_msg is not None
            assert "Y-axis angle must be between" in error_msg
            assert "-90" in error_msg
            assert "90" in error_msg
    
    def test_validate_below_min(self, y_axis):
        """Test validation rejects angles below -90°."""
        invalid_angles = [-91.0, -100.0, -180.0, -360.0]
        
        for angle in invalid_angles:
            is_valid, error_msg = y_axis.validate_angle(angle)
            assert is_valid == False, f"Angle {angle} should be invalid"
            assert error_msg is not None
            assert "Y-axis angle must be between" in error_msg
    
    def test_validate_error_message_format(self, y_axis):
        """Test that error messages are properly formatted."""
        is_valid, error_msg = y_axis.validate_angle(100.0)
        assert is_valid == False
        assert isinstance(error_msg, str)
        assert len(error_msg) > 0
        assert "Y-axis" in error_msg
        assert "-90" in error_msg
        assert "90" in error_msg
