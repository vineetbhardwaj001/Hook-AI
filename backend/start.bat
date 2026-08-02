@echo off
REM ============================================================
REM Hook AI Backend — Windows Startup Script
REM ============================================================

cd /d "%~dp0"
echo.
echo [Hook AI] Starting FastAPI backend...
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.11+
    pause
    exit /b 1
)

REM Check if uvicorn is installed
python -c "import uvicorn" >nul 2>&1
if errorlevel 1 (
    echo [Hook AI] Installing dependencies...
    pip install -r requirements.txt
)

REM Load .env
if exist ".env" (
    echo [Hook AI] Loaded .env configuration
) else (
    echo [Hook AI] WARNING: .env not found. Using defaults.
)

echo [Hook AI] Starting server on http://0.0.0.0:8000
echo [Hook AI] API docs: http://localhost:8000/docs
echo.

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause
