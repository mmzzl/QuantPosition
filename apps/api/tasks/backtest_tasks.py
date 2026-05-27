from datetime import datetime, timedelta
from typing import Dict, Any
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
    except Exception:
        pass


@celery_app.task(bind=True, name="tasks.backtest.run_simple")
def run_simple_backtest(
    self,
    strategy: str = "rule_engine",
    days_back: int = 180,
    initial_cash: float = 100000,
    commission: float = 0.001,
) -> Dict[str, Any]:

    self.update_state(state="PROGRESS", meta={"current": 0, "total": 0, "status": "加载规则..."})

    start = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")

    self.update_state(state="PROGRESS", meta={"current": 0, "total": 0, "status": "回测中..."})

    result = run_backtest(
        strategy_name=strategy,
        start_date=start,
        end_date=end,
        initial_cash=initial_cash,
        commission=commission,
    )

    _save(strategy, result)
    return result
