import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from services.scorer.chip_distribution import compute_chip_distribution


def test_concentrated_chip():
    """All klines at same price → high concentration → low 90% band"""
    klines = [
        {"date": f"2026-{(i//30+4):02d}-{(i%30+1):02d}",
         "open": 10.0, "close": 10.0, "high": 10.2, "low": 9.8,
         "volume": 1_000_000}
        for i in range(60)
    ]
    result = compute_chip_distribution(klines, "2026-07-10", turnover_pct=5.0)
    assert result["concentration_90"] < 15
    assert abs(result["avg_cost"] - 10.0) < 0.1


def test_wide_chip():
    """Wide price spread → high 90% band → low score"""
    klines = []
    for i in range(60):
        base = 10.0 + (i % 30) * 1.0  # price oscillates 10-40
        klines.append({
            "date": f"2026-{(i//30+4):02d}-{(i%30+1):02d}",
            "open": base, "close": base, "high": base * 1.05, "low": base * 0.95,
            "volume": 1_000_000,
        })
    result = compute_chip_distribution(klines, "2026-07-10", turnover_pct=5.0)
    assert result["concentration_90"] > 30  # wide spread
    assert result["avg_cost"] > 0


def test_empty_klines():
    result = compute_chip_distribution([], "2026-07-10")
    assert result["total_chips"] == 0


def test_few_klines():
    result = compute_chip_distribution(
        [{"date": "2026-07-01", "open": 10, "close": 10, "high": 10.1, "low": 9.9, "volume": 1000}],
        "2026-07-10")
    assert result["total_chips"] == 0


def test_profit_ratio_high():
    """All chips below close → profit_ratio near 100%"""
    klines = []
    for i in range(30):
        klines.append({
            "date": f"2026-{(i//30+5):02d}-{(i%30+1):02d}",
            "open": 8.0, "close": 8.0, "high": 8.1, "low": 7.9,
            "volume": 1_000_000,
        })
    # close = 10.0 (current day), all chips at 8 → profit_ratio = 100%
    klines.append({
        "date": "2026-07-10",
        "open": 10.0, "close": 10.0, "high": 10.2, "low": 9.8,
        "volume": 500_000,
    })
    result = compute_chip_distribution(klines, "2026-07-10", turnover_pct=5.0)
    assert result["profit_ratio"] > 90


def test_profit_ratio_low():
    """All chips above close → profit_ratio near 0%"""
    klines = []
    for i in range(30):
        klines.append({
            "date": f"2026-{(i//30+5):02d}-{(i%30+1):02d}",
            "open": 12.0, "close": 12.0, "high": 12.1, "low": 11.9,
            "volume": 1_000_000,
        })
    # close = 10.0, all chips at 12 → profit_ratio = 0%
    klines.append({
        "date": "2026-07-10",
        "open": 10.0, "close": 10.0, "high": 10.2, "low": 9.8,
        "volume": 500_000,
    })
    result = compute_chip_distribution(klines, "2026-07-10", turnover_pct=5.0)
    assert result["profit_ratio"] < 5


def test_avg_cost_trend():
    """Recent chips weigh more → avg cost near recent price"""
    klines = []
    # Old chips at 5 (first 10 days)
    for i in range(10):
        klines.append({
            "date": f"2026-04-{i+1:02d}",
            "open": 5.0, "close": 5.0, "high": 5.1, "low": 4.9,
            "volume": 1_000_000,
        })
    # Recent chips at 15 (last 10 days, high volume)
    for i in range(10):
        klines.append({
            "date": f"2026-05-{i+1:02d}",
            "open": 15.0, "close": 15.0, "high": 15.2, "low": 14.8,
            "volume": 5_000_000,
        })
    result = compute_chip_distribution(klines, "2026-05-10", turnover_pct=10.0)
    assert result["avg_cost"] > 10  # weighted toward recent 15
