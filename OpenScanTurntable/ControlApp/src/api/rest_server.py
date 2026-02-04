"""REST API server for OpenScan Turntable Control."""

from flask import Flask, request, jsonify
import threading
import time
from typing import Optional

from src.turntable import Turntable
from src.grbl import GRBLController, MachineState
from src.utils.config import Config


class RESTServer:
    """Flask-based REST API server for turntable control."""
    
    def __init__(self, turntable: Turntable, 
                 grbl_controller: GRBLController,
                 config: Config):
        """
        Initialize REST API server.
        
        Args:
            turntable: Turntable instance for movement control
            grbl_controller: GRBL controller for status checking
            config: Configuration object
        """
        self.turntable = turntable
        self.grbl_controller = grbl_controller
        self.config = config
        
        # Get configuration
        self.enabled = config.get('rest_api.enabled', True)
        self.host = config.get('rest_api.host', '127.0.0.1')
        self.port = config.get('rest_api.port', 5001)
        self.debug = config.get('rest_api.debug', False)
        self.movement_timeout = config.get('rest_api.movement_timeout', 60.0)
        
        print(f"[REST API] Initializing REST API server")
        print(f"[REST API] Configuration: enabled={self.enabled}, host={self.host}, port={self.port}, timeout={self.movement_timeout}s")
        
        # Initialize Flask app
        self.app = Flask(__name__)
        self._setup_routes()
        self._setup_error_handlers()
        
        # Thread management
        self.server_thread: Optional[threading.Thread] = None
        self._running = False
        
        print(f"[REST API] REST API server initialized")
    
    def _setup_routes(self) -> None:
        """Configure API routes."""
        
        @self.app.route('/position', methods=['PUT'])
        def set_position():
            """Set turntable position (synchronous - waits for completion)."""
            start_time = time.time()
            client_ip = request.remote_addr
            
            print(f"[REST API] PUT /position - Request from {client_ip}")
            
            if not self.grbl_controller.connected:
                print(f"[REST API] PUT /position - Error: Turntable not connected")
                return jsonify({"error": "Turntable not connected"}), 503
            
            try:
                data = request.get_json()
                print(f"[REST API] PUT /position - Request data: {data}")
                
                if data is None:
                    print(f"[REST API] PUT /position - Error: Invalid JSON")
                    return jsonify({"error": "Invalid JSON"}), 400
                
                x_angle = data.get('angle')
                y_angle = data.get('tilt')
                
                # Validate at least one angle provided
                if x_angle is None and y_angle is None:
                    print(f"[REST API] PUT /position - Error: No angles provided")
                    return jsonify({"error": "At least one angle must be provided"}), 400
                
                # Validate ranges - allow negative angles for shortest path calculation
                if x_angle is not None:
                    if not isinstance(x_angle, (int, float)):
                        print(f"[REST API] PUT /position - Error: Invalid angle type: {type(x_angle)}")
                        return jsonify({"error": "Angle must be a number"}), 400
                    # Don't normalize here - let turntable's shortest path logic handle it
                    # Pass as float to preserve precision, turntable will handle shortest path
                    x_angle = float(x_angle)
                    print(f"[REST API] PUT /position - Angle: {x_angle}° (will use shortest path)")
                
                if y_angle is not None:
                    if not isinstance(y_angle, (int, float)):
                        print(f"[REST API] PUT /position - Error: Invalid tilt type: {type(y_angle)}")
                        return jsonify({"error": "Tilt must be a number"}), 400
                    y_angle = float(y_angle)  # Keep as float, let turntable validate against hardware limits
                
                print(f"[REST API] PUT /position - Validated: angle={x_angle}, tilt={y_angle}")
                
                # Get current position before movement
                current_x, current_y = self.turntable.current()
                print(f"[REST API] PUT /position - Current position: angle={current_x:.1f}°, tilt={current_y:.1f}°")
                
                # Execute movement
                print(f"[REST API] PUT /position - Executing movement command...")
                if x_angle is not None and y_angle is not None:
                    print(f"[REST API] PUT /position - Moving both axes: angle={x_angle}°, tilt={y_angle}°")
                    success = self.turntable.move_to_angles(x_angle, y_angle)
                elif x_angle is not None:
                    print(f"[REST API] PUT /position - Rotating X-axis to {x_angle}°")
                    success = self.turntable.rotate_to(Turntable.AXIS_X, x_angle)
                else:  # y_angle is not None
                    print(f"[REST API] PUT /position - Tilting Y-axis to {y_angle}°")
                    success = self.turntable.rotate_to(Turntable.AXIS_Y, y_angle)
                
                if not success:
                    print(f"[REST API] PUT /position - Error: Movement command failed")
                    # Resync position from GRBL after command failure
                    print(f"[REST API] PUT /position - Resyncing position from GRBL...")
                    self._resync_position()
                    return jsonify({"error": "Movement command failed"}), 500
                
                print(f"[REST API] PUT /position - Movement command sent, waiting for completion (timeout: {self.movement_timeout}s)...")
                
                # Wait for movement to complete (synchronous)
                movement_complete = self.grbl_controller.wait_for_idle(timeout=self.movement_timeout)
                
                elapsed_time = time.time() - start_time
                
                # Check for errors during movement
                if not self.grbl_controller.connected:
                    print(f"[REST API] PUT /position - Error: Connection lost during movement after {elapsed_time:.2f}s")
                    # Resync position before returning error
                    self._resync_position()
                    return jsonify({"error": "Connection lost during movement"}), 503
                
                if self.grbl_controller.machine_state == MachineState.ALARM:
                    print(f"[REST API] PUT /position - Error: Machine in alarm state after {elapsed_time:.2f}s")
                    # Resync position after alarm
                    self._resync_position()
                    return jsonify({"error": "Machine in alarm state"}), 500
                
                if movement_complete:
                    # Get final position
                    final_x, final_y = self.turntable.current()
                    print(f"[REST API] PUT /position - Movement completed in {elapsed_time:.2f}s")
                    print(f"[REST API] PUT /position - Final position: angle={final_x:.1f}°, tilt={final_y:.1f}°")
                    print(f"[REST API] PUT /position - Response: 200 OK")
                    return jsonify({"status": "success"}), 200
                else:
                    # Movement didn't complete - could be timeout or other error
                    current_state = self.grbl_controller.machine_state
                    print(f"[REST API] PUT /position - Error: Movement failed after {elapsed_time:.2f}s (state: {current_state.value})")
                    # Resync position after timeout/error
                    self._resync_position()
                    if current_state == MachineState.ALARM:
                        return jsonify({"error": "Machine in alarm state"}), 500
                    else:
                        return jsonify({"error": "Movement timeout"}), 504
                    
            except Exception as e:
                elapsed_time = time.time() - start_time
                print(f"[REST API] PUT /position - Exception after {elapsed_time:.2f}s: {e}")
                import traceback
                print(f"[REST API] PUT /position - Traceback: {traceback.format_exc()}")
                # Resync position after exception
                self._resync_position()
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/reset', methods=['POST'])
        def reset_position():
            """Reset turntable to home position (synchronous - waits for completion)."""
            start_time = time.time()
            client_ip = request.remote_addr
            
            print(f"[REST API] POST /reset - Request from {client_ip}")
            
            if not self.grbl_controller.connected:
                print(f"[REST API] POST /reset - Error: Turntable not connected")
                return jsonify({"error": "Turntable not connected"}), 503
            
            try:
                # Get current position before reset
                current_x, current_y = self.turntable.current()
                print(f"[REST API] POST /reset - Current position: angle={current_x:.1f}°, tilt={current_y:.1f}°")
                
                print(f"[REST API] POST /reset - Executing reset command...")
                success = self.turntable.reset()
                
                if not success:
                    print(f"[REST API] POST /reset - Error: Reset command failed")
                    # Resync position from GRBL after command failure
                    print(f"[REST API] POST /reset - Resyncing position from GRBL...")
                    self._resync_position()
                    return jsonify({"error": "Reset command failed"}), 500
                
                print(f"[REST API] POST /reset - Reset command sent, waiting for completion (timeout: {self.movement_timeout}s)...")
                
                # Wait for reset movement to complete (synchronous)
                movement_complete = self.grbl_controller.wait_for_idle(timeout=self.movement_timeout)
                
                elapsed_time = time.time() - start_time
                
                # Check for errors during movement
                if not self.grbl_controller.connected:
                    print(f"[REST API] POST /reset - Error: Connection lost during reset after {elapsed_time:.2f}s")
                    # Resync position before returning error
                    self._resync_position()
                    return jsonify({"error": "Connection lost during reset"}), 503
                
                if self.grbl_controller.machine_state == MachineState.ALARM:
                    print(f"[REST API] POST /reset - Error: Machine in alarm state after {elapsed_time:.2f}s")
                    # Resync position after alarm
                    self._resync_position()
                    return jsonify({"error": "Machine in alarm state"}), 500
                
                if movement_complete:
                    # Get final position
                    final_x, final_y = self.turntable.current()
                    print(f"[REST API] POST /reset - Reset completed in {elapsed_time:.2f}s")
                    print(f"[REST API] POST /reset - Final position: angle={final_x:.1f}°, tilt={final_y:.1f}°")
                    print(f"[REST API] POST /reset - Response: 200 OK")
                    return jsonify({"status": "success"}), 200
                else:
                    # Reset didn't complete - could be timeout or other error
                    current_state = self.grbl_controller.machine_state
                    print(f"[REST API] POST /reset - Error: Reset failed after {elapsed_time:.2f}s (state: {current_state.value})")
                    # Resync position after timeout/error
                    self._resync_position()
                    if current_state == MachineState.ALARM:
                        return jsonify({"error": "Machine in alarm state"}), 500
                    else:
                        return jsonify({"error": "Reset timeout"}), 504
            except Exception as e:
                elapsed_time = time.time() - start_time
                print(f"[REST API] POST /reset - Exception after {elapsed_time:.2f}s: {e}")
                import traceback
                print(f"[REST API] POST /reset - Traceback: {traceback.format_exc()}")
                # Resync position after exception
                self._resync_position()
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/status', methods=['GET'])
        def get_status():
            """Get current turntable status (immediate response, no waiting)."""
            start_time = time.time()
            client_ip = request.remote_addr
            
            print(f"[REST API] GET /status - Request from {client_ip}")
            
            try:
                x_angle, y_angle = self.turntable.current()
                connected = self.grbl_controller.connected
                
                # Convert to int as per specification (Angle and Tilt should be int)
                response_data = {
                    "angle": int(round(x_angle)),
                    "tilt": int(round(y_angle)),
                    "connected": connected
                }
                
                elapsed_time = time.time() - start_time
                print(f"[REST API] GET /status - Response: angle={response_data['angle']}°, tilt={response_data['tilt']}°, connected={connected} (took {elapsed_time*1000:.1f}ms)")
                print(f"[REST API] GET /status - Response: 200 OK")
                
                return jsonify(response_data), 200
            except Exception as e:
                elapsed_time = time.time() - start_time
                print(f"[REST API] GET /status - Exception after {elapsed_time:.2f}s: {e}")
                import traceback
                print(f"[REST API] GET /status - Traceback: {traceback.format_exc()}")
                return jsonify({"error": str(e)}), 500
    
    def _resync_position(self) -> None:
        """
        Resync position from GRBL after an error.
        This ensures the internal position tracking matches GRBL's actual position.
        """
        if not self.grbl_controller.connected:
            return
        
        try:
            # Query GRBL status to get current position
            status_info = self.grbl_controller.query_status()
            if status_info:
                # The status query will trigger position updates via callbacks
                # This ensures the UI and internal tracking are updated
                print(f"[REST API] Position resynced from GRBL status report")
            else:
                # If query failed, at least trigger a status poll
                print(f"[REST API] Status query failed, position may be out of sync")
        except Exception as e:
            print(f"[REST API] Error resyncing position: {e}")
    
    def _setup_error_handlers(self) -> None:
        """Configure error handlers."""
        
        @self.app.errorhandler(400)
        def bad_request(error):
            print(f"[REST API] Error 400 - Bad Request")
            return jsonify({"error": "Bad Request"}), 400
        
        @self.app.errorhandler(500)
        def internal_error(error):
            print(f"[REST API] Error 500 - Internal Server Error: {error}")
            return jsonify({"error": "Internal Server Error"}), 500
        
        @self.app.errorhandler(503)
        def service_unavailable(error):
            print(f"[REST API] Error 503 - Service Unavailable")
            return jsonify({"error": "Service Unavailable"}), 503
        
        @self.app.errorhandler(504)
        def gateway_timeout(error):
            print(f"[REST API] Error 504 - Gateway Timeout")
            return jsonify({"error": "Gateway Timeout"}), 504
    
    def start(self) -> None:
        """Start Flask server in background thread."""
        if not self.enabled:
            print(f"[REST API] Server disabled in configuration")
            return
        
        if self.server_thread and self.server_thread.is_alive():
            print(f"[REST API] Server already running")
            return  # Already running
        
        def run_server():
            self._running = True
            print(f"[REST API] Starting server on {self.host}:{self.port}")
            print(f"[REST API] Server started - Ready to accept requests")
            self.app.run(
                host=self.host,
                port=self.port,
                debug=self.debug,
                threaded=True,
                use_reloader=False
            )
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        print(f"[REST API] Server thread started")
    
    def stop(self) -> None:
        """Stop Flask server."""
        print(f"[REST API] Stopping server...")
        self._running = False
        # Flask daemon thread will auto-terminate when main process exits
        # For true graceful shutdown, would need Werkzeug shutdown mechanism
        print(f"[REST API] Server stopped")
