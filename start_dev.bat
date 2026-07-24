@echo off
cd /d "%~dp0"

set APP_DIR=D:\home\apps\api
set PYTHON=python
set PYTHONUTF8=1

echo Starting Graphify dev environment...
echo.

echo [1/3] Starting FastAPI (uvicorn) ...
start "Graphify-API" "%PYTHON%" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

echo [2/3] Starting Celery Worker ...
start "Graphify-Celery" cmd /k "set PYTHONUTF8=1 && cd /d %APP_DIR% && %PYTHON% -m celery -A celery_config.celery_app worker --loglevel=info --pool=threads"

echo [3/3] Starting Scheduler ...
start "Graphify-Scheduler" cmd /k "set PYTHONUTF8=1 && cd /d %APP_DIR% && %PYTHON% scheduler/scheduler.py"

echo All 3 services started in separate windows.
pause
