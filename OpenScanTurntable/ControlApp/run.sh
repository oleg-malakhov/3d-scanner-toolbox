#!/bin/bash

# OpenScan Turntable Control App Launcher (Linux/macOS)
# Uses uv for Python environment management

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "Error: uv is not installed or not in PATH"
    echo ""
    echo "Please install uv first:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo ""
    echo "Or visit: https://github.com/astral-sh/uv"
    exit 1
fi

# Detect macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    # On macOS, use system Python (which has tkinter) but uv for dependencies
    echo "macOS detected: Using system Python with tkinter support"
    
    # Check if system Python 3 is available
    if ! command -v python3 &> /dev/null; then
        echo "Error: Python 3 is not installed"
        echo "Please install Python 3.8+ from https://www.python.org/ or via Homebrew"
        exit 1
    fi
    
    # Check Python version
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
        echo "Error: Python 3.8 or later is required. Found Python $PYTHON_VERSION"
        exit 1
    fi
    
    # Check if tkinter is available
    if ! python3 -c "import tkinter" &> /dev/null; then
        echo "Error: tkinter is not available in system Python"
        echo "On macOS, you may need to install Python via Homebrew:"
        echo "  brew install python-tk"
        exit 1
    fi
    
    # Use uv to install dependencies into a virtual environment
    if [ ! -d ".venv" ]; then
        echo "Creating virtual environment..."
        uv venv --python "$(which python3)"
        if [ $? -ne 0 ]; then
            echo "Error: Failed to create virtual environment"
            exit 1
        fi
    fi
    
    # Install dependencies using uv
    echo "Installing dependencies..."
    uv pip install -r requirements.txt
    
    if [ $? -ne 0 ]; then
        echo "Error: Failed to install dependencies"
        exit 1
    fi
    
    # Run with system Python (which has tkinter) but use venv's site-packages
    echo "Starting OpenScan Turntable Control App..."
    # Use system Python but add venv's site-packages to path
    PYTHONPATH=".venv/lib/python$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')/site-packages:$PYTHONPATH" python3 main.py
    
else
    # On Linux, use uv's Python (which should have tkinter)
    echo "Using uv for Python environment management"
    
    # Create virtual environment if it doesn't exist
    if [ ! -d ".venv" ]; then
        echo "Creating virtual environment..."
        uv venv --python 3.8+
        if [ $? -ne 0 ]; then
            echo "Error: Failed to create virtual environment"
            exit 1
        fi
    fi
    
    # Install dependencies from requirements.txt into the virtual environment
    echo "Installing dependencies..."
    uv pip install -r requirements.txt
    
    if [ $? -ne 0 ]; then
        echo "Error: Failed to install dependencies"
        exit 1
    fi
    
    # Run the application using uv (automatically uses .venv in current directory)
    echo "Starting OpenScan Turntable Control App..."
    uv run main.py
fi

