"""Main UI window for OpenScan Turntable Control App."""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from typing import Optional, Dict
import threading
import time

from src.grbl import GRBLController, MachineState
from src.turntable import Turntable
from src.utils.config import Config
from src.utils.serial_utils import list_serial_ports, get_port_display_name
from src.api.rest_server import RESTServer


class MainWindow:
    """Main application window."""
    
    def __init__(self, root: tk.Tk, config: Config):
        """
        Initialize main window.
        
        Args:
            root: Tkinter root window
            config: Configuration object
        """
        self.root = root
        self.config = config
        self.root.title("OpenScan Turntable Control")
        self.root.geometry("600x700")
        
        # Initialize status_text as None (will be created in _build_ui)
        self.status_text = None
        
        # Build UI first (creates status_text)
        self._build_ui()
        
        # Initialize controllers (after UI is built so message callbacks work)
        # GRBL controller logs only to console, not UI
        self.grbl_controller = GRBLController(config)
        # Register status callback
        self.grbl_controller.register_status_callback(self._on_status_update)
        
        # Turntable/Axis logs go to both console and UI
        # Position callback updates UI with latest position
        self.turntable = Turntable(
            self.grbl_controller, 
            config, 
            message_callback=self._add_status_message,
            position_callback=self._on_position_update
        )
        
        # Initialize REST server if enabled
        self.rest_server = None
        if config.get('rest_api.enabled', True):
            try:
                self.rest_server = RESTServer(
                    turntable=self.turntable,
                    grbl_controller=self.grbl_controller,
                    config=config
                )
                self.rest_server.start()
                self._add_status_message(f"REST API server started on port {self.rest_server.port}")
            except Exception as e:
                self._add_status_message(f"Failed to start REST API: {e}")
        
        # Auto-connect if enabled
        if config.get('serial.auto_connect', True):
            self.root.after(100, self._auto_connect)
    
    def _build_ui(self) -> None:
        """Build the user interface."""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Connection panel
        self._build_connection_panel(main_frame)
        
        # Separator
        ttk.Separator(main_frame, orient='horizontal').grid(
            row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10
        )
        
        # Axis control panels
        axis_frame = ttk.Frame(main_frame)
        axis_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        self._build_x_axis_panel(axis_frame)
        self._build_y_axis_panel(axis_frame)
        
        # Control buttons
        self._build_control_buttons(main_frame)
        
        # Status/messages panel
        self._build_status_panel(main_frame)
    
    def _build_connection_panel(self, parent: ttk.Frame) -> None:
        """Build connection control panel."""
        conn_frame = ttk.LabelFrame(parent, text="Connection", padding="10")
        conn_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Port selection
        ttk.Label(conn_frame, text="Port:").grid(row=0, column=0, padx=5, pady=5)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(conn_frame, textvariable=self.port_var, width=30, state='readonly')
        self.port_combo.grid(row=0, column=1, padx=5, pady=5)
        self._update_port_list()
        
        # Buttons
        button_frame = ttk.Frame(conn_frame)
        button_frame.grid(row=0, column=2, padx=10)
        
        self.connect_btn = ttk.Button(button_frame, text="Connect", command=self._manual_connect)
        self.connect_btn.grid(row=0, column=0, padx=2)
        
        self.auto_connect_btn = ttk.Button(button_frame, text="Auto-Connect", command=self._auto_connect)
        self.auto_connect_btn.grid(row=0, column=1, padx=2)
        
        self.disconnect_btn = ttk.Button(button_frame, text="Disconnect", command=self._disconnect, state='disabled')
        self.disconnect_btn.grid(row=0, column=2, padx=2)
        
        # Status indicator
        status_frame = ttk.Frame(conn_frame)
        status_frame.grid(row=1, column=0, columnspan=3, pady=5)
        
        self.status_indicator = tk.Canvas(status_frame, width=20, height=20)
        self.status_indicator.grid(row=0, column=0, padx=5)
        self._update_status_indicator(False)
        
        self.status_label = ttk.Label(status_frame, text="Disconnected")
        self.status_label.grid(row=0, column=1, padx=5)
        
        self.machine_state_label = ttk.Label(status_frame, text="")
        self.machine_state_label.grid(row=0, column=2, padx=5)
    
    def _build_x_axis_panel(self, parent: ttk.Frame) -> None:
        """Build X-axis (rotation) control panel."""
        x_frame = ttk.LabelFrame(parent, text="X-Axis (Rotation)", padding="10")
        x_frame.grid(row=0, column=0, padx=10, pady=5, sticky=(tk.W, tk.E, tk.N))
        
        # Current angle
        ttk.Label(x_frame, text="Current:").grid(row=0, column=0, padx=5, pady=5)
        self.x_current_label = ttk.Label(x_frame, text="0.0°", font=('Arial', 12, 'bold'))
        self.x_current_label.grid(row=0, column=1, padx=5, pady=5)
        
        # Target angle
        ttk.Label(x_frame, text="Target:").grid(row=1, column=0, padx=5, pady=5)
        self.x_target_var = tk.StringVar(value="0")
        x_target_entry = ttk.Entry(x_frame, textvariable=self.x_target_var, width=10)
        x_target_entry.grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(x_frame, text="°").grid(row=1, column=2, padx=2)
        
        # Rotate button
        self.rotate_btn = ttk.Button(x_frame, text="Rotate", command=self._rotate_x, state='disabled')
        self.rotate_btn.grid(row=2, column=0, columnspan=3, pady=10)
    
    def _build_y_axis_panel(self, parent: ttk.Frame) -> None:
        """Build Y-axis (tilt) control panel."""
        y_frame = ttk.LabelFrame(parent, text="Y-Axis (Tilt)", padding="10")
        y_frame.grid(row=0, column=1, padx=10, pady=5, sticky=(tk.W, tk.E, tk.N))
        
        # Current angle
        ttk.Label(y_frame, text="Current:").grid(row=0, column=0, padx=5, pady=5)
        self.y_current_label = ttk.Label(y_frame, text="0.0°", font=('Arial', 12, 'bold'))
        self.y_current_label.grid(row=0, column=1, padx=5, pady=5)
        
        # Target angle
        ttk.Label(y_frame, text="Target:").grid(row=1, column=0, padx=5, pady=5)
        self.y_target_var = tk.StringVar(value="0")
        y_target_entry = ttk.Entry(y_frame, textvariable=self.y_target_var, width=10)
        y_target_entry.grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(y_frame, text="°").grid(row=1, column=2, padx=2)
        
        # Tilt button
        self.tilt_btn = ttk.Button(y_frame, text="Tilt", command=self._tilt_y, state='disabled')
        self.tilt_btn.grid(row=2, column=0, columnspan=3, pady=10)
    
    def _build_control_buttons(self, parent: ttk.Frame) -> None:
        """Build control buttons panel."""
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        self.reset_btn = ttk.Button(button_frame, text="Reset to Home", command=self._reset_home, state='disabled')
        self.reset_btn.grid(row=0, column=0, padx=5)
        
        self.emergency_stop_btn = ttk.Button(button_frame, text="Emergency Stop", command=self._emergency_stop, state='disabled')
        self.emergency_stop_btn.grid(row=0, column=1, padx=5)
    
    def _build_status_panel(self, parent: ttk.Frame) -> None:
        """Build status/messages panel."""
        status_frame = ttk.LabelFrame(parent, text="Messages", padding="10")
        status_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        parent.rowconfigure(4, weight=1)
        
        self.status_text = scrolledtext.ScrolledText(status_frame, height=10, width=70, wrap=tk.WORD)
        self.status_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        status_frame.columnconfigure(0, weight=1)
        status_frame.rowconfigure(0, weight=1)
        
        self._add_status_message("Application started. Ready to connect.")
    
    def _update_port_list(self) -> None:
        """Update serial port list."""
        ports = list_serial_ports()
        # Sort to show USB ports first in dropdown
        ports_sorted = sorted(ports, key=lambda x: (not x[2], x[0]))  # USB first, then by name
        port_list = [get_port_display_name(port, desc, is_usb) for port, desc, is_usb in ports_sorted]
        self.port_combo['values'] = port_list
        if port_list:
            self.port_var.set(port_list[0])
    
    def _update_status_indicator(self, connected: bool) -> None:
        """Update connection status indicator."""
        self.status_indicator.delete("all")
        color = "green" if connected else "red"
        self.status_indicator.create_oval(5, 5, 15, 15, fill=color, outline="black")
    
    def _add_status_message(self, message: str) -> None:
        """Add message to status panel."""
        # Guard against calls before UI is fully initialized
        if self.status_text is None:
            # UI not ready yet, just print to console
            print(message)
            return
        
        # Use after() to ensure thread-safe UI updates
        self.root.after(0, lambda: self._do_add_status_message(message))
    
    def _do_add_status_message(self, message: str) -> None:
        """Actually add message to status panel (called on main thread)."""
        if self.status_text:
            self.status_text.insert(tk.END, f"{message}\n")
            self.status_text.see(tk.END)
    
    def _auto_connect(self) -> None:
        """Auto-connect to GRBL device."""
        self._add_status_message("Auto-detecting GRBL device...")
        self.connect_btn.config(state='disabled')
        self.auto_connect_btn.config(state='disabled')
        
        def connect_thread():
            success = self.grbl_controller.connect(auto_detect=True)
            self.root.after(0, lambda: self._on_connection_change(success))
        
        threading.Thread(target=connect_thread, daemon=True).start()
    
    def _manual_connect(self) -> None:
        """Manually connect to selected port."""
        port_display = self.port_var.get()
        if not port_display:
            messagebox.showerror("Error", "Please select a port")
            return
        
        # Extract port name (before " - ")
        port = port_display.split(" - ")[0]
        
        self._add_status_message(f"Connecting to {port}...")
        self.connect_btn.config(state='disabled')
        self.auto_connect_btn.config(state='disabled')
        
        def connect_thread():
            success = self.grbl_controller.connect(port=port, auto_detect=False)
            self.root.after(0, lambda: self._on_connection_change(success))
        
        threading.Thread(target=connect_thread, daemon=True).start()
    
    def _disconnect(self) -> None:
        """Disconnect from GRBL."""
        self.grbl_controller.disconnect()
        self._on_connection_change(False)
    
    def _on_connection_change(self, connected: bool) -> None:
        """Handle connection state change."""
        self._update_status_indicator(connected)
        
        if connected:
            self.status_label.config(text="Connected")
            self.connect_btn.config(state='disabled')
            self.auto_connect_btn.config(state='disabled')
            self.disconnect_btn.config(state='normal')
            self.rotate_btn.config(state='normal')
            self.tilt_btn.config(state='normal')
            self.reset_btn.config(state='normal')
            self.emergency_stop_btn.config(state='normal')
            # Start position polling when connected
            self.turntable.start_position_polling()
        else:
            self.status_label.config(text="Disconnected")
            self.connect_btn.config(state='normal')
            self.auto_connect_btn.config(state='normal')
            self.disconnect_btn.config(state='disabled')
            self.rotate_btn.config(state='disabled')
            self.tilt_btn.config(state='disabled')
            self.reset_btn.config(state='disabled')
            self.emergency_stop_btn.config(state='disabled')
            self.machine_state_label.config(text="")
            # Stop position polling when disconnected
            self.turntable.stop_position_polling()
    
    def _on_status_update(self, state: MachineState, position: Dict[str, float]) -> None:
        """Handle status update from GRBL."""
        self.root.after(0, lambda: self._update_ui_status(state, position))
    
    def _update_ui_status(self, state: MachineState, position: Dict[str, float]) -> None:
        """Update UI with status information."""
        # Update machine state
        self.machine_state_label.config(text=f"| {state.value}")
        
        # Position updates are now handled by _on_position_update from Turntable polling
    
    def _on_position_update(self, x_angle: float, y_angle: float) -> None:
        """Handle position update from Turntable polling (called from background thread)."""
        # Use after() to ensure thread-safe UI updates
        self.root.after(0, lambda: self._do_update_position_ui(x_angle, y_angle))
    
    def _do_update_position_ui(self, x_angle: float, y_angle: float) -> None:
        """Update position UI labels (called on main thread)."""
        self.x_current_label.config(text=f"{x_angle:.1f}°")
        self.y_current_label.config(text=f"{y_angle:.1f}°")
    
    def _rotate_x(self) -> None:
        """Rotate X-axis to target angle."""
        try:
            target_angle = float(self.x_target_var.get())
            success = self.turntable.rotate_to(Turntable.AXIS_X, target_angle)
            if success:
                self._add_status_message(f"Rotating to {target_angle}°")
            else:
                messagebox.showerror("Error", "Failed to rotate")
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid angle value: {e}")
    
    def _tilt_y(self) -> None:
        """Tilt Y-axis to target angle."""
        try:
            target_angle = float(self.y_target_var.get())
            success = self.turntable.rotate_to(Turntable.AXIS_Y, target_angle)
            if success:
                self._add_status_message(f"Tilting to {target_angle}°")
            else:
                messagebox.showerror("Error", "Failed to tilt")
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid angle value: {e}")
    
    def _reset_home(self) -> None:
        """Reset to home position."""
        self._add_status_message("Resetting to home position...")
        success = self.turntable.reset()
        if not success:
            messagebox.showerror("Error", "Failed to reset to home")
    
    def _emergency_stop(self) -> None:
        """Emergency stop."""
        self.grbl_controller.emergency_stop()
        self._add_status_message("EMERGENCY STOP activated")
    
    def on_closing(self) -> None:
        """Handle window closing."""
        # Stop position polling
        self.turntable.stop_position_polling()
        
        # Stop REST server
        if self.rest_server:
            self.rest_server.stop()
        
        # Disconnect GRBL
        if self.grbl_controller.connected:
            self.grbl_controller.disconnect()
        
        self.root.destroy()

