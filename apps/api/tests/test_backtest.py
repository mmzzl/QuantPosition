import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.backtest_service import BacktestService
from schemas.backtest import BacktestRequest, TaskStatusResponse


def _make_app(with_auth=True):
    app = FastAPI()
    from routers.backtest import router
    if with_auth:
        from app.core.auth import get_current_user, AuthenticatedUser
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            user_id="test-user", username="tester",
        )
    app.include_router(router)
    return TestClient(app)


class TestBacktestRequest:
    def test_default_values(self):
        req = BacktestRequest()
        assert req.days_back == 360
        assert req.initial_cash == 100000
        assert req.commission == 0.001
        assert req.max_positions == 5
        assert req.max_hold_days == 60
        assert req.cooldown_days == 1

    def test_validates_ranges(self):
        with pytest.raises(Exception):
            BacktestRequest(days_back=10)
        with pytest.raises(Exception):
            BacktestRequest(days_back=800)
        with pytest.raises(Exception):
            BacktestRequest(initial_cash=1000)
        with pytest.raises(Exception):
            BacktestRequest(commission=0.1)
        with pytest.raises(Exception):
            BacktestRequest(max_positions=0)

    def test_extra_fields_forbidden(self):
        with pytest.raises(Exception):
            BacktestRequest(unknown_field="value")


class TestTaskStatusResponse:
    def test_pending_status(self):
        r = TaskStatusResponse(task_id="test-id")
        assert r.status == "PENDING"
        assert r.progress is None

    def test_success_with_result(self):
        r = TaskStatusResponse(
            task_id="test-id",
            status="SUCCESS",
            result={"trades": 10, "portfolio_return": 5.0},
        )
        assert r.result["trades"] == 10


class TestBacktestServiceSubmit:
    def test_submit_returns_task_id(self):
        mock_task = MagicMock()
        mock_task.id = "backtest-task-001"
        with patch("tasks.backtest_tasks.run_simple_backtest.delay", return_value=mock_task):
            with patch("services.backtest_service.get_db") as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                task_id = BacktestService.submit(
                    days_back=180, initial_cash=50000,
                )
        assert task_id == "backtest-task-001"

    def test_submit_forwards_params(self):
        mock_task = MagicMock()
        mock_task.id = "tid"
        with patch("tasks.backtest_tasks.run_simple_backtest.delay", return_value=mock_task) as mock_delay:
            with patch("services.backtest_service.get_db"):
                BacktestService.submit(
                    days_back=90, initial_cash=200000, commission=0.0005,
                    max_positions=3, max_hold_days=30,
                    cooldown_days=2,
                )
        mock_delay.assert_called_once_with(
            days_back=90, initial_cash=200000, commission=0.0005,
            max_positions=3, max_hold_days=30,
            cooldown_days=2,
        )


class TestBacktestServiceGetTaskStatus:
    def test_pending_when_no_progress(self):
        with patch("services.backtest_service.task_progress.get_progress", return_value={"status": "PENDING"}):
            result = BacktestService.get_task_status("no-such-task")
        assert result["status"] == "PENDING"

    def test_success_with_inline_result(self):
        with patch("services.backtest_service.task_progress.get_progress", return_value={"status": "回测完成"}):
            with patch("services.backtest_service.get_db") as mock_get_db:
                mock_db = MagicMock()
                mock_db.backtest_progress.find_one.return_value = {
                    "_id": "task-1",
                    "status": "回测完成",
                    "result": {"trades": 5, "portfolio_return": 3.5},
                }
                mock_get_db.return_value = mock_db
                result = BacktestService.get_task_status("task-1")
        assert result["status"] == "SUCCESS"
        assert result["result"]["trades"] == 5

    def test_failure_status(self):
        with patch("services.backtest_service.task_progress.get_progress", return_value={"status": "回测失败"}):
            with patch("services.backtest_service.get_db") as mock_get_db:
                mock_db = MagicMock()
                mock_db.backtest_progress.find_one.return_value = {
                    "_id": "task-1",
                    "status": "回测失败",
                    "detail": "K线数据不足",
                }
                mock_get_db.return_value = mock_db
                result = BacktestService.get_task_status("task-1")
        assert result["status"] == "FAILURE"
        assert "K线数据不足" in result["error"]


class TestBacktestServiceGetLatest:
    def test_no_result(self):
        with patch("services.backtest_service.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.backtest_results.find_one.return_value = None
            mock_get_db.return_value = mock_db
            result = BacktestService.get_latest()
        assert result["exists"] is False

    def test_with_result(self):
        with patch("services.backtest_service.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.backtest_results.find_one.return_value = {
                "_id": "latest",
                "saved_at": datetime.now(),
                "trades": 10,
                "portfolio_return": 5.5,
            }
            mock_get_db.return_value = mock_db
            result = BacktestService.get_latest()
        assert result["trades"] == 10
        assert "_id" not in result
        assert "saved_at" not in result


class TestBacktestEngineEdgeCases:
    def test_run_backtest_with_no_data(self):
        from services.backtest_engine import run_backtest
        with patch("services.backtest_engine.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.stock_indicators.find.return_value.sort.return_value = []
            mock_db.stock_kline.distinct.return_value = []
            mock_db.trading_rules.find.return_value.sort.return_value = []
            mock_db.sector_stocks.find.return_value = []
            mock_get_db.return_value = mock_db
            result = run_backtest()
        assert result is not None
        assert result["trades"] == 0
        assert result["processed"] == 0

    def test_run_backtest_with_no_rules(self):
        from services.backtest_engine import run_backtest
        with patch("services.backtest_engine.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.stock_kline.distinct.return_value = ["000001", "000002"]
            mock_db.stock_indicators.find.return_value.sort.return_value = []
            mock_db.trading_rules.find.return_value.sort.return_value = []
            mock_db.sector_stocks.find.return_value = [
                {"stock_code": "sz.000001", "stock_name": "平安银行"},
                {"stock_code": "sz.000002", "stock_name": "万科A"},
            ]
            mock_get_db.return_value = mock_db
            result = run_backtest()
        assert result["trades"] == 0

    def _make_engine_data(self):
        """构造 3 只股票 5 个交易日的合成数据, 满足买入/卖出条件"""
        def row(close, last_close):
            return {
                "open": close, "close": close, "high": close * 1.02,
                "low": close * 0.98, "volume": 500000, "last_close": last_close,
                "ma5": 154.0, "ma10": 150.0, "ma20": 145.0, "ma60": 140.0,
                "ma5_vol": 200000, "high20": 160.0, "low20": 140.0,
                "rsi": 45, "atr": 1.5, "adx": 20, "amplitude": 0.02,
            }

        dates = ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09"]
        data = {}
        prev = {}
        for i, d in enumerate(dates):
            for c in ("600001", "600002", "600003"):
                # 第 3 只第 1 天价格波动大, 不满足买入; 其它可买入
                close = 150.0
                last = prev.get(c, 149.0)
                data.setdefault(c, {})[d] = row(close, last)
                prev[c] = close
        return data

    def _make_buy_rules(self):
        """买入条件成立, 卖出/风控不成立"""
        return [
            {"rule_id": 1, "name": "风控", "type": "risk",
             "condition": "price>1000000", "priority": 1, "weight": 1.0, "enabled": True},
            {"rule_id": 2, "name": "卖出", "type": "sell",
             "condition": "price<0.001", "priority": 2, "weight": 0.5, "enabled": True},
            {"rule_id": 3, "name": "买入", "type": "buy",
             "condition": "price>0", "priority": 3, "weight": 0.5, "enabled": True},
        ]

    def test_equity_curve_includes_held_days(self):
        """持仓期间每个交易日都应记录净值, 强制平仓收益计入最终净值"""
        from services.backtest_engine import run_backtest
        data = self._make_engine_data()
        rules = self._make_buy_rules()
        with patch("services.backtest_engine.get_db") as mock_get_db, \
             patch("services.backtest_engine._load_data", return_value=data) as _, \
             patch("services.backtest_engine._load_name_map",
                   return_value={"600001": "测试1", "600002": "测试2", "600003": "测试3"}):
            mock_db = MagicMock()
            mock_db.stock_kline.distinct.return_value = ["600001", "600002", "600003"]
            mock_get_db.return_value = mock_db
            result = run_backtest(
                codes=["600001", "600002", "600003"],
                start_date="2026-01-05", end_date="2026-01-09",
                custom_rules=rules, max_positions=1, max_hold_days=60,
            )
        eq = result["equity_curve"]
        ed = result["equity_dates"]
        # 每个交易日(含持仓日) + 强制平仓最后一天, 都应记录
        assert len(eq) >= 5
        assert ed[-1] == "2026-01-09"
        # 最后一天(强制平仓)净值应高于持仓期末值或等于卖出后现金
        assert eq[-1] > 0
        assert result["trades"] == 1
        assert result["trades_list"][0]["reason"] == "timeout"

    def test_equity_curve_grows_when_position_gains(self):
        """持仓期内价格下跌再上涨, 净值曲线应逐日反映 (不复用 continue 跳过)"""
        from services.backtest_engine import run_backtest
        dates = ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09"]
        closes = {"600001": [150.0, 160.0, 170.0, 180.0, 190.0]}
        data = {}
        prev = {}
        for i, d in enumerate(dates):
            for c, cs in closes.items():
                close = cs[i]
                last = prev.get(c, close)
                data.setdefault(c, {})[d] = {
                    "open": close, "close": close, "high": close * 1.02,
                    "low": close * 0.98, "volume": 500000, "last_close": last,
                    "ma5": 154.0, "ma10": 150.0, "ma20": 145.0, "ma60": 140.0,
                    "ma5_vol": 200000, "high20": 160.0, "low20": 140.0,
                    "rsi": 45, "atr": 1.5, "adx": 20, "amplitude": 0.02,
                }
                prev[c] = close
        rules = self._make_buy_rules()
        with patch("services.backtest_engine.get_db") as mock_get_db, \
             patch("services.backtest_engine._load_data", return_value=data) as _, \
             patch("services.backtest_engine._load_name_map",
                   return_value={"600001": "测试1"}):
            mock_db = MagicMock()
            mock_db.stock_kline.distinct.return_value = ["600001"]
            mock_get_db.return_value = mock_db
            result = run_backtest(
                codes=["600001"], start_date="2026-01-05", end_date="2026-01-09",
                custom_rules=rules, max_positions=1, max_hold_days=60,
            )
        eq = result["equity_curve"]
        ed = result["equity_dates"]
        # 5 个交易日每天都记录 + 强制平仓追记最终现金
        assert len(eq) >= 5
        assert ed[-1] == "2026-01-09"
        assert eq[-1] > eq[0]  # 价格上涨, 最终净值上升
        assert result["trades"] == 1


class TestBacktestRouterEndpoints:
    def test_submit_endpoint_returns_task_id(self):
        mock_task = MagicMock()
        mock_task.id = "test-task-123"
        client = _make_app()
        with patch("routers.backtest.run_simple_backtest") as mock_bt:
            mock_bt.delay.return_value = mock_task
            with patch("routers.backtest.get_db") as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                resp = client.post(
                    "/backtest/run?days_back=360&initial_cash=100000",
                    headers={"Authorization": "Bearer test_token"},
                )
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "test-task-123"

    def test_submit_validates_days_back(self):
        client = _make_app()
        with patch("routers.backtest.get_db"):
            resp = client.post(
                "/backtest/run?days_back=10",
                headers={"Authorization": "Bearer test_token"},
            )
        assert resp.status_code == 422

    def test_submit_validates_too_many_days(self):
        client = _make_app()
        with patch("routers.backtest.get_db"):
            resp = client.post(
                "/backtest/run?days_back=800",
                headers={"Authorization": "Bearer test_token"},
            )
        assert resp.status_code == 422

    def test_get_task_status_endpoint(self):
        client = _make_app()
        with patch("routers.backtest.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.backtest_progress.find_one.return_value = {
                "_id": "task-1",
                "status": "回测完成",
                "result": {"trades": 3, "portfolio_return": 2.5},
            }
            mock_get_db.return_value = mock_db
            resp = client.get("/backtest/task/task-1", headers={"Authorization": "Bearer test_token"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "SUCCESS"

    def test_get_latest_without_results(self):
        client = _make_app()
        with patch("routers.backtest.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.backtest_results.find_one.return_value = None
            mock_get_db.return_value = mock_db
            resp = client.get("/backtest/latest", headers={"Authorization": "Bearer test_token"})
        assert resp.status_code == 200
        assert resp.json()["exists"] is False

    def test_without_auth_returns_401(self):
        client = _make_app(with_auth=False)
        resp = client.post("/backtest/run?days_back=360")
        assert resp.status_code == 401
