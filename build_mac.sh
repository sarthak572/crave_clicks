#!/bin/bash
set -e

echo "Starting build process for Mac..."

# Function to check python version >= 3.12
check_python_version() {
    if command -v python3 &> /dev/null; then
        python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' &> /dev/null
        return $?
    else
        return 1
    fi
}

echo "Checking for Python 3.12 or newer..."
if ! check_python_version; then
    echo "Python 3.12+ is not installed or not found."
    echo "Downloading official Python 3.12 installer for macOS..."
    curl -O https://www.python.org/ftp/python/3.12.6/python-3.12.6-macos11.pkg
    
    echo "Installing Python 3.12... (You may be prompted for your Mac administrator password)"
    sudo installer -pkg python-3.12.6-macos11.pkg -target /
    
    # Remove the installer after successful installation
    rm python-3.12.6-macos11.pkg
    
    echo "Python installed successfully."
else
    echo "Python 3.12+ is already installed."
fi

# Python 3 is standard on Mac
PYTHON_CMD="python3"

echo "Upgrading pip..."
$PYTHON_CMD -m pip install --upgrade pip

echo "Installing project dependencies (PySide6, SQLAlchemy, etc.)..."
$PYTHON_CMD -m pip install .

echo "Installing PyInstaller..."
$PYTHON_CMD -m pip install "PyInstaller>=6,<7"

echo "Building the application using PyInstaller..."
$PYTHON_CMD -m PyInstaller CafePOS.spec --clean -y

echo "=============================================="
echo "Build completed successfully!"
echo "You can find your Mac application in the 'dist' folder."
echo "Look for 'dist/CafePOS.app' or 'dist/CafePOS'."
echo "=============================================="
