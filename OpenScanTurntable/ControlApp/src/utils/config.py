"""Configuration management for OpenScan Turntable Control App."""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional


class Config:
    """Manages application configuration."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to config file. If None, uses default location.
        """
        if config_path is None:
            # Get application root directory (parent of src directory)
            app_root = Path(__file__).parent.parent.parent
            config_path = app_root / "config" / "settings.json"
        
        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self.load()
    
    def load(self) -> None:
        """Load configuration from file."""
        # Create config directory if it doesn't exist
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load config if file exists, otherwise use defaults
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Failed to load config: {e}")
                self._config = self._get_default_config()
        else:
            self._config = self._get_default_config()
            self.save()
    
    def save(self) -> None:
        """Save configuration to file."""
        try:
            # Ensure directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Error: Failed to save config: {e}")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.
        
        Args:
            key_path: Dot-separated path to config value (e.g., 'serial.baud_rate')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        value = self._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key_path: str, value: Any) -> None:
        """
        Set configuration value using dot notation.
        
        Args:
            key_path: Dot-separated path to config value (e.g., 'serial.baud_rate')
            value: Value to set
        """
        keys = key_path.split('.')
        config = self._config
        
        # Navigate/create nested structure
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        # Set the final value
        config[keys[-1]] = value
    
    def get_all(self) -> Dict[str, Any]:
        """Get entire configuration dictionary."""
        return self._config.copy()
    
    @staticmethod
    def _get_default_config() -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "serial": {
                "auto_connect": True,
                "default_port": "COM3",
                "baud_rate": 115200,
                "timeout": 1.0,
                "auto_detect_timeout": 2.0,
                "auto_reconnect": False
            },
            "motors": {
                "x_axis": {
                    "step_angle": 1.8,
                    "microsteps": 0,
                    "max_angle": 360,
                    "min_angle": 0,
                    "speed": 800,
                    "acceleration": 50.0,
                    "gear_ratio": 1.0,
                    "always_on": False
                },
                "y_axis": {
                    "step_angle": 1.8,
                    "microsteps": 0,
                    "max_angle": 90,
                    "min_angle": -90,
                    "speed": 400,
                    "acceleration": 50.0,
                    "gear_ratio": 1.0,
                    "always_on": True
                }
            },
            "grbl": {
                "init_commands": [
                    "$X",
                    "G90",
                    "G21",
                    "G54"
                ],
                "status_poll_interval": 0.1
            },
            "home_position": {
                "x": 0,
                "y": 0
            }
        }

