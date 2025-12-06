@echo off
REM ===================================================
REM  Start SmartParking FastAPI Server (Conda version)
REM ===================================================

echo.
echo ============================================================
echo   Starting SmartParking FastAPI Server
echo ============================================================
echo.

REM Check if conda is available
where conda >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Conda not found!
    echo.
    echo Please:
    echo   1. Open Anaconda Prompt instead of CMD
    echo   2. Or add Conda to PATH
    echo.
    pause
    exit /b 1
)

REM Check if environment exists
conda env list | findstr "smartparking" >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Environment 'smartparking' not found!
    echo.
    echo Creating environment from environment.yml...
    conda env create -f environment.yml
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to create environment!
        pause
        exit /b 1
    )
    echo.
    echo [SUCCESS] Environment created!
    echo.
)

echo Activating Conda environment: smartparking
call conda activate smartparking

echo.
echo Checking Python version...
python --version

echo.
echo Starting FastAPI server...
echo Server will be available at: http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server
echo.

REM Start server
python main_fastapi.py

REM If server stops
echo.
echo Server stopped.
pause

