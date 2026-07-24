import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.backtest_service import BacktestService
from schemas.backtest import BacktestRequest, BackendMetricsResponse, TaskStatusResponse


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
        assert req.max_stocks == 500
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


class TestBackendMetricsResponse:
    def test_valid_metrics(self):
        m = BackendMetricsResponse(
            annual_return=15.2,
            sharpe_ratio=1.5,
            max_drawdown=8.3,
            win_rate=55.0,
            total_return=12.0,
            total_trades=100,
        )
        assert m.annual_return == 15.2
        assert m.sharpe_ratio == 1.5
        assert m.max_drawdown == 8.3
        assert m.win_rate == 55.0
        assert m.total_trades == 100


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
                    max_stocks=100, max_positions=3, max_hold_days=30,
                    cooldown_days=2,
                )
        mock_delay.assert_called_once_with(
            days_back=90, initial_cash=200000, commission=0.0005,
            max_stocks=100, max_positions=3, max_hold_days=30,
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
            result = run_backtest(max_stocks=0)
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
            result = run_backtest(max_stocks=2)
        assert result["trades"] == 0


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
