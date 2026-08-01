import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
from services.scoring.oversold_bounce import oversold_bounce_score


class TestScoringPerformance:
    def test_single_call_under_5ms(self):
        start = time.perf_counter()
        for _ in range(100):
            oversold_bounce_score(
                close=10.0, ma5=10.204, ma10=9.8, ma20=9.5, ma60=9.0,
                volume=800_000, ma5_vol=100_000_000,
                high20=10.5, amplitude=0.04, is_st=False,
                capital_flow_status="inflow",
                has_big_drop=False, has_chip_support=True, has_capital_outflow=False,
            )
        elapsed_ms = (time.perf_counter() - start) / 100 * 1000
        assert elapsed_ms < 5.0, f"单次 {elapsed_ms:.2f}ms 超过 5ms 阈值"

    def test_bulk_scoring_5000_under_30s(self):
        kwargs = dict(
            close=10.0, ma5=10.204, ma10=9.8, ma20=9.5, ma60=9.0,
            volume=800_000, ma5_vol=100_000_000,
            high20=10.5, amplitude=0.04, is_st=False,
        )
        start = time.perf_counter()
        for _ in range(5000):
            oversold_bounce_score(**kwargs)
        elapsed = time.perf_counter() - start
        assert elapsed < 30.0, f"5000 次 {elapsed:.1f}s 超过 30s 阈值"

    def test_score_detail_call_under_10ms(self):
        from services.scoring.oversold_bounce import score_detail
        start = time.perf_counter()
        for _ in range(100):
            score_detail(
                close=10.0, ma5=10.204, ma10=9.8, ma20=9.5, ma60=9.0,
                volume=800_000, ma5_vol=100_000_000,
                high20=10.5, amplitude=0.04, is_st=False,
            )
        elapsed_ms = (time.perf_counter() - start) / 100 * 1000
        assert elapsed_ms < 10.0, f"score_detail 单次 {elapsed_ms:.2f}ms 超过 10ms 阈值"