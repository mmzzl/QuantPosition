import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from datetime import datetime
import pytest
from unittest.mock import patch, MagicMock
from services.review_service import ReviewService


def make_daily_kline(dates, closes, volumes=None):
    vols = volumes if volumes else [100000] * len(closes)
    klines = []
    for i, (d, c) in enumerate(zip(dates, closes)):
        open_p = closes[i - 1] if i > 0 else c
        klines.append({
            "date": d, "open": open_p, "close": c,
            "high": max(open_p, c) * 1.02, "low": min(open_p, c) * 0.98,
            "volume": vols[i] if i < len(vols) else 100000
        })
    return klines


def make_bar(t, o, c, v):
    return {"date": f"2026-07-04 {t}", "open": o, "close": c,
            "high": max(o, c) * 1.01, "low": min(o, c) * 0.99,
            "volume": v, "amount": v * c}


class TestVWAPAnalysis:
    def test_vwap_returns_dict_with_status_and_vwap(self):
        times = [f"{h:02d}:{m:02d}" for h in range(9, 15) for m in [35, 40, 45, 50, 55]]
        bars = [make_bar(t, 10.0, 10.05, 10000) for t in times]
        status, vwap = ReviewService._analyze_vwap(bars)
        assert isinstance(status, str)
        assert isinstance(vwap, float)

    def test_vwap_empty_bars_returns_oscillate(self):
        status, vwap = ReviewService._analyze_vwap([])
        assert status == "震荡"
        assert vwap == 0


class TestMainForce4Layer:
    def test_4layer_verification_bars_insufficient(self):
        result = ReviewService._4layer_verification("000001")
        assert isinstance(result, dict)

    @patch("services.review_service.ReviewService._get_daily_klines")
    @patch("services.review_service.ReviewService._get_5m_klines")
    def test_4layer_verification_with_data(self, mock_5m, mock_daily):
        mock_daily.return_value = make_daily_kline(
            [f"2026-07-{i+1:02d}" for i in range(20)],
            [10.0 + i * 0.05 for i in range(20)]
        )
        mock_5m.return_value = [make_bar("09:35", 10.0, 10.05, 10000)]
        result = ReviewService._4layer_verification("000001")
        assert "intention" in result
        assert "intention_confidence" in result


class TestGenerateReview:
    @patch("database.get_db")
    @patch("services.review_service.ReviewService.analyze")
    def test_generate_review_returns_report_dict(self, mock_analyze, mock_get_db):
        mock_db = MagicMock()
        mock_db.holdings.find.return_value = [
            {"code": "000001", "name": "平安银行"}
        ]
        mock_db.alert_log.find.return_value = []
        mock_get_db.return_value = mock_db

        mock_analyze.return_value = {
            "code": "000001", "name": "平安银行", "date": "2026-07-17",
            "total_score": 70, "grade": "A",
            "conclusion": "持有", "pattern": "U型洗盘分时",
            "main_force_intention": "吸筹", "intention_detail": "低位吸筹",
            "strategy": "中线持有", "position": "低位",
            "vwap_status": "强势", "volume_signal": "洗盘",
            "tail_signal": "抢筹", "volume_detail": "",
            "daily_vol_pattern": "", "daily_patterns": [],
        }

        report = ReviewService.generate_review("2026-07-17")
        assert isinstance(report, dict)
        assert report["date"] == "2026-07-17"
        assert "summary" in report
        assert "top_stocks" in report
        assert "sector_analysis" in report


class TestReviewServiceRun:
    def test_review_spider_run_exists(self):
        from bin.review_spider import run
        assert callable(run)

    def test_review_runner_run_exists(self):
        from bin.review_runner import run
        assert callable(run)

    def test_review_picker_run_exists(self):
        from bin.review_picker import run
        assert callable(run)
