from datetime import datetime, timedelta
from typing import Dict, Any, List
from celery_config import celery_app
from database import get_db
from services.backtest_engine import run_backtest, STRATEGY_MAP


def _save(name: str, data: dict):
    try:
        db = get_db()
        db.backtest_results.replace_one(
            {"_id": "latest"},
            {**data, "name": name, "saved_at": datetime.now()},
            upsert=True,
        )
    except Exception:
        pass


@celery_app.task(bind=True, name="tasks.backtest.run_simple")
def run_simple_backtest(
    self,
    strategy: str = "dual_ma",
    days_back: int = 180,
    hold_days: List[int] = None,
    use_rules: bool = False,
    initial_cash: float = 100000,
    commission: float = 0.001,
) -> Dict[str, Any]:

    self.update_state(state="PROGRESS", meta={"current": 0, "total": 0, "status": "加载K线数据..."})

    db = get_db()
    today = datetime.now()
    start_date = (today - timedelta(days=days_back)).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")

    codes = db.stock_kline.distinct("code", {"frequency": 9})
    total = len(codes)

    self.update_state(state="PROGRESS", meta={
        "current": 0, "total": total,
        "status": f"共{total}只股票，回测中..."
    })

    name_map = {}
    for s in db.sector_stocks.find({}, {"stock_code": 1, "stock_name": 1}):
        pure = s["stock_code"].split(".")[-1]
        name_map[pure] = s.get("stock_name", "")

    filtered = []
    for code in codes:
        name = name_map.get(code, "")
        if name.startswith("ST") or name.startswith("*ST"):
            continue
        filtered.append(code)

    self.update_state(state="PROGRESS", meta={
        "current": 0, "total": len(filtered),
        "status": f"排除ST后{len(filtered)}只，开始Backtrader回测..."
    })

    result = run_backtest(
        strategy_name=strategy,
        codes=filtered,
        start_date=start_date,
        end_date=end_date,
        initial_cash=initial_cash,
        commission=commission,
    )

    self.update_state(state="PROGRESS", meta={
        "current": len(filtered), "total": len(filtered),
        "status": "回测完成"
    })

    _save(strategy, result)
    return result
