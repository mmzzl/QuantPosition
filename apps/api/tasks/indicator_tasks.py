from celery_config import celery_app
from bin.indicator_calculator import IndicatorCalculator, run_daily_update
from database import get_db


@celery_app.task(bind=True, name="tasks.indicators.update")
def update_indicators(self):
    self.update_state(state='PROGRESS', meta={'status': '开始更新指标...'})
    calculator = IndicatorCalculator()
    db = calculator.db
    today_str = datetime.now().strftime("%Y-%m-%d")
    from bin.indicator_calculator import get_codes_with_klines_today
    codes = get_codes_with_klines_today(db, today_str)
    if not codes:
        self.update_state(state='SUCCESS', meta={'status': '今日无新 K 线数据，跳过'})
        return {"updated": 0, "errors": 0}
    from bin.indicator_calculator import update_stock_indicators
    updated, errors = update_stock_indicators(db, codes)
    return {"updated": updated, "errors": errors}


@celery_app.task(bind=True, name="tasks.indicators.backfill")
def backfill_indicators(self):
    self.update_state(state='PROGRESS', meta={'status': '开始回填指标...'})
    calculator = IndicatorCalculator()
    updated, errors = calculator.backfill()
    return {"updated": updated, "errors": errors}

from datetime import datetime
