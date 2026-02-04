"""Serial port connection management for GRBL."""

import serial
import time
import logging
from typing import Optional

from src.utils.config import Config
from src.utils.serial_utils import find_grbl_device


class SerialConnection:
    """Manages serial port connection to GRBL device."""
    
    def __init__(self, config: Config):
        """
        Initialize serial connection manager.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.serial: Optional[serial.Serial] = None
        
        self.baud_rate = config.get('serial.baud_rate', 115200)
        self.timeout = config.get('serial.timeout', 1.0)
    
    def connect(self, port: Optional[str] = None, auto_detect: bool = True) -> bool:
        """
        Connect to GRBL device.
        
        Args:
            port: Serial port name. If None and auto_detect is True, will auto-detect.
            auto_detect: If True, automatically find GRBL device.
            
        Returns:
            True if connected successfully, False otherwise
        """
        if self.is_connected():
            self.disconnect()
        
        if auto_detect and port is None:
            progress_callback = lambda msg: self.logger.info(f"Auto-detecting: {msg}")
            port = find_grbl_device(
                baud_rate=self.baud_rate,
                timeout=self.config.get('serial.auto_detect_timeout', 2.0),
                progress_callback=progress_callback
            )
        
        if port is None:
            self.logger.error("No GRBL device found")
            return False
        
        try:
            self.serial = serial.Serial(
                port,
                self.baud_rate,
                timeout=self.timeout,
                write_timeout=self.timeout
            )
            time.sleep(0.1)  # Small delay for port to stabilize
            
            # Clear buffers
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            
            # Send wake-up command
            self.serial.write(b'\r\n')
            time.sleep(0.2)
            
            # Read welcome message
            response = self.serial.read(100).decode('utf-8', errors='ignore')
            if 'Grbl' not in response and 'grbl' not in response.lower():
                self.serial.close()
                self.serial = None
                self.logger.error(f"Device on {port} is not GRBL")
                return False
            
            self.logger.info(f"Connected to {port}")
            return True
            
        except (serial.SerialException, OSError) as e:
            self.logger.error(f"Connection error: {e}")
            if self.serial:
                try:
                    self.serial.close()
                except Exception as close_error:
                    self.logger.error(f"Error closing serial port: {close_error}")
                self.serial = None
            return False
    
    def disconnect(self) -> None:
        """Disconnect from GRBL device."""
        if self.serial and self.serial.is_open:
            try:
                self.serial.close()
            except Exception as e:
                self.logger.error(f"Error closing serial port: {e}")
            self.serial = None
        self.logger.info("Disconnected")
    
    def is_connected(self) -> bool:
        """
        Check if connected.
        
        Returns:
            True if connected and port is open, False otherwise
        """
        return self.serial is not None and self.serial.is_open
    
    def write(self, data: bytes) -> int:
        """
        Write data to serial port.
        
        Args:
            data: Bytes to write
            
        Returns:
            Number of bytes written
            
        Raises:
            serial.SerialException: If not connected or write fails
        """
        if not self.is_connected():
            raise serial.SerialException("Not connected")
        return self.serial.write(data)
    
    def readline(self) -> Optional[str]:
        """
        Read a line from serial port.
        
        Returns:
            Decoded line string, or None if no data available
        """
        if not self.is_connected():
            return None
        if self.serial.in_waiting > 0:
            return self.serial.readline().decode('utf-8', errors='ignore').strip()
        return None
    
    def reset_buffers(self) -> None:
        """Reset input and output buffers."""
        if self.is_connected():
            try:
                self.serial.reset_input_buffer()
                self.serial.reset_output_buffer()
            except Exception as e:
                self.logger.error(f"Error resetting buffers: {e}")
