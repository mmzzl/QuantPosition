import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from services.scorer.fund_chip import score_fund_chip


def test_chip_concentrated():
    """Concentrated chip (low 90% band) → 8pts"""
    klines = _mock_klines(10.0)
    result = score_fund_chip("000001", "2026-07-10",
                              klines=klines, turnover_pct=8.0)
    assert result["breakdown"]["chip"] == 8
    assert result["breakdown"]["turnover"] == 5
    assert result["total"] == 13


def test_chip_wide():
    """Wide chip distribution → 2pts"""
    klines = _mock_klines_oscillate()
    result = score_fund_chip("000001", "2026-07-10",
                              klines=klines, turnover_pct=8.0)
    assert result["breakdown"]["chip"] == 2
    assert result["breakdown"]["turnover"] == 5
    assert result["total"] == 7


def test_no_klines():
    """No klines → chip = 0"""
    result = score_fund_chip("000001", "2026-07-10",
                              klines=[], turnover_pct=5.0)
    assert result["breakdown"]["chip"] == 0
    assert result["breakdown"]["turnover"] == 5
    assert result["total"] == 5


def test_turnover_too_high():
    """Turnover too high → 3pts"""
    result = score_fund_chip("000001", "2026-07-10",
                              klines=_mock_klines(10.0), turnover_pct=22.0)
    assert result["breakdown"]["turnover"] == 3
    assert result["total"] == 11  # 8 (chip) + 3 (turnover)


def test_turnover_too_low():
    """Turnover too low → 0pts"""
    result = score_fund_chip("000001", "2026-07-10",
                              klines=_mock_klines(10.0), turnover_pct=1.0)
    assert result["breakdown"]["turnover"] == 0
    assert result["total"] == 8


def _mock_klines(price=10.0, days=60):
    klines = []
    for i in range(days):
        d = f"2026-{(i//30+4):02d}-{(i%30+1):02d}"
        klines.append({
            "date": d, "open": price, "close": price,
            "high": price * 1.02, "low": price * 0.98,
            "volume": 1_000_000,
        })
    return klines


def _mock_klines_oscillate(days=60):
    klines = []
    for i in range(days):
        base = 10.0 + (i % 30) * 1.0
        d = f"2026-{(i//30+4):02d}-{(i%30+1):02d}"
        klines.append({
            "date": d, "open": base, "close": base,
            "high": base * 1.05, "low": base * 0.95,
            "volume": 1_000_000,
        })
    return klines
