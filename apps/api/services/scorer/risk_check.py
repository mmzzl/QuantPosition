"""极简风控评分 (5分)"""
import logging
from typing import Dict, Any, Set, Optional
from datetime import datetime, timedelta

import requests

logger = logging.getLogger(__name__)

DELISTING_CODES: Set[str] = set()

_cache: Dict[str, Any] = {}

CNINFO_BASE = "http://www.cninfo.com.cn"
_org_map: Optional[Dict[str, str]] = None


def clear_cache():
    _cache.clear()
    global _org_map
    _org_map = None


def _load_org_map():
    global _org_map
    if _org_map is not None:
        return
    _org_map = {}
    try:
        resp = requests.get(
            f"{CNINFO_BASE}/new/data/szse_stock.json",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if resp.ok:
            for s in resp.json().get("stockList", []):
                code = s.get("code", "")
                org_id = s.get("orgId", "")
                if code and org_id:
                    _org_map[code] = org_id
    except Exception:
        logger.warning("Failed to load szse_stock.json from cninfo")


def _check_cninfo_jiejin(code: str, date_str: str) -> bool:
    key = f"jiejin:{code}"
    if key in _cache:
        return _cache[key]

    _load_org_map()
    org_id = _org_map.get(code) if _org_map else None
    if not org_id:
        _cache[key] = False
        return False

    end = date_str.replace("-", "")
    start_dt = datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=30)
    start = start_dt.strftime("%Y-%m-%d")

    try:
        resp = requests.post(
            f"{CNINFO_BASE}/new/hisAnnouncement/query",
            data={
                "pageNum": "1",
                "pageSize": "5",
                "stock": f"{code},{org_id}",
                "searchkey": "\u9650\u552e\u80a1\u4efd\u4e0a\u5e02\u6d41\u901a \u89e3\u7981",
                "seDate": f"{start}~{date_str}",
                "sortName": "announcementTime",
                "sortType": "-1",
                "isHLtitle": "true",
            },
            headers={
                "User-Agent": "Mozilla/5.0",
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=10,
        )
        body = resp.json()
        anns = body.get("announcements")
        result = bool(anns and len(anns) > 0)
    except Exception:
        logger.debug("cninfo jiejin query failed for %s", code)
        result = False

    _cache[key] = result
    return result


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

    # 3. 当日无解禁/减持公告 (+1, otherwise veto) — cninfo 查询
    bad_news = _check_cninfo_jiejin(code, date_str)

    breakdown["bad_news"] = 0 if bad_news else 1
    total = sum(breakdown.values())

    return {"total": total, "veto": False, "breakdown": breakdown}
