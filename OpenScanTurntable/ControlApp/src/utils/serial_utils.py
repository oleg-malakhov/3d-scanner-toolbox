"""Serial port utilities for GRBL communication."""

import serial
import serial.tools.list_ports
from typing import List, Optional, Tuple, Callable
import time


def list_serial_ports() -> List[Tuple[str, str, bool]]:
    """
    List all available serial ports with USB detection.
    
    Returns:
        List of tuples (port_name, description, is_usb)
    """
    ports = []
    for port in serial.tools.list_ports.comports():
        port_name = port.device
        description = port.description or ""
        
        # Check if port is USB
        is_usb = False
        
        # Check port name for USB indicators
        port_lower = port_name.lower()
        if any(indicator in port_lower for indicator in ['usb', 'ttyusb', 'ttyacm', 'cu.usb', 'cu.usbserial']):
            is_usb = True
        
        # Check description for USB indicators
        desc_lower = description.lower()
        if any(indicator in desc_lower for indicator in ['usb', 'serial', 'ch340', 'ftdi', 'cp210', 'pl2303']):
            is_usb = True
        
        # Check if port has VID/PID (indicates USB device)
        if hasattr(port, 'vid') and port.vid is not None:
            is_usb = True
        
        ports.append((port_name, description, is_usb))
    
    return ports


def is_grbl_device(port: str, baud_rate: int = 115200, timeout: float = 2.0) -> bool:
    """
    Check if a serial port is connected to a GRBL device.
    
    Args:
        port: Serial port name (e.g., 'COM3', '/dev/ttyUSB0')
        baud_rate: Baud rate to use (default: 115200)
        timeout: Timeout in seconds for reading response
        
    Returns:
        True if GRBL device detected, False otherwise
    """
    try:
        ser = serial.Serial(port, baud_rate, timeout=timeout)
        time.sleep(0.1)  # Small delay for port to stabilize
        
        # Clear any existing data
        ser.reset_input_buffer()
        
        # Send wake-up command
        ser.write(b'\r\n')
        time.sleep(0.1)
        
        # Read response
        response = ser.read(100).decode('utf-8', errors='ignore')
        ser.close()
        
        # Check if response contains GRBL identifier
        if 'Grbl' in response or 'grbl' in response.lower():
            return True
        
    except (serial.SerialException, OSError, UnicodeDecodeError):
        pass
    
    return False


def find_grbl_device(
    baud_rate: int = 115200,
    timeout: float = 2.0,
    progress_callback: Optional[Callable[[str], None]] = None
) -> Optional[str]:
    """
    Automatically find and connect to a GRBL device.
    Prioritizes USB ports first, then other ports.
    
    Args:
        baud_rate: Baud rate to use (default: 115200)
        timeout: Timeout in seconds for each port test
        progress_callback: Optional callback function(port_name) called for each port tested
        
    Returns:
        Port name if GRBL device found, None otherwise
    """
    ports = list_serial_ports()
    
    # Separate USB and non-USB ports
    usb_ports = [p for p in ports if p[2]]  # p[2] is is_usb flag
    non_usb_ports = [p for p in ports if not p[2]]
    
    # Sort USB ports by name for consistent ordering
    usb_ports.sort(key=lambda x: x[0])
    # Sort non-USB ports by name
    non_usb_ports.sort(key=lambda x: x[0])
    
    # Combine: USB ports first, then non-USB ports
    prioritized_ports = usb_ports + non_usb_ports
    
    if progress_callback and usb_ports:
        progress_callback(f"Found {len(usb_ports)} USB port(s), checking USB ports first...")
    
    for port_name, description, is_usb in prioritized_ports:
        port_type = "USB" if is_usb else "non-USB"
        if progress_callback:
            progress_callback(f"Testing {port_type} port {port_name}...")
        
        if is_grbl_device(port_name, baud_rate, timeout):
            if progress_callback:
                progress_callback(f"Found GRBL on {port_name} ({port_type})")
            return port_name
    
    if progress_callback:
        progress_callback("No GRBL device found")
    return None


def get_port_display_name(port_name: str, description: str = "", is_usb: bool = False) -> str:
    """
    Get a user-friendly display name for a port.
    
    Args:
        port_name: Port name (e.g., 'COM3', '/dev/ttyUSB0')
        description: Port description (optional)
        is_usb: Whether port is USB (optional)
        
    Returns:
        Display name for the port
    """
    parts = [port_name]
    if is_usb:
        parts.append("USB")
    if description:
        parts.append(description)
    return " - ".join(parts)

