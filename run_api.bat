@echo off
set PYTHONUTF8=1
cd /d D:\home\apps\api
python -m uvicorn main:app --host 0.0.0.0 --port 8000
