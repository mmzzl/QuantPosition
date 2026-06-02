@echo off
cd /d "%~dp0"

echo Stopping GraphifyScheduler ...
nssm stop GraphifyScheduler

echo Stopping GraphifyCelery ...
nssm stop GraphifyCelery

echo Stopping GraphifyAPI ...
nssm stop GraphifyAPI

echo All services stopped.
pause
