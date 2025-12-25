import argparse
import sys
import requests
import json

API_BASE_URL = "http://localhost:5001"

def set_position(angle=None, tilt=None):
    """Calls the /position endpoint."""
    url = f"{API_BASE_URL}/position"
    headers = {'Content-Type': 'application/json'}
    
    data = {}
    if angle is not None:
        data['angle'] = angle
    if tilt is not None:
        data['tilt'] = tilt

    try:
        response = requests.put(url, headers=headers, data=json.dumps(data), timeout=30)
        response.raise_for_status()  # Raises an exception for 4XX/5XX errors
        print("Successfully set position.")
        print("Response:", response.json())
    except requests.exceptions.RequestException as e:
        print(f"Error setting position: {e}", file=sys.stderr)
        sys.exit(1)

def reset_position():
    """Calls the /reset endpoint."""
    url = f"{API_BASE_URL}/reset"
    try:
        response = requests.post(url, timeout=30)
        response.raise_for_status()
        print("Successfully reset position.")
        print("Response:", response.json())
    except requests.exceptions.RequestException as e:
        print(f"Error resetting position: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Client for Revopoint Dual Axis Turntable GUI API.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # Rotate command
    parser_rotate = subparsers.add_parser("rotate", help="Rotate the turntable to a specific absolute angle.")
    parser_rotate.add_argument("angle", type=int, help="Absolute angle in degrees (e.g., 0, 90, 180, 270).")

    # Tilt command
    parser_tilt = subparsers.add_parser("tilt", help="Tilt the turntable to an absolute angle.")
    parser_tilt.add_argument("angle", type=int, help="Absolute angle in degrees (between -30 and 30).")

    # Reset command
    subparsers.add_parser("reset", help="Reset the turntable to the zero position.")

    if len(sys.argv) < 2:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    if args.command == 'reset':
        reset_position()
    elif args.command == 'rotate':
        set_position(angle=args.angle)
    elif args.command == 'tilt':
        set_position(tilt=args.angle)

if __name__ == "__main__":
    main()
