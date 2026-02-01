"""REST API server for OpenScan Turntable Control."""

from flask import Flask, request, jsonify
import threading
from typing import Optional

from src.turntable import Turntable
from src.grbl_controller import GRBLController
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
        
        # Initialize Flask app
        self.app = Flask(__name__)
        self._setup_routes()
        self._setup_error_handlers()
        
        # Thread management
        self.server_thread: Optional[threading.Thread] = None
        self._running = False
    
    def _setup_routes(self) -> None:
        """Configure API routes."""
        
        @self.app.route('/position', methods=['PUT'])
        def set_position():
            """Set turntable position (synchronous - waits for completion)."""
            if not self.grbl_controller.connected:
                return jsonify({"error": "Turntable not connected"}), 503
            
            try:
                data = request.get_json()
                if data is None:
                    return jsonify({"error": "Invalid JSON"}), 400
                
                x_angle = data.get('angle')
                y_angle = data.get('tilt')
                
                # Validate at least one angle provided
                if x_angle is None and y_angle is None:
                    return jsonify({"error": "At least one angle must be provided"}), 400
                
                # Validate ranges
                if x_angle is not None:
                    if not isinstance(x_angle, (int, float)) or x_angle < 0 or x_angle > 360:
                        return jsonify({"error": "Angle must be a number between 0 and 360"}), 400
                
                if y_angle is not None:
                    if not isinstance(y_angle, (int, float)) or y_angle < -90 or y_angle > 90:
                        return jsonify({"error": "Tilt must be a number between -90 and 90"}), 400
                
                # Execute movement
                if x_angle is not None and y_angle is not None:
                    success = self.turntable.move_to_angles(x_angle, y_angle)
                elif x_angle is not None:
                    success = self.turntable.rotate_to(Turntable.AXIS_X, x_angle)
                else:  # y_angle is not None
                    success = self.turntable.rotate_to(Turntable.AXIS_Y, y_angle)
                
                if not success:
                    return jsonify({"error": "Movement command failed"}), 500
                
                # Wait for movement to complete (synchronous)
                movement_complete = self.grbl_controller.wait_for_idle(timeout=self.movement_timeout)
                
                if movement_complete:
                    return jsonify({"status": "success"}), 200
                else:
                    return jsonify({"error": "Movement timeout"}), 504
                    
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/reset', methods=['POST'])
        def reset_position():
            """Reset turntable to home position (synchronous - waits for completion)."""
            if not self.grbl_controller.connected:
                return jsonify({"error": "Turntable not connected"}), 503
            
            try:
                success = self.turntable.reset()
                if not success:
                    return jsonify({"error": "Reset command failed"}), 500
                
                # Wait for reset movement to complete (synchronous)
                movement_complete = self.grbl_controller.wait_for_idle(timeout=self.movement_timeout)
                
                if movement_complete:
                    return jsonify({"status": "success"}), 200
                else:
                    return jsonify({"error": "Reset timeout"}), 504
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/status', methods=['GET'])
        def get_status():
            """Get current turntable status (immediate response, no waiting)."""
            try:
                x_angle, y_angle = self.turntable.current()
                connected = self.grbl_controller.connected
                
                return jsonify({
                    "angle": round(x_angle, 1),
                    "tilt": round(y_angle, 1),
                    "connected": connected
                }), 200
            except Exception as e:
                return jsonify({"error": str(e)}), 500
    
    def _setup_error_handlers(self) -> None:
        """Configure error handlers."""
        
        @self.app.errorhandler(400)
        def bad_request(error):
            return jsonify({"error": "Bad Request"}), 400
        
        @self.app.errorhandler(500)
        def internal_error(error):
            return jsonify({"error": "Internal Server Error"}), 500
        
        @self.app.errorhandler(503)
        def service_unavailable(error):
            return jsonify({"error": "Service Unavailable"}), 503
        
        @self.app.errorhandler(504)
        def gateway_timeout(error):
            return jsonify({"error": "Gateway Timeout"}), 504
    
    def start(self) -> None:
        """Start Flask server in background thread."""
        if not self.enabled:
            return
        
        if self.server_thread and self.server_thread.is_alive():
            return  # Already running
        
        def run_server():
            self._running = True
            self.app.run(
                host=self.host,
                port=self.port,
                debug=self.debug,
                threaded=True,
                use_reloader=False
            )
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
    
    def stop(self) -> None:
        """Stop Flask server."""
        self._running = False
        # Flask daemon thread will auto-terminate when main process exits
        # For true graceful shutdown, would need Werkzeug shutdown mechanism
        pass
