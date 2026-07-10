import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from unittest.mock import patch
import pandas as pd
from services.scorer.fund_chip import score_fund_chip, clear_cache


def setup_function():
    clear_cache()


def _mock_fund_flow_df(code="000001", net_amount=100_000_000):
    amount_str = f"{net_amount / 1e8:.2f}亿" if net_amount >= 1e8 else f"{net_amount / 1e4:.0f}万"
    data = {"股票代码": [int(code)], "股票简称": ["TestStock"], "最新价": [10.0],
            "阶段涨跌幅": ["2.50%"], "连续换手率": ["8.00%"], "资金流入净额": [amount_str]}
    return pd.DataFrame(data)


def _mock_lhb_df(code="000001"):
    data = {"股票代码": [code], "股票名称": ["TestStock"], "收盘价": [10.0],
            "对应值(%)": [2.5], "成交量(万股)": [100], "成交额(万元)": [5000], "指标": ["有价格涨跌幅限制的日收盘价格涨幅偏离值达到7%的前三只证券"]}
    return pd.DataFrame(data)


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


def test_fund_flow_strong():
    with patch("services.scorer.fund_chip.akshare") as mock_ak:
        mock_ak.stock_fund_flow_individual.return_value = _mock_fund_flow_df("000001", 500_000_000)
        mock_ak.stock_lhb_detail_daily_sina.return_value = _mock_lhb_df("000001")
        result = score_fund_chip("000001", "2026-07-10",
                                  klines=_mock_klines(10.0), turnover_pct=8.0)
    assert result["breakdown"]["fund_flow"] == 12
    assert result["breakdown"]["lhb"] == 10
    assert result["breakdown"]["chip"] == 8  # concentrated (low 90% band)
    assert result["breakdown"]["turnover"] == 5
    assert result["total"] == 35


def test_fund_flow_negative():
    with patch("services.scorer.fund_chip.akshare") as mock_ak:
        mock_ak.stock_fund_flow_individual.return_value = _mock_fund_flow_df("000001", -50_000_000)
        mock_ak.stock_lhb_detail_daily_sina.return_value = _mock_lhb_df("999999")
        result = score_fund_chip("000001", "2026-07-10",
                                  klines=_mock_klines(20.0), turnover_pct=2.0)
    assert result["breakdown"]["fund_flow"] == 0
    assert result["breakdown"]["lhb"] == 5  # not on LHB → neutral
    assert result["breakdown"]["chip"] == 8  # computed from klines
    assert result["breakdown"]["turnover"] == 0
    assert result["total"] == 13


def test_akshare_api_error():
    with patch("services.scorer.fund_chip.akshare") as mock_ak:
        mock_ak.stock_fund_flow_individual.side_effect = Exception("API error")
        mock_ak.stock_lhb_detail_daily_sina.side_effect = Exception("API error")
        result = score_fund_chip("000001", "2026-07-10",
                                  klines=_mock_klines(15.0), turnover_pct=10.0)
    assert result["breakdown"]["fund_flow"] == 0
    assert result["breakdown"]["lhb"] == 5  # neutral fallback
    assert result["breakdown"]["chip"] == 8  # still computed from klines
    assert result["breakdown"]["turnover"] == 5
    assert result["total"] == 18


def test_fund_flow_not_in_rank():
    """When code not found in the ranking df, fund_flow = 0"""
    with patch("services.scorer.fund_chip.akshare") as mock_ak:
        mock_ak.stock_fund_flow_individual.return_value = _mock_fund_flow_df("999999", 100_000_000)
        mock_ak.stock_lhb_detail_daily_sina.return_value = pd.DataFrame()
        result = score_fund_chip("000001", "2026-07-10",
                                  klines=_mock_klines(10.0), turnover_pct=6.0)
    assert result["breakdown"]["fund_flow"] == 0  # code 000001 not in 999999 df
    assert result["breakdown"]["lhb"] == 5  # neutral


def test_penalty_continuous_outflow():
    with patch("services.scorer.fund_chip.akshare") as mock_ak:
        mock_ak.stock_fund_flow_individual.return_value = _mock_fund_flow_df("000001", -200_000_000)
        mock_ak.stock_lhb_detail_daily_sina.return_value = _mock_lhb_df("000001")
        result = score_fund_chip("000001", "2026-07-10",
                                  klines=_mock_klines(10.0), turnover_pct=8.0)
    assert result["total"] == 0


def test_cache_hit():
    clear_cache()
    with patch("services.scorer.fund_chip.akshare") as mock_ak:
        mock_ak.stock_fund_flow_individual.return_value = _mock_fund_flow_df("000001", 100_000_000)
        mock_ak.stock_lhb_detail_daily_sina.return_value = _mock_lhb_df("000001")
        _ = score_fund_chip("000001", "2026-07-10",
                             klines=_mock_klines(10.0), turnover_pct=8.0)
        call_count = mock_ak.stock_fund_flow_individual.call_count
        _ = score_fund_chip("000001", "2026-07-10",
                             klines=_mock_klines(10.0), turnover_pct=8.0)
        assert mock_ak.stock_fund_flow_individual.call_count == call_count
