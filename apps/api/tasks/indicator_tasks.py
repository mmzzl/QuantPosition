from celery_config import celery_app
from bin.indicator_calculator import run_daily_update, backfill_all_indicators
from database import get_db


@celery_app.task(bind=True, name="tasks.indicators.update")
def update_indicators(self):
    """Celery 任务：每日指标更新"""
    self.update_state(state='PROGRESS', meta={'status': '开始更新指标...'})
    return run_daily_update()


@celery_app.task(bind=True, name="tasks.indicators.backfill")
def backfill_indicators(self):
    """Celery 任务：回填所有历史指标"""
    self.update_state(state='PROGRESS', meta={'status': '开始回填指标...'})
    db = get_db()
    updated, errors = backfill_all_indicators(db)
    return {"updated": updated, "errors": errors}
