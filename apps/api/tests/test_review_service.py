import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from unittest.mock import patch
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


class TestDailyVolumeTrend:
    def test_accumulation_volume_pattern(self):
        klines = []
        for i in range(20):
            down = i % 2 == 0
            vol = 30000 if down else 150000
            if i in (7, 13):
                vol = 350000
            klines.append({
                "date": f"2026-06-{i+1:02d}",
                "open": 10.0 + i * 0.05 + (0.1 if down else 0),
                "close": 10.0 + i * 0.05,
                "high": 10.0 + i * 0.05 + 0.3,
                "low": 10.0 + i * 0.05 - 0.1,
                "volume": vol
            })
        result = ReviewService._analyze_daily_volume_trend(klines)
        assert result["pattern"] == "\u5438\u7b79\u91cf"

    def test_wash_volume_shrink_on_dips(self):
        klines = []
        for i in range(20):
            vol = 100000 if i < 10 else (20000 + (i - 10) * 5000)
            klines.append({
                "date": f"2026-06-{i+1:02d}",
                "open": 10.0 + i * 0.12,
                "close": 10.0 + i * 0.12 - (0.1 if 10 <= i <= 12 else 0),
                "high": 10.0 + i * 0.12 + 0.2,
                "low": 10.0 + i * 0.12 - 0.2,
                "volume": vol
            })
        result = ReviewService._analyze_daily_volume_trend(klines)
        assert result["pattern"] == "\u6d17\u76d8\u91cf"

    def test_distribution_volume_pattern(self):
        klines = []
        for i in range(20):
            up = i % 2 == 0
            klines.append({
                "date": f"2026-06-{i+1:02d}",
                "open": 15.0 - i * 0.08,
                "close": 15.0 - i * 0.08 - (0.1 if up else 0),
                "high": 15.0 - i * 0.08 + 0.1,
                "low": 15.0 - i * 0.08 - 0.2,
                "volume": 150000 if up else 30000
            })
        result = ReviewService._analyze_daily_volume_trend(klines)
        assert result["pattern"] == "\u51fa\u8d27\u91cf"


class TestDetectSequence:
    def test_limit_up_then_shrink(self):
        dates = [f"2026-07-{i+1:02d}" for i in range(6)]
        closes = [10.0, 10.0, 10.5, 11.55, 11.60, 11.62]
        vols = [100000] * 3 + [300000, 80000, 50000]
        klines = make_daily_kline(dates, closes, vols)
        seq = ReviewService._detect_sequence(klines)
        assert "\u6da8\u505c\u540e\u7f29\u91cf" in seq

    def test_limit_up_then_continuous_up(self):
        dates = [f"2026-07-{i+1:02d}" for i in range(6)]
        closes = [10.0, 10.0, 10.5, 11.55, 12.5, 13.2]
        vols = [100000] * 3 + [300000, 250000, 250000]
        klines = make_daily_kline(dates, closes, vols)
        seq = ReviewService._detect_sequence(klines)
        assert "\u6da8\u505c\u540e\u7ee7\u7eed\u4e0a\u653b" in seq

    def test_consecutive_yin_shrink(self):
        dates = [f"2026-07-{i+1:02d}" for i in range(6)]
        closes = [12.0, 11.8, 11.6, 11.4, 11.35, 11.32]
        vols = [100000, 80000, 60000, 45000, 40000, 38000]
        klines = make_daily_kline(dates, closes, vols)
        seq = ReviewService._detect_sequence(klines)
        assert "\u8fde\u9634\u7f29\u91cf" in seq

    def test_limit_up_volume_not_included_in_post_days(self):
        dates = [f"2026-07-{i+1:02d}" for i in range(6)]
        closes = [10.0, 10.0, 10.5, 11.55, 11.56, 11.55]
        vols = [100000] * 3 + [500000, 30000, 20000]
        klines = make_daily_kline(dates, closes, vols)
        seq = ReviewService._detect_sequence(klines)
        assert "\u6da8\u505c\u540e\u7f29\u91cf" in seq


class TestKlinePatterns:
    def test_hammer_candle(self):
        dates = [f"2026-07-{i+1:02d}" for i in range(15)]
        klines = make_daily_kline(dates, [10.0] * 15)
        klines[-1] = {"date": "2026-07-15", "open": 10.0, "close": 9.95,
                       "high": 10.05, "low": 9.5, "volume": 100000}
        patterns = ReviewService._detect_kline_pattern(klines)
        assert "\u957f\u4e0b\u5f71" in patterns

    def test_w_double_bottom(self):
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
        assert "W\u5e95" in patterns


class TestMainForceIntention:
    def test_accumulation_low_position(self):
        dates = [f"2026-06-{i+1:02d}" for i in range(20)]
        closes = [10.0 + i * 0.08 for i in range(20)]
        vols = [80000 if i % 2 == 0 else 30000 for i in range(20)]
        klines = make_daily_kline(dates, closes, vols)
        mf = ReviewService._assess_main_force_intention(
            position="\u4f4e\u4f4d", daily_klines=klines,
            vwap_status="\u5f3a\u52bf", volume_signal="\u6d17\u76d8",
            pattern="U\u578b\u6d17\u76d8\u5206\u65f6", tail_signal="\u62a2\u7b79"
        )
        assert mf["intention"] in ("\u5438\u7b79",)

    def test_distribution_high_position(self):
        dates = [f"2026-06-{i+1:02d}" for i in range(20)]
        closes = [10.0 * (1 + 0.04 * i) for i in range(20)]
        klines = make_daily_kline(dates, closes)
        mf = ReviewService._assess_main_force_intention(
            position="\u9ad8\u4f4d", daily_klines=klines,
            vwap_status="\u5f31\u52bf", volume_signal="\u51fa\u8d27",
            pattern="M\u5934\u5206\u65f6", tail_signal="\u653e\u91cf\u8df3\u6c34"
        )
        assert mf["intention"] == "\u771f\u51fa\u8d27"

    def test_fake_distribution_mid_recovery(self):
        dates = [f"2026-07-{i+1:02d}" for i in range(15)]
        closes = [10.0 + i * 0.2 for i in range(15)]
        klines = make_daily_kline(dates, closes)
        klines[-3] = {**klines[-3], "close": klines[-4]["close"] * 0.97, "low": klines[-4]["close"] * 0.94}
        klines[-2] = {**klines[-2], "close": klines[-3]["close"] * 0.96, "low": klines[-3]["close"] * 0.94}
        klines[-1] = {**klines[-1], "close": klines[-3]["close"] * 1.03}
        mf = ReviewService._assess_main_force_intention(
            position="\u4e2d\u6bb5", daily_klines=klines,
            vwap_status="\u9707\u8361", volume_signal="\u51fa\u8d27",
            pattern="\u65e9\u76d8\u8109\u51b2\u5168\u5929\u56de\u843d", tail_signal="\u65e0\u91cf\u6a2a\u76d8"
        )
        assert mf["intention"] == "\u5047\u51fa\u8d27\u8bf1\u7a7a"


class TestAnalyzeUnified:

    @patch('database.get_db')
    @patch('services.review_service.ReviewService._get_daily_klines')
    @patch('services.review_service.ReviewService._get_5m_klines')
    def test_analyze_returns_unified_dict(self, mock_get_5m, mock_get_daily, mock_get_db):
        mock_get_daily.return_value = make_daily_kline(
            [f"2026-07-{i+1:02d}" for i in range(20)],
            [10.0 + i * 0.05 for i in range(20)]
        )
        mock_get_5m.return_value = [
            make_bar("09:35", 10.0, 10.05, 10000),
            make_bar("09:40", 10.05, 10.10, 15000),
        ]
        result = ReviewService.analyze("000001", "平安银行", "2026-07-17")

        assert "dimensions" in result
        assert "quantitative_score" in result
        assert "total_score" in result
        assert "grade" in result
