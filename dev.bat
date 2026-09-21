@echo off
REM RSI-Filtered MACD Momentum Stock Scanner - Development Script for Windows
REM Installs dependencies and runs the stock scanner

setlocal enabledelayedexpansion

echo ==========================================
echo Stock Scanner - Setup ^& Run
echo ==========================================
echo.

REM Get the directory where the script is located
cd /d "%~dp0"

REM Detect Python executable
REM Try python first, then py launcher, then python3
set PYTHON_CMD=python
python --version >nul 2>&1
if errorlevel 1 (
    set PYTHON_CMD=py
    py --version >nul 2>&1
    if errorlevel 1 (
        set PYTHON_CMD=python3
        python3 --version >nul 2>&1
        if errorlevel 1 (
            echo Error: Python is not installed or not in PATH
            echo Please install Python from https://www.python.org/downloads/
            pause
            exit /b 1
        )
    )
)

echo Using Python: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

REM Virtual environment setup
set VENV_DIR=venv

REM Create virtual environment if it doesn't exist
if not exist "%VENV_DIR%" (
    echo Creating virtual environment...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo Error: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created!
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo Error: Failed to activate virtual environment
    pause
    exit /b 1
)

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip --quiet
if errorlevel 1 (
    echo Warning: Failed to upgrade pip, continuing anyway...
)

REM Install dependencies
echo Installing dependencies from requirements.txt...
echo.
pip install -r requirements.txt
if errorlevel 1 (
    echo Error: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo Dependencies installed successfully!
echo.
echo ==========================================
echo Running Stock Scanner...
echo ==========================================
echo.

REM Run the Trading Hub using venv Python
python app.py

if errorlevel 1 (
    echo.
    echo Error: Stock scanner failed to run
    pause
    exit /b 1
)

echo.
pause

