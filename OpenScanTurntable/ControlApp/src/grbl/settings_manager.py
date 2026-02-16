"""GRBL settings management."""

import threading
import time
import logging
from typing import Dict, Optional

from src.grbl.constants import GRBL_MAX_RATE
from src.grbl.command_sender import CommandSender
from src.grbl.response_handler import ResponseHandler
from src.utils.config import Config


class SettingsManager:
    """Manages GRBL settings."""
    
    def __init__(self, command_sender: CommandSender, response_handler: ResponseHandler, config: Config):
        """
        Initialize settings manager.
        
        Args:
            command_sender: CommandSender instance
            response_handler: ResponseHandler instance
            config: Configuration object
        """
        self.command_sender = command_sender
        self.response_handler = response_handler
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        self.grbl_settings: Dict[str, float] = {}
        self.settings_received = threading.Event()
        
        self.grbl_x_steps_per_mm = 1.0
        self.grbl_y_steps_per_mm = 1.0
    
    def retrieve_settings(self) -> None:
        """Retrieve all GRBL settings."""
        self.logger.info("Retrieving GRBL Settings...")
        self.grbl_settings = {}
        self.settings_received.clear()
        
        try:
            self.command_sender.send_command("$$", wait_for_response=False)
        except Exception as e:
            self.logger.error(f"Error requesting settings: {e}")
            return
        
        if self.settings_received.wait(timeout=3.0):
            time.sleep(1.5)  # Wait for all settings to arrive
            self._check_and_update_settings()
        else:
            self.logger.warning("Timeout waiting for settings response")
            if self.grbl_settings:
                self._check_and_update_settings()
            else:
                self.logger.warning("No settings received. Check GRBL connection.")
    
    def parse_setting(self, line: str) -> None:
        """
        Parse a GRBL setting line.
        
        Args:
            line: Setting line from GRBL (e.g., "$100=1.0")
        """
        try:
            if '=' in line:
                parts = line.split('=')
                setting_code = parts[0].strip().replace('$', '')
                value_str = parts[1].split()[0] if parts[1].split() else parts[1].strip()
                value = float(value_str)
                
                setting_key = f"${setting_code}"
                self.grbl_settings[setting_key] = value
                
                # Update steps/mm if this is $100 or $101
                if setting_code == '100':
                    self.grbl_x_steps_per_mm = value
                elif setting_code == '101':
                    self.grbl_y_steps_per_mm = value
                
                # Signal that we've received at least one setting
                if not self.settings_received.is_set():
                    self.settings_received.set()
        except (ValueError, IndexError) as e:
            self.logger.debug(f"Error parsing setting line '{line}': {e}")
    
    def apply_settings_from_config(self) -> None:
        """Apply settings from configuration to GRBL after connect and init_commands."""
        print("[GRBL] Applying settings from configuration to GRBL...")
        
        # Get settings from config (use speed from config, fallback to GRBL_MAX_RATE if not set)
        config_x_max_rate = self.config.get('motors.x_axis.speed', GRBL_MAX_RATE)
        config_y_max_rate = self.config.get('motors.y_axis.speed', GRBL_MAX_RATE)
        config_x_accel = self.config.get('motors.x_axis.acceleration', None)
        config_y_accel = self.config.get('motors.y_axis.acceleration', None)
        
        settings_applied = False
        
        # Apply X-axis max rate
        if config_x_max_rate is not None:
            print(f"[GRBL] Applying $110={config_x_max_rate:.1f} (X-axis max rate)")
            waiter = self.response_handler.create_response_waiter()
            if self.command_sender.send_command(f"$110={config_x_max_rate:.1f}", True, waiter):
                self.grbl_settings['$110'] = config_x_max_rate
                settings_applied = True
            time.sleep(0.2)
        
        # Apply Y-axis max rate
        if config_y_max_rate is not None:
            print(f"[GRBL] Applying $111={config_y_max_rate:.1f} (Y-axis max rate)")
            waiter = self.response_handler.create_response_waiter()
            if self.command_sender.send_command(f"$111={config_y_max_rate:.1f}", True, waiter):
                self.grbl_settings['$111'] = config_y_max_rate
                settings_applied = True
            time.sleep(0.2)
        
        # Apply X-axis acceleration
        if config_x_accel is not None:
            print(f"[GRBL] Applying $120={config_x_accel:.1f} (X-axis acceleration)")
            waiter = self.response_handler.create_response_waiter()
            if self.command_sender.send_command(f"$120={config_x_accel:.1f}", True, waiter):
                self.grbl_settings['$120'] = config_x_accel
                settings_applied = True
            time.sleep(0.2)
        
        # Apply Y-axis acceleration
        if config_y_accel is not None:
            print(f"[GRBL] Applying $121={config_y_accel:.1f} (Y-axis acceleration)")
            waiter = self.response_handler.create_response_waiter()
            if self.command_sender.send_command(f"$121={config_y_accel:.1f}", True, waiter):
                self.grbl_settings['$121'] = config_y_accel
                settings_applied = True
            time.sleep(0.2)
        
        if settings_applied:
            print("[GRBL] Settings from configuration applied successfully")
        else:
            self.logger.warning("No settings were applied from configuration")
    
    def _check_and_update_settings(self) -> None:
        """Check if GRBL settings match configuration and update if needed."""
        self.logger.info("Checking GRBL Settings Against Configuration...")
        
        # Get settings from config (use speed from config, fallback to GRBL_MAX_RATE if not set)
        config_x_max_rate = self.config.get('motors.x_axis.speed', GRBL_MAX_RATE)
        config_y_max_rate = self.config.get('motors.y_axis.speed', GRBL_MAX_RATE)
        config_x_accel = self.config.get('motors.x_axis.acceleration', None)
        config_y_accel = self.config.get('motors.y_axis.acceleration', None)
        
        grbl_x_max_rate = self.grbl_settings.get('$110', None)
        grbl_y_max_rate = self.grbl_settings.get('$111', None)
        grbl_x_accel = self.grbl_settings.get('$120', None)
        grbl_y_accel = self.grbl_settings.get('$121', None)
        
        settings_updated = False
        
        # Check and update X-axis max rate
        if grbl_x_max_rate is not None:
            if abs(grbl_x_max_rate - config_x_max_rate) > 0.1:
                self.logger.info(f"Updating $110 from {grbl_x_max_rate:.1f} to {config_x_max_rate:.1f}")
                waiter = self.response_handler.create_response_waiter()
                if self.command_sender.send_command(f"$110={config_x_max_rate:.1f}", True, waiter):
                    self.grbl_settings['$110'] = config_x_max_rate
                    settings_updated = True
        
        # Check and update Y-axis max rate
        if grbl_y_max_rate is not None:
            if abs(grbl_y_max_rate - config_y_max_rate) > 0.1:
                self.logger.info(f"Updating $111 from {grbl_y_max_rate:.1f} to {config_y_max_rate:.1f}")
                waiter = self.response_handler.create_response_waiter()
                if self.command_sender.send_command(f"$111={config_y_max_rate:.1f}", True, waiter):
                    self.grbl_settings['$111'] = config_y_max_rate
                    settings_updated = True
        
        # Check and update accelerations
        if config_x_accel is not None and grbl_x_accel is not None:
            if abs(grbl_x_accel - config_x_accel) > 0.1:
                self.logger.info(f"Updating $120 from {grbl_x_accel:.1f} to {config_x_accel:.1f}")
                waiter = self.response_handler.create_response_waiter()
                if self.command_sender.send_command(f"$120={config_x_accel:.1f}", True, waiter):
                    self.grbl_settings['$120'] = config_x_accel
                    settings_updated = True
        
        if config_y_accel is not None and grbl_y_accel is not None:
            if abs(grbl_y_accel - config_y_accel) > 0.1:
                self.logger.info(f"Updating $121 from {grbl_y_accel:.1f} to {config_y_accel:.1f}")
                waiter = self.response_handler.create_response_waiter()
                if self.command_sender.send_command(f"$121={config_y_accel:.1f}", True, waiter):
                    self.grbl_settings['$121'] = config_y_accel
                    settings_updated = True
        
        if settings_updated:
            self.logger.info("GRBL settings updated successfully")
        else:
            self.logger.info("All GRBL settings match configuration")
