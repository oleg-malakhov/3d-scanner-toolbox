# Tests

This directory contains tests for the OpenScanTurntable ControlApp.

## Structure

### Unit Tests (No GRBL Connection Required)
- `test_axis_calculations.py` - Tests for calculation logic (steps, degrees, conversions)
- `test_command_builder.py` - Tests for GRBL command building (pure functions)
- `test_axis_normalization.py` - Tests for angle normalization (X-axis shortest path, Y-axis clamping)
- `test_axis_validation.py` - Tests for angle validation logic

### Integration Tests (With Mocked GRBL)
- `test_axis_integration.py` - Integration tests with mocked command sender (to be created)
- `test_turntable.py` - Tests for Turntable class (to be created)

### End-to-End Tests (With Real GRBL - Optional)
- `test_axis_e2e.py` - End-to-end tests requiring hardware (to be created)
- `test_api.py` - Tests for REST API (to be created)

## Running Tests

### Prerequisites

Install test dependencies:
```bash
pip install pytest pytest-cov
```

Or install all requirements (including test dependencies):
```bash
pip install -r requirements.txt
```

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_command_builder.py -v
python -m pytest tests/test_axis_calculations.py -v
python -m pytest tests/test_axis_normalization.py -v
python -m pytest tests/test_axis_validation.py -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html

# Run only unit tests (no GRBL connection required)
python -m pytest tests/test_command_builder.py tests/test_axis_calculations.py tests/test_axis_normalization.py tests/test_axis_validation.py -v
```

## Test Coverage

### Unit Tests (No GRBL Connection Required)

These tests can run without any hardware or GRBL connection:

1. **test_command_builder.py** - Tests GRBL command building
   - Single axis move commands
   - Combined move commands
   - Work offset commands
   - Edge cases (large/small values, precision)

2. **test_axis_calculations.py** - Tests calculation logic
   - Steps/degrees conversions
   - GRBL units conversions
   - Feedrate calculations
   - Movement time estimation

3. **test_axis_normalization.py** - Tests angle normalization
   - X-axis shortest path calculation
   - Y-axis clamping
   - Edge cases (boundaries, negative angles)

4. **test_axis_validation.py** - Tests angle validation
   - X-axis accepts any angle (modular arithmetic)
   - Y-axis strict validation (-90 to 90)

### Integration Tests (With Mocked GRBL)

These tests use mocked GRBL interfaces (to be created):
- `test_axis_integration.py` - Full axis workflow with mocked command sender

### End-to-End Tests (With Real GRBL - Optional)

These tests require actual hardware (to be created):
- `test_axis_e2e.py` - Tests with real GRBL connection
