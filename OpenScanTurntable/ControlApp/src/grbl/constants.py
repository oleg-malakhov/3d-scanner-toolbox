"""Constants and enums for GRBL communication."""

from enum import Enum


# GRBL Configuration
GRBL_MAX_RATE = 15000.0  # steps/min

# Buffer Configuration
RX_BUFFER_SIZE = 128  # GRBL's default receive buffer size
AVG_COMMAND_SIZE = 20  # Average command size for buffer accounting

# Timeouts
RESPONSE_TIMEOUT = 30.0  # Wait for GRBL ok (long moves can delay serial responses)
MAX_CONSECUTIVE_ERRORS = 10  # Max errors before stopping status polling
STATUS_POLL_LOCK_TIMEOUT = 0.01  # 10ms timeout for status poll lock
MIN_MOVEMENT_TIMEOUT = 15.0  # Minimum wait for move completion
MOVEMENT_TIMEOUT_BUFFER = 20.0  # Extra seconds added to estimated move time
POSITION_AT_TARGET_TOLERANCE = 1.0  # degrees — for completion fallback

# Movement Detection
POSITION_STABLE_THRESHOLD = 5  # Number of checks for position stability
POSITION_CHANGE_THRESHOLD = 0.001  # Minimum position change to consider movement


class MachineState(Enum):
    """GRBL machine states."""
    IDLE = "Idle"
    RUN = "Run"
    HOLD = "Hold"
    JOG = "Jog"
    ALARM = "Alarm"
    DOOR = "Door"
    CHECK = "Check"
    HOME = "Home"
    SLEEP = "Sleep"
    UNKNOWN = "Unknown"
