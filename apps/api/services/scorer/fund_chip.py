# DEPRECATED: replaced by services.scoring.oversold_bounce. Do not use in new code.
"""资金筹码评分 (35→13分) — 仅保留筹码分布 + 换手率，移除 akshare"""
import logging
from typing import Dict, Any, Optional, List

from services.scorer.chip_distribution import compute_chip_distribution

logger = logging.getLogger(__name__)


def score_fund_chip(code: str, date_str: str,
                    klines: Optional[List[Dict]] = None,
                    turnover_pct: Optional[float] = None) -> Dict[str, Any]:
    breakdown = {"chip": 0, "turnover": 0}

    # 筹码集中度 (8pts) — 基于 K 线 + 换手率估算
    if klines:
        chip = compute_chip_distribution(klines, date_str, turnover_pct=turnover_pct)
        conc = chip.get("concentration_90", 999)
        if conc < 15:
            breakdown["chip"] = 8
        elif conc <= 30:
            breakdown["chip"] = 5
        else:
            breakdown["chip"] = 2

    # 换手率 (5pts)
    if turnover_pct is not None:
        if 5 <= turnover_pct <= 18:
            breakdown["turnover"] = 5
        elif (3 <= turnover_pct < 5) or (18 < turnover_pct <= 25):
            breakdown["turnover"] = 3

    total = sum(breakdown.values())
    return {"total": total, "breakdown": breakdown}
