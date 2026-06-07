from datetime import datetime, timedelta
from typing import Dict, Any
import logging
from celery_config import celery_app
from database import get_db
from services.backtest_engine import run_backtest


def _save(strategy: str, data: dict):
    try:
        db = get_db()
        db.backtest_results.replace_one(
            {"_id": "latest"},
            {**data, "saved_at": datetime.now()},
            upsert=True,
        )
    except Exception as e:
        logging.warning(f"保存回测结果失败: {e}")


@celery_app.task(bind=True, name="tasks.backtest.run_simple")
def run_simple_backtest(
    self,
    strategy: str = "portfolio_rule_engine",
    days_back: int = 360,
    initial_cash: float = 100000,
    commission: float = 0.001,
    max_stocks: int = 500,
    max_positions: int = 5,
) -> Dict[str, Any]:

    db = get_db()
    task_id = self.request.id
    db.backtest_progress.update_one(
        {"_id": task_id},
        {"$set": {"current": 0, "total": 0, "status": "初始化...", "detail": "", "updated_at": datetime.now()}},
        upsert=True,
    )

    start = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")

    result = run_backtest(
        strategy_name=strategy,
        start_date=start,
        end_date=end,
        initial_cash=initial_cash,
        commission=commission,
        max_stocks=max_stocks,
        max_positions=max_positions,
        celery_task=self,
        task_id=task_id,
    )

    _save(strategy, result)
    return result
