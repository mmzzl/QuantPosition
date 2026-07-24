@echo off
cd /d "%~dp0"

echo Uninstalling Graphify services ...

where nssm >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: nssm not found
    pause
    exit /b 1
)

for %%s in (GraphifyAPI GraphifyCelery GraphifyScheduler) do (
    echo Stopping %%s ...
    nssm stop %%s >nul 2>nul
    echo Removing %%s ...
    nssm remove %%s confirm
)

echo All services uninstalled.
pause
