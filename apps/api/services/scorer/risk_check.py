"""极简风控评分 (5分)"""
import logging
from typing import Dict, Any, Set

import akshare

logger = logging.getLogger(__name__)

DELISTING_CODES: Set[str] = set()

_cache: Dict[str, Any] = {}


def clear_cache():
    _cache.clear()


def is_st(name: str) -> bool:
    return "ST" in name or "*ST" in name or "退" in name


def score_risk(code: str, name: str, date_str: str,
               delisting_risk: bool = False) -> Dict[str, Any]:
    breakdown = {"st": 0, "delist": 0, "bad_news": 0}

    # 1. 非ST检测 (+2, otherwise veto)
    if is_st(name):
        return {"total": 0, "veto": True, "breakdown": breakdown}

    breakdown["st"] = 2

    # 2. 无退市预警 (+2, otherwise veto)
    if delisting_risk or code in DELISTING_CODES:
        return {"total": 0, "veto": True, "breakdown": breakdown}

    breakdown["delist"] = 2

    # 3. 当日无解禁/减持公告 (+1, otherwise veto)
    date_compact = date_str.replace("-", "")
    cache_key = f"restricted:{date_compact}"
    bad_news = False
    try:
        if cache_key not in _cache:
            _cache[cache_key] = akshare.stock_restricted_release_detail_em(
                start_date=date_compact, end_date=date_compact)
        df = _cache[cache_key]
        if df is not None and not df.empty:
            match = df[df["股票代码"].astype(str) == code]
            if not match.empty:
                bad_news = True
    except Exception:
        logger.debug("stock_restricted_release_detail_em failed for %s (东方财富接口预期不可用)", date_str)

    breakdown["bad_news"] = 0 if bad_news else 1
    total = sum(breakdown.values())

    return {"total": total, "veto": False, "breakdown": breakdown}
