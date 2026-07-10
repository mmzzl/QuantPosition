"""资金筹码评分 (35分)"""
import logging
from typing import Dict, Any, Optional

import akshare

logger = logging.getLogger(__name__)

_cache: Dict[str, Any] = {}


def clear_cache():
    _cache.clear()


def _normalize_ak_code(raw: str) -> str:
    return raw.split(".")[0].strip().zfill(6)


def score_fund_chip(code: str, date_str: str, turnover_pct: Optional[float] = None) -> Dict[str, Any]:
    breakdown = {"fund_flow": 0, "lhb": 0, "chip": 0, "turnover": 0}
    net_amount = None

    # 2.1 主力资金净流入 (12pts)
    cache_key_ff = "fund_flow_rank:3日排行"
    try:
        if cache_key_ff not in _cache:
            _cache[cache_key_ff] = akshare.stock_fund_flow_individual("3日排行")
        df_ff = _cache[cache_key_ff]
        if df_ff is not None and not df_ff.empty:
            match = df_ff[df_ff["股票代码"].astype(str).apply(_normalize_ak_code) == code]
            if not match.empty:
                row = match.iloc[0]
                net_amount = float(row["净额"])
                rank = match.index[0] + 1
                if net_amount > 0 and rank <= 500:
                    breakdown["fund_flow"] = 12
                elif net_amount > 0:
                    breakdown["fund_flow"] = 8
    except Exception:
        logger.warning("stock_fund_flow_individual failed for %s", code)

    # 2.2 龙虎榜 (10pts) — Sina source has no net buy column, just check presence
    cache_key_lhb = f"lhb:{date_str}"
    try:
        if cache_key_lhb not in _cache:
            _cache[cache_key_lhb] = akshare.stock_lhb_detail_daily_sina(date_str)
        df_lhb = _cache[cache_key_lhb]
        if df_lhb is not None and not df_lhb.empty:
            match = df_lhb[df_lhb["股票代码"].astype(str).apply(_normalize_ak_code) == code]
            breakdown["lhb"] = 10 if not match.empty else 5
        else:
            breakdown["lhb"] = 5
    except Exception:
        logger.warning("stock_lhb_detail_daily_sina failed for %s", date_str)
        breakdown["lhb"] = 5

    # 2.3 筹码集中度 (8pts)
    cache_key_cyq = f"cyq:{code}"
    try:
        if cache_key_cyq not in _cache:
            _cache[cache_key_cyq] = akshare.stock_cyq_em(code, adjust="qfq")
        df_cyq = _cache[cache_key_cyq]
        if df_cyq is not None and not df_cyq.empty:
            concentration = float(df_cyq.iloc[0]["90集中度"])
            if concentration < 10:
                breakdown["chip"] = 8
            elif concentration <= 20:
                breakdown["chip"] = 5
            else:
                breakdown["chip"] = 2
    except Exception:
        logger.warning("stock_cyq_em failed for %s", code)

    # 2.4 换手率 (5pts)
    if turnover_pct is not None:
        if 5 <= turnover_pct <= 18:
            breakdown["turnover"] = 5
        elif (3 <= turnover_pct < 5) or (18 < turnover_pct <= 25):
            breakdown["turnover"] = 3

    total = sum(breakdown.values())
    if net_amount is not None and net_amount < -100_000_000:
        total = 0

    return {"total": total, "breakdown": breakdown}
