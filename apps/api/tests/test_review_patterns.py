import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
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


class TestWBottomPattern:
    def test_w_bottom_detected(self):
        lows = [10.5, 10.3, 9.8, 9.7, 9.8, 10.0, 9.9, 9.8, 9.7, 9.9, 10.1, 10.2, 10.3, 10.4, 10.5]
        closes = [10.6, 10.4, 9.9, 9.8, 9.9, 10.1, 10.0, 9.9, 9.8, 10.0, 10.2, 10.3, 10.4, 10.5, 10.6]
        klines = []
        for i in range(15):
            klines.append({
                "date": f"2026-07-{i+1:02d}",
                "open": closes[i], "close": closes[i],
                "high": closes[i] * 1.02, "low": lows[i],
                "volume": 100000
            })
        patterns = ReviewService._detect_kline_pattern(klines)
        assert "W底" in patterns

    def test_w_bottom_not_detected_flat(self):
        klines = make_daily_kline(
            [f"2026-07-{i+1:02d}" for i in range(15)],
            [10.0] * 15
        )
        patterns = ReviewService._detect_kline_pattern(klines)
        assert "W底" not in patterns

    def test_w_bottom_insufficient_data(self):
        klines = make_daily_kline(
            [f"2026-07-{i+1:02d}" for i in range(5)],
            [10.0, 9.8, 9.7, 9.8, 10.0]
        )
        patterns = ReviewService._detect_kline_pattern(klines)
        assert patterns == []


class TestFalseBreakPattern:
    def test_false_break_detected(self):
        dates = [f"2026-07-{i+1:02d}" for i in range(15)]
        closes = [10.0 + i * 0.05 for i in range(15)]
        klines = make_daily_kline(dates, closes)
        klines[-3] = {**klines[-3], "close": 11.0}
        klines[-2] = {**klines[-2], "close": 10.5}
        klines[-1] = {**klines[-1], "close": 10.95}
        patterns = ReviewService._detect_kline_pattern(klines)
        assert "假破位" in patterns


class TestVolumePriceAnalysis:
    def test_volume_price_analysis_short_data(self):
        times = [f"{h:02d}:{m:02d}" for h in [9] for m in [35, 40]]
        bars = [make_bar(t, 10.0, 10.05, 10000) for t in times]
        signal, detail = ReviewService._analyze_volume(bars)
        assert signal == "震荡"

    def test_volume_price_analysis_distribution_signal(self):
        times = [f"{h:02d}:{m:02d}" for h in range(9, 15) for m in [35, 40, 45, 50, 55]]
        bars = []
        for i, t in enumerate(times):
            if i < 3:
                bars.append(make_bar(t, 10.0, 10.05, 80000))
            elif i < 6:
                bars.append(make_bar(t, 10.05, 10.08, 90000))
            else:
                bars.append(make_bar(t, 10.0, 9.8, 60000))
        signal, detail = ReviewService._analyze_volume(bars)
        assert isinstance(signal, str)
        assert isinstance(detail, str)


class TestConsecutivePatterns:
    def test_consecutive_yang_volume_increasing(self):
        dates = [f"2026-07-{i+1:02d}" for i in range(6)]
        closes = [10.0, 10.2, 10.5, 10.8, 11.2, 11.6]
        vols = [50000, 70000, 100000, 120000, 150000, 180000]
        klines = make_daily_kline(dates, closes, vols)
        seq = ReviewService._detect_sequence(klines)
        assert "量价齐升" in seq

    def test_high_level_stagnation(self):
        dates = [f"2026-07-{i+1:02d}" for i in range(6)]
        closes = [15.0, 15.1, 15.15, 15.05, 15.1, 15.15]
        vols = [100000, 100000, 100000, 350000, 120000, 120000]
        klines = make_daily_kline(dates, closes, vols)
        seq = ReviewService._detect_sequence(klines)
        assert "高位放量滞涨" in seq


class TestPositionDeterminationEdge:
    def test_less_than_5_klines_returns_mid(self):
        klines = make_daily_kline(
            [f"2026-07-{i+1:02d}" for i in range(3)],
            [10.0, 10.5, 11.0]
        )
        assert ReviewService._determine_position(klines) == "中段"
