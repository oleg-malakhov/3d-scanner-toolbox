import asyncio
import tkinter as tk
from tkinter import ttk
import threading
import queue
from flask import Flask, request, jsonify
from bleak import BleakClient, BleakScanner
import logging
import os
import time
import platform

# --- Windows specific feature flag ---
POPUP_HANDLER_ENABLED = False
if platform.system() == "Windows":
    try:
        import ctypes
        import ctypes.wintypes
        from pywinauto import Application, Desktop
        POPUP_HANDLER_ENABLED = True
    except ImportError:
        logging.warning("Windows-specific dependency 'pywinauto' not found. Popup handler is disabled.")
        logging.warning("You can install it using: pip install pywinauto")

# --- Windows specific popup handler ---
if POPUP_HANDLER_ENABLED:
    psapi = ctypes.WinDLL('Psapi.dll')
    kernel32 = ctypes.WinDLL('kernel32.dll')

    def get_process_name(pid):
        """Get process name from process ID."""
        h_process = kernel32.OpenProcess(
            ctypes.wintypes.DWORD(0x0400 | 0x0010),  # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
            False,
            pid
        )
        if not h_process:
            return None
        
        try:
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            if psapi.GetModuleBaseNameW(h_process, None, buf, ctypes.sizeof(buf)) > 0:
                return buf.value
            else:
                return None
        finally:
            kernel32.CloseHandle(h_process)

    def find_text_in_descendants(control, text_snippet):
        """Recursively search for a static text control with specific text."""
        try:
            if "Static" in control.class_name() and text_snippet in control.window_text():
                return True
        except Exception:
            pass

        for child in control.children():
            if find_text_in_descendants(child, text_snippet):
                return True
                
        return False

    def find_and_close_popup_recursive(control, popup_class, inner_text_snippet):
        """Recursively searches for a popup within a control tree and closes it."""
        try:
            if control.is_visible() and control.class_name() == popup_class:
                if find_text_in_descendants(control, inner_text_snippet):
                    for child in control.children():
                        if "Button" in child.class_name() and child.window_text() == "OK":
                            child.click()
                            return True
            for child in control.children():
                if find_and_close_popup_recursive(child, popup_class, inner_text_snippet):
                    return True
        except Exception:
            pass
        return False

    def handle_popup(app_name, popup_class, inner_text_snippet):
        """Finds a dialog by its process name, verifies its content, and clicks 'OK'."""
        try:
            desktop = Desktop(backend='uia')
            top_windows = desktop.windows()

            for window in top_windows:
                if not window.is_visible():
                    continue
                try:
                    pid = window.process_id()
                    process_name = get_process_name(pid)
                    if process_name and app_name in process_name:
                        if find_and_close_popup_recursive(window, popup_class, inner_text_snippet):
                            return True
                except Exception:
                    continue
        except Exception as e:
            if not ("Process not found" in str(e) or "TimeoutError" in str(e) or "ElementNotFoundError" in str(e)):
                logging.warning(f"Popup handler error: {e}")
        return False

    def popup_watcher_thread():
        """The main loop for watching and closing the popup."""
        APP_NAME = "FlexScan3D"
        POPUP_CLASS = "#32770"
        TARGET_TEXT = "Failed to detect a valid checkerboard pattern."
        
        logging.info("Popup watcher for FlexScan3D started in background (Windows only).")
        while True:
            try:
                if handle_popup(APP_NAME, POPUP_CLASS, TARGET_TEXT):
                    logging.info("FlexScan3D checkerboard popup found and closed.")
                time.sleep(2)
            except Exception as e:
                logging.error(f"Error in popup watcher thread: {e}")
                time.sleep(5)


# --- Constants from turntable_api.py ---
UART_SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb"
UART_CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"
FASTEST_ROTATION_SPEED = 35.64
FASTEST_TILT_SPEED = 9
MAX_RETRY_ATTEMPTS = 5
API_PORT = 5001


class TurntableController:
    """
    Manages the connection and communication with the Revopoint Turntable.
    This class is designed to be run in a separate thread.
    """

    def __init__(self, gui_queue):
        self.gui_queue = gui_queue
        self.client = None
        self.device_address = None
        self.current_tilt_angle = 0
        self.current_rotation_angle = 0
        self.is_connected = False
        self.response_future = None
        self.cmd_lock = asyncio.Lock()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def run(self):
        """The main entry point for the controller thread."""
        self.loop.run_until_complete(self.manage_connection())

    async def manage_connection(self):
        """Maintains a persistent connection to the turntable."""
        while True:
            if not self.is_connected:
                await self.connect()
            else:
                await self.update_status()
                await asyncio.sleep(1)  # Poll every second

            # Small delay to prevent a tight loop on repeated failures
            if not self.is_connected:
                await asyncio.sleep(5)

    async def connect(self):
        """Scans for and connects to the turntable."""
        self.put_on_gui_queue("status", "Scanning...")
        config_file = "turntable_address.txt"
        device_address = None

        # 1. Try reading from the config file
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                device_address = f.read().strip()
                if device_address:
                    self.put_on_gui_queue("status", f"Found saved address: {device_address}")

        # 2. If no address, scan by name
        if not device_address:
            device = await BleakScanner.find_device_by_name("REVO_DUAL_AXIS_TABLE", timeout=10.0)
            if device:
                device_address = device.address
                self.put_on_gui_queue("status", f"Found device: {device_address}")
                with open(config_file, "w") as f:
                    f.write(device_address)
            else:
                self.put_on_gui_queue("status", "Turntable not found. Retrying in 10s.")
                await asyncio.sleep(10)
                return

        self.device_address = device_address
        self.put_on_gui_queue("address", self.device_address)

        try:
            self.client = BleakClient(self.device_address, disconnected_callback=self.on_disconnect)
            await self.client.connect()
            self.is_connected = self.client.is_connected
            if self.is_connected:
                self.put_on_gui_queue("status", "Connected")
                await self.setup_turntable()
        except Exception as e:
            self.put_on_gui_queue("status", f"Connection failed: {e}")
            self.is_connected = False

    def on_disconnect(self, client):
        """Callback for when the device gets disconnected."""
        self.is_connected = False
        self.put_on_gui_queue("status", "Disconnected. Reconnecting...")
        self.put_on_gui_queue("angle", "N/A")
        self.put_on_gui_queue("tilt", "N/A")

    async def setup_turntable(self):
        """Initial setup after connecting."""
        await self.client.start_notify(UART_CHAR_UUID, self.notification_handler)
        await self.send_command(f"+CT,TURNSPEED={FASTEST_ROTATION_SPEED};")
        await self.send_command(f"+CR,TILTSPEED={FASTEST_TILT_SPEED};")

    async def update_status(self):
        """Periodically fetches and updates the turntable's status."""
        if not self.is_connected:
            return

        try:
            # Get absolute angle
            angle_response = await self.send_command("+QT,CHANGEANGLE;")
            if angle_response and angle_response.startswith('+DATA='):
                angle_str = angle_response.strip('+DATA=').strip(';')
                self.current_rotation_angle = int(float(angle_str))
                self.put_on_gui_queue("angle", self.current_rotation_angle)

            # Tilt is not directly readable, we rely on our internal state
            self.put_on_gui_queue("tilt", self.current_tilt_angle)

        except Exception as e:
            logging.error(f"Error updating status: {e}")
            # The disconnected_callback will handle the state change
            pass

    def put_on_gui_queue(self, msg_type, data):
        """Helper to put data onto the queue for the GUI."""
        self.gui_queue.put({"type": msg_type, "data": data})

    def notification_handler(self, sender, data):
        """Handles incoming BLE notifications."""
        if self.response_future and not self.response_future.done():
            self.response_future.set_result(data)

    async def send_command(self, cmd: str) -> str:
        """Sends a command to the turntable and waits for a notification response."""
        async with self.cmd_lock:
            if not self.is_connected:
                return ""
            try:
                self.response_future = self.loop.create_future()
                await self.client.write_gatt_char(UART_CHAR_UUID, cmd.encode('utf-8'))
                
                # Wait for the notification to arrive, with a timeout
                response_bytes = await asyncio.wait_for(self.response_future, timeout=10.0)
                
                return response_bytes.decode('utf-8', errors='ignore').strip()
            except asyncio.TimeoutError:
                logging.warning(f"Timeout waiting for response for '{cmd}'")
                return ""
            except Exception as e:
                logging.warning(f"Error in send_command for '{cmd}': {e}")
                return ""

    # --- Public methods to be called from other threads ---
    def set_position(self, tilt: int, angle: int):
        """Sets the turntable to a specific tilt and angle."""
        if not self.is_connected:
            raise ConnectionError("Turntable is not connected.")
        
        future = asyncio.run_coroutine_threadsafe(self._async_set_position(tilt, angle), self.loop)
        return future.result()

    async def _async_set_position(self, tilt: int, angle: int):
        try:
            # Tilt first
            target_tilt = max(-30, min(30, tilt))
            if target_tilt != self.current_tilt_angle:
                await self.send_command(f"+CR,TILTVALUE={target_tilt};")
                # Simple wait for tilt, as there's no feedback from the device
                wait_time_tilt = (abs(target_tilt - self.current_tilt_angle) / FASTEST_TILT_SPEED) + 0.5
                await asyncio.sleep(wait_time_tilt)
                self.current_tilt_angle = target_tilt

            # Then rotate
            target_angle = angle % 360
            if target_angle != self.current_rotation_angle:
                initial_angle = self.current_rotation_angle
                diff = target_angle - initial_angle
                if diff > 180: move_angle = diff - 360
                elif diff < -180: move_angle = diff + 360
                else: move_angle = diff
                
                await self.send_command(f"+CT,TURNANGLE={move_angle};")

                # Add a small delay to allow the turntable to start moving
                await asyncio.sleep(0.5)

                # Poll for rotation completion
                while True:
                    await self.update_status() # This updates self.current_rotation_angle
                    diff = abs(self.current_rotation_angle - target_angle)
                    if min(diff, 360 - diff) < 2:  # tolerance of 2 degrees
                        break
                    await asyncio.sleep(0.2)

            return True
        except Exception as e:
            logging.error(f"Failed to set position: {e}")
            return False

    def reset_position(self):
        """Resets the turntable to its zero position."""
        if not self.is_connected:
            raise ConnectionError("Turntable is not connected.")
        
        future = asyncio.run_coroutine_threadsafe(self._async_reset(), self.loop)
        return future.result()

    async def _async_reset(self):
        try:
            self.current_tilt_angle = 0
            await self.send_command("+CR,TOZERO;")
            await self.send_command("+CT,TOZERO;")
            
            # Poll for reset completion
            while True:
                await self.update_status()
                if self.current_rotation_angle < 2 or self.current_rotation_angle > 358:
                    break
                await asyncio.sleep(0.2)

            return True
        except Exception as e:
            logging.error(f"Failed to reset: {e}")
            return False


class TurntableApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Turntable Control")
        self.gui_queue = queue.Queue()

        # --- Turntable Controller ---
        self.turntable_controller = TurntableController(self.gui_queue)
        self.controller_thread = threading.Thread(target=self.turntable_controller.run, daemon=True)
        self.controller_thread.start()

        # --- Flask API ---
        self.api_thread = threading.Thread(target=self.run_api, daemon=True)
        self.api_thread.start()

        # --- Windows Popup Watcher ---
        if POPUP_HANDLER_ENABLED:
            self.popup_thread = threading.Thread(target=popup_watcher_thread, daemon=True)
            self.popup_thread.start()

        # --- GUI Setup ---
        self.create_widgets()
        self.process_gui_queue()

    def create_widgets(self):
        frame = ttk.Frame(self.root, padding="10")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Labels and Values
        self.address_var = tk.StringVar(value="N/A")
        self.angle_var = tk.StringVar(value="N/A")
        self.tilt_var = tk.StringVar(value="N/A")
        self.status_var = tk.StringVar(value="Initializing...")

        ttk.Label(frame, text="Address:").grid(column=0, row=0, sticky=tk.W)
        ttk.Label(frame, textvariable=self.address_var).grid(column=1, row=0, sticky=tk.W)

        ttk.Label(frame, text="Angle:").grid(column=0, row=1, sticky=tk.W)
        ttk.Label(frame, textvariable=self.angle_var).grid(column=1, row=1, sticky=tk.W)

        ttk.Label(frame, text="Tilt:").grid(column=0, row=2, sticky=tk.W)
        ttk.Label(frame, textvariable=self.tilt_var).grid(column=1, row=2, sticky=tk.W)
        
        ttk.Label(frame, text="Status:").grid(column=0, row=3, sticky=tk.W)
        ttk.Label(frame, textvariable=self.status_var).grid(column=1, row=3, sticky=tk.W)

        # Reset Button
        reset_button = ttk.Button(frame, text="Reset", command=self.handle_reset)
        reset_button.grid(column=0, row=4, columnspan=2, pady=10)

    def process_gui_queue(self):
        """Processes messages from the controller thread to update the GUI."""
        try:
            while True:
                message = self.gui_queue.get_nowait()
                msg_type = message.get("type")
                data = message.get("data")

                if msg_type == "address":
                    self.address_var.set(data)
                elif msg_type == "angle":
                    self.angle_var.set(str(data))
                elif msg_type == "tilt":
                    self.tilt_var.set(str(data))
                elif msg_type == "status":
                    self.status_var.set(data)

        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_gui_queue)

    def handle_reset(self):
        """Handles the click of the Reset button."""
        self.status_var.set("Resetting...")
        try:
            # Run the reset in a separate thread to not block the GUI
            threading.Thread(target=self.turntable_controller.reset_position, daemon=True).start()
        except Exception as e:
            self.status_var.set(f"Reset failed: {e}")

    def run_api(self):
        """Runs the Flask web server."""
        app = Flask(__name__)

        @app.route('/position', methods=['PUT'])
        def set_position_endpoint():
            if not request.is_json:
                return jsonify({"error": "Request must be JSON"}), 400
            
            data = request.get_json()
            # Use current values as default if not provided
            tilt = data.get('tilt', self.turntable_controller.current_tilt_angle)
            angle = data.get('angle', self.turntable_controller.current_rotation_angle)

            try:
                success = self.turntable_controller.set_position(int(tilt), int(angle))
                if success:
                    return jsonify({"status": "success"}), 200
                else:
                    return jsonify({"error": "Failed to set position"}), 500
            except ConnectionError as e:
                return jsonify({"error": str(e)}), 503 # Service Unavailable
            except Exception as e:
                logging.error(f"API Error: {e}")
                return jsonify({"error": "An internal error occurred"}), 500

        @app.route('/reset', methods=['POST'])
        def reset_position_endpoint():
            try:
                success = self.turntable_controller.reset_position()
                if success:
                    return jsonify({"status": "success"}), 200
                else:
                    return jsonify({"error": "Failed to reset position"}), 500
            except ConnectionError as e:
                return jsonify({"error": str(e)}), 503
            except Exception as e:
                logging.error(f"API Error: {e}")
                return jsonify({"error": "An internal error occurred"}), 500

        @app.route('/status', methods=['GET'])
        def get_status_endpoint():
            if not self.turntable_controller.is_connected:
                return jsonify({"error": "Turntable is not connected"}), 503

            status = {
                "angle": self.turntable_controller.current_rotation_angle,
                "tilt": self.turntable_controller.current_tilt_angle,
                "connected": self.turntable_controller.is_connected
            }
            return jsonify(status), 200

        # You can change the host and port here
        app.run(host='0.0.0.0', port=API_PORT)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    root = tk.Tk()
    app = TurntableApp(root)
    root.mainloop()
