#!/bin/bash

# RSI-Filtered MACD Momentum Stock Scanner - Development Script
# Installs dependencies and runs the stock scanner

set -e  # Exit on error

echo "=========================================="
echo "Stock Scanner - Setup & Run"
echo "=========================================="
echo ""

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Detect Python executable
# Try pyenv Python first if available
PYTHON_CMD="python3"
if command -v pyenv &> /dev/null; then
    PYENV_PYTHON=$(pyenv which python 2>/dev/null || echo "")
    if [ -n "$PYENV_PYTHON" ] && [ -f "$PYENV_PYTHON" ]; then
        PYTHON_CMD="$PYENV_PYTHON"
        echo "Using pyenv Python: $PYTHON_CMD"
    fi
fi

# Fallback to system python3
if ! command -v "$PYTHON_CMD" &> /dev/null && [ "$PYTHON_CMD" != "python3" ]; then
    PYTHON_CMD="python3"
fi

# Check if Python is available
if ! command -v "$PYTHON_CMD" &> /dev/null; then
    echo "Error: Python is not installed or not in PATH"
    exit 1
fi

echo "Using Python: $PYTHON_CMD"
echo "Python version: $($PYTHON_CMD --version)"
echo ""

# Virtual environment setup
VENV_DIR="venv"

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    "$PYTHON_CMD" -m venv "$VENV_DIR"
    echo "Virtual environment created!"
    echo ""
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip --quiet

# Install dependencies
echo "Installing dependencies from requirements.txt..."
echo ""
pip install -r requirements.txt

echo ""
echo "Dependencies installed successfully!"
echo ""
echo "=========================================="
echo "Running Stock Scanner..."
echo "=========================================="
echo ""

# Run the Trading Hub using venv Python
python app.py

