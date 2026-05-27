import os
import sys
import logging
# 确保当前目录在模块搜索路径中（celery 可能从其他目录启动）
_app_dir = os.path.dirname(os.path.abspath(__file__))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

from celery import Celery
from config.config import settings
from systems.logs import Log

celery_app = Celery(
    'tasks',
    broker=f'redis://{settings.redis_host}:{settings.redis_port}/1',
    backend=f'redis://{settings.redis_host}:{settings.redis_port}/2'
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    task_soft_time_limit=3000
)

# 显式导入任务模块，确保 @celery_app.task 装饰器注册
from tasks import selection_tasks  # noqa
from tasks import news_selection_tasks  # noqa
from tasks import kline_tasks  # noqa
from tasks import backtest_tasks  # noqa
Log("celery", log_type=Log.TYPE_FILE, level=logging.INFO)
