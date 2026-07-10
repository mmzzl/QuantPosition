import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services.scorer.price_volume import score_price_volume


def _klines(closes, volumes):
    """Build kline list. Index 0 = today (most recent), index N = N days ago."""
    dates = [f"2026-07-{10-i:02d}" for i in range(len(closes))]
    highs = [c * 1.02 for c in closes]
    lows = [c * 0.98 for c in closes]
    return [
        {"close": c, "volume": v, "high": h, "low": l, "date": d}
        for c, v, h, l, d in zip(closes, volumes, highs, lows, dates)
    ]


def test_empty_klines():
    result = score_price_volume([], "2026-07-10")
    assert result["total"] == 0


def test_ma_bullish_and_above_ma5():
    klines = _klines(
        closes=[11, 10.5, 10, 9.5, 9, 8.5, 8, 7.5, 7, 6.5, 6, 5.5, 5, 4.5, 4, 3.5, 3, 2.5, 2, 1.5],
        volumes=[100]*20,
    )
    result = score_price_volume(klines, "2026-07-10")
    assert result["breakdown"]["ma_trend"] == 15


def test_volume_price_healthy():
    klines = _klines(
        closes=[12, 11.5, 11, 10.5, 10, 9.5, 9, 8.5],
        volumes=[200, 150, 80, 180, 200, 220, 100, 90],
    )
    result = score_price_volume(klines, "2026-07-10")
    assert result["breakdown"]["volume_price"] == 12


def test_breakthrough_20day_high():
    closes = [12] + [10]*19
    volumes = [100]*20
    klines = _klines(closes, volumes)
    result = score_price_volume(klines, "2026-07-10")
    assert result["breakdown"]["breakthrough"] == 8


def test_breakthrough_10day_high_only():
    closes = [12] + [11]*9 + [13]*10
    volumes = [100]*20
    klines = _klines(closes, volumes)
    result = score_price_volume(klines, "2026-07-10")
    assert result["breakdown"]["breakthrough"] == 4


def test_amplitude_moderate():
    klines = _klines(closes=[10]*20, volumes=[100]*20)
    result = score_price_volume(klines, "2026-07-10")
    assert result["breakdown"]["amplitude"] == 5


def test_penalty_below_ma20():
    closes = [5] + [10]*19
    volumes = [100]*20
    klines = _klines(closes, volumes)
    result = score_price_volume(klines, "2026-07-10")
    assert result["total"] == 0


def test_penalty_consecutive_drop():
    closes_full = [8.5, 9.5, 10.5] + [10]*17
    volumes_full = [800, 800, 800] + [100]*17
    klines = _klines(closes_full, volumes_full)
    result = score_price_volume(klines, "2026-07-10")
    assert result["total"] == 0


def test_penalty_high_position_stagnation():
    closes = [10, 9.98] + [7]*18
    volumes = [300] + [100]*19
    klines = _klines(closes, volumes)
    result = score_price_volume(klines, "2026-07-10")
    assert result["total"] == 0


def test_full_score_conditions():
    closes = []
    c = 14.86
    for i in range(20):
        closes.append(round(c, 2))
        c = c / 1.02
    volumes = [250, 80, 80, 230, 220] + [150]*15
    klines = _klines(closes, volumes)
    result = score_price_volume(klines, "2026-07-10")
    assert result["total"] >= 30


def test_amplitude_too_low():
    klines = _klines(closes=[10]*20, volumes=[100]*20)
    for k in klines:
        k["high"] = k["close"] * 1.005
        k["low"] = k["close"] * 0.995
    result = score_price_volume(klines, "2026-07-10")
    assert result["breakdown"]["amplitude"] == 0


def test_volume_retracement_not_shrinking():
    closes = [12, 11.5, 11, 10.5, 10]
    volumes = [200, 200, 200, 200, 100]
    klines = _klines(closes, volumes)
    result = score_price_volume(klines, "2026-07-10")
    assert result["breakdown"]["volume_price"] < 12


def test_full_score_breakdown_keys():
    klines = _klines([10]*20, [100]*20)
    result = score_price_volume(klines, "2026-07-10")
    assert "total" in result
    assert "breakdown" in result
    for key in ("ma_trend", "volume_price", "breakthrough", "amplitude"):
        assert key in result["breakdown"]
