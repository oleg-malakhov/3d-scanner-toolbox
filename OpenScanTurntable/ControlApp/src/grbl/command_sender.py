"""Command sending with buffer tracking and retry logic."""

import threading
import time
import logging
from typing import Optional

import serial

from src.grbl.constants import RX_BUFFER_SIZE, AVG_COMMAND_SIZE, RESPONSE_TIMEOUT
from src.grbl.serial_connection import SerialConnection
from src.grbl.response_handler import ResponseWaiter


class CommandSender:
    """Handles command sending with buffer tracking."""
    
    def __init__(self, serial_connection: SerialConnection, retry_config: dict, response_handler=None):
        """
        Initialize command sender.
        
        Args:
            serial_connection: SerialConnection instance
            retry_config: Retry configuration dictionary
            response_handler: ResponseHandler instance (optional, can be set later)
        """
        self.serial_connection = serial_connection
        self.response_handler = response_handler
        self.logger = logging.getLogger(__name__)
        
        self.command_lock = threading.Lock()
        self.rx_buffer_used = 0
        
        self.retry_enabled = retry_config.get('enabled', True)
        self.max_retries = retry_config.get('max_retries', 3)
        self.retry_delay = retry_config.get('retry_delay', 0.1)
    
    def send_command(self, command: str, wait_for_response: bool = True, 
                     response_waiter: Optional[ResponseWaiter] = None) -> bool:
        """
        Send command with buffer tracking and retry logic.
        
        Args:
            command: G-code command string
            wait_for_response: If True, wait for response via waiter
            response_waiter: ResponseWaiter instance (required if wait_for_response=True)
        
        Returns:
            True if command sent successfully (and OK received if waiting), False otherwise
        """
        with self.command_lock:
            if not self.serial_connection.is_connected():
                self.logger.error("Serial port not available, cannot send command")
                return False
            
            # Add line ending if not present
            raw_command = command
            if not command.endswith('\r\n'):
                command = command.rstrip() + '\r\n'
            
            # Calculate command size for buffer tracking
            command_size = len(command.encode('utf-8'))
            
            # Check buffer space (with safety margin)
            if self.rx_buffer_used + command_size > RX_BUFFER_SIZE - 10:
                self.logger.warning("Buffer nearly full, waiting briefly...")
                time.sleep(0.05)
                # Re-check
                if self.rx_buffer_used + command_size > RX_BUFFER_SIZE - 10:
                    self.logger.warning("Buffer still nearly full")
            
            # Retry loop for write operations
            max_attempts = self.max_retries + 1 if self.retry_enabled else 1
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    if attempt > 1:
                        self.logger.debug(f"Retry attempt {attempt}/{max_attempts} for command: {raw_command.strip()}")
                        time.sleep(self.retry_delay)
                    
                    self.logger.debug(f"Sending command: {raw_command.strip()}")
                    bytes_written = self.serial_connection.write(command.encode('utf-8'))
                    self.rx_buffer_used += command_size
                    
                    # Wait for response if needed
                    if wait_for_response and response_waiter:
                        self.logger.debug("Waiting for OK response (timeout: 5s)...")
                        if response_waiter.wait(timeout=RESPONSE_TIMEOUT):
                            # Response received
                            result = response_waiter.get_result()
                            
                            # Decrease buffer usage (command processed)
                            self.rx_buffer_used = max(0, self.rx_buffer_used - AVG_COMMAND_SIZE)
                            
                            if result:
                                self.logger.debug("Command acknowledged")
                                return True
                            else:
                                self.logger.warning("Command error response")
                                return False
                        else:
                            # Timeout — drop the waiter so a late OK cannot match a later command.
                            self.logger.warning("Timeout waiting for response")
                            if self.response_handler:
                                self.response_handler.cancel_pending(response_waiter.sequence)
                            return False
                    
                    # Command sent without waiting for response
                    self.logger.debug("Command sent (not waiting for response)")
                    return True
                    
                except serial.SerialTimeoutException as e:
                    last_exception = e
                    self.logger.warning(f"Write timeout on attempt {attempt}/{max_attempts}: {e}")
                    if attempt < max_attempts:
                        continue
                    else:
                        return False
                        
                except serial.SerialException as e:
                    last_exception = e
                    self.logger.error(f"Serial error on attempt {attempt}/{max_attempts}: {e}")
                    if attempt < max_attempts and self.retry_enabled:
                        continue
                    else:
                        return False
                        
                except Exception as e:
                    last_exception = e
                    self.logger.error(f"Exception on attempt {attempt}/{max_attempts}: {e}", exc_info=True)
                    if attempt < max_attempts and self.retry_enabled:
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        return False
            
            if last_exception:
                self.logger.error(f"Final exception: {last_exception}")
            return False
    
    def decrease_buffer_usage(self, amount: int = AVG_COMMAND_SIZE) -> None:
        """
        Decrease buffer usage (called when response received).
        
        Args:
            amount: Amount to decrease (default: AVG_COMMAND_SIZE)
        """
        with self.command_lock:
            self.rx_buffer_used = max(0, self.rx_buffer_used - amount)
