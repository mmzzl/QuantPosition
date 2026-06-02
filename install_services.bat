@echo off
cd /d "%~dp0"

set APP_DIR=D:\home\apps\api
set LOG_DIR=D:\home\logs

if not exist "%APP_DIR%" (
    echo ERROR: Directory not found: %APP_DIR%
    pause
    exit /b 1
)

where nssm >nul 2>nul
if %errorlevel% neq 0 (
    echo nssm not found. Download from: https://nssm.cc/download
    echo Extract nssm.exe to C:\Windows\System32 or this directory.
    pause
    exit /b 1
)

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo Installing Graphify services (3 total)...
echo.

:: ---- 1. FastAPI ----
echo [1/3] Installing GraphifyAPI ...
nssm install GraphifyAPI cmd /c "D:\home\run_api.bat"
nssm set GraphifyAPI AppDirectory "%APP_DIR%"
nssm set GraphifyAPI AppStdout "%LOG_DIR%\api_stdout.log"
nssm set GraphifyAPI AppStderr "%LOG_DIR%\api_stderr.log"
nssm set GraphifyAPI AppRotateFiles 1
nssm set GraphifyAPI AppRotateSeconds 86400
nssm set GraphifyAPI Start SERVICE_AUTO_START
nssm set GraphifyAPI DisplayName "Graphify API (FastAPI)"
nssm set GraphifyAPI Description "Graphify backend FastAPI service"
echo Done

:: ---- 2. Celery Worker ----
echo [2/3] Installing GraphifyCelery ...
nssm install GraphifyCelery cmd /c "D:\home\run_celery.bat"
nssm set GraphifyCelery AppDirectory "%APP_DIR%"
nssm set GraphifyCelery AppStdout "%LOG_DIR%\celery_stdout.log"
nssm set GraphifyCelery AppStderr "%LOG_DIR%\celery_stderr.log"
nssm set GraphifyCelery AppRotateFiles 1
nssm set GraphifyCelery AppRotateSeconds 86400
nssm set GraphifyCelery Start SERVICE_AUTO_START
nssm set GraphifyCelery DisplayName "Graphify Celery Worker"
nssm set GraphifyCelery Description "Graphify Celery async task worker"
echo Done

:: ---- 3. Scheduler ----
echo [3/3] Installing GraphifyScheduler ...
nssm install GraphifyScheduler cmd /c "D:\home\run_scheduler.bat"
nssm set GraphifyScheduler AppDirectory "%APP_DIR%"
nssm set GraphifyScheduler AppStdout "%LOG_DIR%\scheduler_stdout.log"
nssm set GraphifyScheduler AppStderr "%LOG_DIR%\scheduler_stderr.log"
nssm set GraphifyScheduler AppRotateFiles 1
nssm set GraphifyScheduler AppRotateSeconds 86400
nssm set GraphifyScheduler Start SERVICE_AUTO_START
nssm set GraphifyScheduler DisplayName "Graphify Scheduler"
nssm set GraphifyScheduler Description "Graphify scheduled task scheduler (APScheduler)"
echo Done

echo.
echo All services installed successfully!
echo.
echo To start:  nssm start GraphifyAPI ^& nssm start GraphifyCelery ^& nssm start GraphifyScheduler
echo To stop:   nssm stop GraphifyAPI ^& nssm stop GraphifyCelery ^& nssm stop GraphifyScheduler
echo To remove: uninstall_services.bat
echo.
echo Logs: %LOG_DIR%\*_stdout.log / *_stderr.log
echo.
echo Start all services now?
choice /c YN /m "Start now"
if %errorlevel% equ 1 (
    echo Starting GraphifyAPI ...
    nssm start GraphifyAPI
    echo Starting GraphifyCelery ...
    nssm start GraphifyCelery
    echo Starting GraphifyScheduler ...
    nssm start GraphifyScheduler
    echo All services started.
) else (
    echo Skipped. You can run start_services.bat later.
)

pause
