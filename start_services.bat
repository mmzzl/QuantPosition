@echo off
cd /d "%~dp0"

echo Starting GraphifyAPI ...
nssm start GraphifyAPI

echo Starting GraphifyCelery ...
nssm start GraphifyCelery

echo Starting GraphifyScheduler ...
nssm start GraphifyScheduler

echo All services started.
pause
