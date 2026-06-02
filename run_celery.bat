@echo off
set PYTHONUTF8=1
cd /d D:\home\apps\api
python -m celery -A celery_config.celery_app worker --loglevel=info --pool=threads
