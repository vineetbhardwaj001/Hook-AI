@echo off
REM ============================================================
REM Hook AI — Celery Worker Startup Script (Windows)
REM ============================================================

cd /d "%~dp0"
echo.
echo [Hook AI Celery] Starting analysis worker...
echo.

python -m celery -A app.workers.celery_app worker --loglevel=info -Q analysis,cleanup -c 2

pause
