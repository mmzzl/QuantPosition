import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock

mock_kline_tasks = MagicMock()
mock_kline_tasks.update_kline_data = MagicMock()
mock_kline_tasks.update_kline_data.delay.return_value = MagicMock(id="test-task-id")
sys.modules["tasks.kline_tasks"] = mock_kline_tasks

from fastapi.testclient import TestClient
from fastapi import FastAPI
from routers.sectors import router
from app.core.auth import get_current_user, AuthenticatedUser

app = FastAPI()
app.include_router(router)

app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
    user_id="test-user", username="testuser"
)

client = TestClient(app)


class TestHeatmapEndpoint:

    def test_returns_200_with_correct_structure(self):
        mock_result = {
            "sectors": [
                {
                    "sector_name": "\u94f6\u884c", "sector_code": "BK001",
                    "change_pct": 2.5, "stock_count": 30, "avg_volume": 1000000,
                    "start_price": 10.0, "end_price": 10.25
                }
            ],
            "period": "24h",
            "total_sectors": 1,
            "start_date": "2026-07-01",
            "end_date": "2026-07-02"
        }
        with patch("routers.sectors.SectorService.get_sector_heatmap", return_value=mock_result):
            response = client.get("/sectors/heatmap?period=24h")

        assert response.status_code == 200
        data = response.json()
        assert "sectors" in data
        assert data["period"] == "24h"
        assert data["total_sectors"] == 1

    def test_returns_500_when_service_raises_exception(self):
        with patch("routers.sectors.SectorService.get_sector_heatmap", side_effect=Exception("DB error")):
            response = client.get("/sectors/heatmap?period=24h")

        assert response.status_code == 500
        assert "DB error" in response.text or "\u83b7\u53d6\u70ed\u529b\u56fe" in response.text

    def test_validates_period_parameter(self):
        response = client.get("/sectors/heatmap?period=invalid")
        assert response.status_code == 422


class TestSectorStocksEndpoint:

    def test_returns_200_with_correct_structure(self):
        mock_result = {
            "sector_name": "\u94f6\u884c",
            "sector_code": "BK001",
            "stocks": [
                {"code": "000001", "name": "\u5e73\u5b89\u94f6\u884c", "change_pct": 1.5,
                 "current_price": 11.0, "first_price": 10.0,
                 "high": 11.2, "low": 9.8, "volume": 100000, "amount": 1100000}
            ],
            "total": 1,
            "page": 1,
            "page_size": 50
        }
        with patch("routers.sectors.SectorService.get_sector_stocks", return_value=mock_result):
            response = client.get("/sectors/%E9%93%B6%E8%A1%8C/stocks")

        assert response.status_code == 200
        data = response.json()
        assert data["sector_name"] == "\u94f6\u884c"
        assert len(data["stocks"]) == 1

    def test_returns_422_when_sector_not_found(self):
        with patch("routers.sectors.SectorService.get_sector_stocks",
                   side_effect=ValueError("板块不存在: 未知")):
            response = client.get("/sectors/%E6%9C%AA%E7%9F%A5/stocks")

        assert response.status_code == 422

    def test_supports_sort_parameters(self):
        mock_result = {
            "sector_name": "\u94f6\u884c", "sector_code": "BK001",
            "stocks": [], "total": 0, "page": 1, "page_size": 50
        }
        with patch("routers.sectors.SectorService.get_sector_stocks", return_value=mock_result) as mock_method:
            client.get("/sectors/%E9%93%B6%E8%A1%8C/stocks?sort_by=volume&sort_order=asc")

        args, _ = mock_method.call_args
        # args: (sector_name, period, start_date, end_date, sort_by, sort_order, page, page_size)
        assert args[4] == "volume"
        assert args[5] == "asc"

    def test_validates_sort_by_parameter(self):
        response = client.get("/sectors/%E9%93%B6%E8%A1%8C/stocks?sort_by=invalid")
        assert response.status_code == 422

    def test_validates_sort_order_parameter(self):
        response = client.get("/sectors/%E9%93%B6%E8%A1%8C/stocks?sort_order=invalid")
        assert response.status_code == 422

    def test_validates_page_ge_1(self):
        response = client.get("/sectors/%E9%93%B6%E8%A1%8C/stocks?page=0")
        assert response.status_code == 422

    def test_validates_page_size_le_100(self):
        response = client.get("/sectors/%E9%93%B6%E8%A1%8C/stocks?page_size=101")
        assert response.status_code == 422


class TestRefreshKlineEndpoint:

    def test_returns_200_with_task_id(self):
        response = client.post("/sectors/refresh-kline")
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["task_id"] == "test-task-id"

    def test_returns_500_on_failure(self):
        mock_kline_tasks.update_kline_data.delay.side_effect = Exception("Celery error")
        try:
            response = client.post("/sectors/refresh-kline")
            assert response.status_code == 500
        finally:
            mock_kline_tasks.update_kline_data.delay.side_effect = None


class TestKlineDataEndpoint:

    def test_returns_200_with_correct_structure(self):
        mock_result = {
            "code": "000001", "name": "\u5e73\u5b89\u94f6\u884c", "period": "daily",
            "data": [
                {"date": "2026-07-01", "open": 10.0, "close": 10.5,
                 "high": 10.8, "low": 9.9, "volume": 100000, "amount": 1050000}
            ],
            "total": 1
        }
        with patch("routers.sectors.SectorService.get_kline_data", return_value=mock_result):
            response = client.get("/sectors/kline/000001")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "000001"
        assert data["name"] == "\u5e73\u5b89\u94f6\u884c"
        assert data["total"] == 1

    def test_returns_200_when_no_data(self):
        mock_result = {"code": "000001", "name": "", "period": "daily", "data": [], "total": 0}
        with patch("routers.sectors.SectorService.get_kline_data", return_value=mock_result):
            response = client.get("/sectors/kline/000001")

        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_returns_500_on_unexpected_error(self):
        with patch("routers.sectors.SectorService.get_kline_data",
                   side_effect=Exception("Unexpected")):
            response = client.get("/sectors/kline/000001")

        assert response.status_code == 500

    def test_passes_start_and_end_date(self):
        mock_result = {
            "code": "000001", "name": "\u5e73\u5b89\u94f6\u884c", "period": "daily",
            "data": [], "total": 0
        }
        with patch("routers.sectors.SectorService.get_kline_data", return_value=mock_result) as mock_method:
            client.get("/sectors/kline/000001?start_date=2026-01-01&end_date=2026-06-30")

        mock_method.assert_called_once_with("000001", "2026-01-01", "2026-06-30")
