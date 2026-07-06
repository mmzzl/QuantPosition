import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from services.review_service import ReviewService


def make_daily_kline(dates, closes):
    return [
        {"date": d, "open": c, "close": c, "high": c * 1.05, "low": c * 0.95, "volume": 100000}
        for i, (d, c) in enumerate(zip(dates, closes))
    ]


def make_bar(t, o, c, v):
    return {"date": f"2026-07-04 {t}", "open": o, "close": c,
            "high": max(o, c) * 1.01, "low": min(o, c) * 0.99,
            "volume": v, "amount": v * c}


def gen_times():
    return [f"{h:02d}:{m:02d}" for h in range(9, 15) for m in [35, 40, 45, 50, 55]]


class TestPositionDetermination:
    def test_high_position_stage_gain_over_40(self):
        closes = [10.0 * (1 + 0.03 * i) for i in range(20)]
        klines = make_daily_kline([f"2026-06-0{i+1:02d}" for i in range(20)], closes)
        assert ReviewService._determine_position(klines) == "\u9ad8\u4f4d"

    def test_mid_position_stage_gain_10_30(self):
        closes = [10.0 * (1 + 0.01 * i) for i in range(20)]
        klines = make_daily_kline([f"2026-06-0{i+1:02d}" for i in range(20)], closes)
        assert ReviewService._determine_position(klines) == "\u4e2d\u6bb5"

    def test_low_position_small_gain(self):
        closes = [5.0] * 18 + [5.1, 5.2]
        klines = make_daily_kline([f"2026-06-0{i+1:02d}" for i in range(20)], closes)
        assert ReviewService._determine_position(klines) == "\u4f4e\u4f4d"


class TestVWAPAnalysis:
    def test_strong_vwap_most_bars_above(self):
        times = gen_times()
        bars = [make_bar(t, 10.0, 10.05 if i < 5 else 10.15, 10000) for i, t in enumerate(times)]
        status, _ = ReviewService._analyze_vwap(bars)
        assert status == "\u5f3a\u52bf"

    def test_weak_vwap_most_bars_below(self):
        times = gen_times()
        bars = [make_bar(t, 10.1, 10.05 if i < 5 else 9.95, 10000) for i, t in enumerate(times)]
        status, _ = ReviewService._analyze_vwap(bars)
        assert status == "\u5f31\u52bf"

    def test_balanced_vwap_mixed(self):
        times = gen_times()
        bars = [make_bar(t, 10.0, 10.02 if i % 2 == 0 else 9.98, 10000) for i, t in enumerate(times)]
        status, _ = ReviewService._analyze_vwap(bars)
        assert status == "\u9707\u8361"


class TestVolumeAnalysis:
    def test_distribution_morning_spike_volume_divergence(self):
        times = gen_times()
        bars = []
        for i, t in enumerate(times):
            if i == 0:
                bars.append(make_bar(t, 10.0, 10.03, 80000))
            elif i == 1:
                bars.append(make_bar(t, 10.03, 10.06, 100000))
            elif i == 2:
                bars.append(make_bar(t, 10.06, 10.08, 90000))
            elif i < 5:
                bars.append(make_bar(t, 10.05, 10.0, 6000))
            elif i < 8:
                bars.append(make_bar(t, 10.0, 9.95, 5000))
            else:
                bars.append(make_bar(t, 9.9, 9.85, 25000))
        signal, _ = ReviewService._analyze_volume(bars)
        assert signal == "\u51fa\u8d27"

    def test_suction_down_low_vol_up_high_vol(self):
        times = gen_times()
        bars = []
        for i, t in enumerate(times):
            if i < 8:
                bars.append(make_bar(t, 9.82, 9.8, 3000))
            elif i < 15:
                bars.append(make_bar(t, 9.95, 10.0, 40000))
            else:
                bars.append(make_bar(t, 10.05, 10.1, 35000))
        signal, _ = ReviewService._analyze_volume(bars)
        assert signal == "\u6d17\u76d8"

    def test_probe_early_spike_then_quiet(self):
        times = gen_times()
        bars = []
        for i, t in enumerate(times):
            if i == 5:
                bars.append(make_bar(t, 10.0, 10.5, 60000))
            elif i == 6:
                bars.append(make_bar(t, 10.5, 10.5, 60000))
            else:
                bars.append(make_bar(t, 10.0, 10.0, 5000))
        signal, _ = ReviewService._analyze_volume(bars)
        assert signal == "\u8bd5\u76d8"


class TestPatternRecognition:
    def test_m_top_pattern(self):
        times = gen_times()
        bars = []
        for i, t in enumerate(times):
            if i < 3:
                bars.append(make_bar(t, 10.0, 10.3, 10000))
            elif i < 6:
                bars.append(make_bar(t, 10.25, 10.35, 10000))
            elif i < 10:
                bars.append(make_bar(t, 10.2, 10.0, 10000))
            else:
                bars.append(make_bar(t, 9.9, 9.7, 10000))
        pattern = ReviewService._recognize_pattern(bars, "\u5f31\u52bf", "\u51fa\u8d27")
        assert pattern == "M\u5934\u5206\u65f6"

    def test_u_shape_pattern(self):
        times = gen_times()
        bars = []
        for i, t in enumerate(times):
            if i < 4:
                bars.append(make_bar(t, 10.0, 9.5, 10000))
            elif i < 8:
                bars.append(make_bar(t, 9.6, 10.1, 10000))
            else:
                bars.append(make_bar(t, 10.1, 10.2, 10000))
        pattern = ReviewService._recognize_pattern(bars, "\u5f3a\u52bf", "\u6d17\u76d8")
        assert pattern == "U\u578b\u6d17\u76d8\u5206\u65f6"

    def test_tail_accumulation(self):
        times = gen_times()
        bars = []
        for i, t in enumerate(times):
            if i < 25:
                bars.append(make_bar(t, 10.0, 10.0, 5000))
            else:
                bars.append(make_bar(t, 10.05, 10.15, 40000))
        pattern = ReviewService._recognize_pattern(bars, "\u5f3a\u52bf", "\u6d17\u76d8")
        assert pattern == "\u5c3e\u76d8\u62a2\u7b79\u578b"


class TestConclusion:
    def test_sell_high_weak_distribution(self):
        result = ReviewService._generate_conclusion(
            position="\u9ad8\u4f4d", vwap_status="\u5f31\u52bf",
            volume_signal="\u51fa\u8d27", pattern="M\u5934\u5206\u65f6",
            tail_signal="\u653e\u91cf\u8df3\u6c34"
        )
        assert result["conclusion"] == "\u5356\u51fa"

    def test_hold_mid_strong_suction(self):
        result = ReviewService._generate_conclusion(
            position="\u4e2d\u6bb5", vwap_status="\u5f3a\u52bf",
            volume_signal="\u6d17\u76d8", pattern="U\u578b\u6d17\u76d8\u5206\u65f6",
            tail_signal="\u62a2\u7b79"
        )
        assert result["conclusion"] == "\u6301\u6709"

    def test_watch_balanced(self):
        result = ReviewService._generate_conclusion(
            position="\u4e2d\u6bb5", vwap_status="\u9707\u8361",
            volume_signal="\u9707\u8361", pattern="\u9707\u8361\u5e73\u8861\u5f62\u6001",
            tail_signal="\u65e0\u91cf\u6a2a\u76d8"
        )
        assert result["conclusion"] == "\u89c2\u671b"
