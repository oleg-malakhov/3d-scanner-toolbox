#!/usr/bin/env python3
"""OpenScan Turntable Control Application - Main Entry Point."""

import sys
import tkinter as tk
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.config import Config
from src.ui.main_window import MainWindow


def main():
    """Main application entry point."""
    # Load configuration
    config = Config()
    
    # Create root window
    root = tk.Tk()
    
    # Create main window
    app = MainWindow(root, config)
    
    # Handle window closing
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    # Start main loop
    try:
        root.mainloop()
    except KeyboardInterrupt:
        app.on_closing()


if __name__ == "__main__":
    main()

