import logging
from typing import Dict, Any, Optional
from datetime import date

from database import get_db

logger = logging.getLogger(__name__)


class StockScorer:
    MODE_SHORT = "short"

    def __init__(self, db=None):
        self._db = db

    def _get_db(self):
        if self._db is None:
            self._db = get_db()
        return self._db

    def _is_filtered(self, code: str, name: str) -> bool:
        pure = code.split(".")[-1] if "." in code else code
        if not (pure.isdigit() and len(pure) == 6):
            return True
        if pure.startswith(("300", "688")):
            return True
        if name:
            n = name.upper().replace("*", "")
            if "ST" in n or "退" in name:
                return True
        return False

    def _load_industry_code(self, code: str) -> Optional[str]:
        try:
            from systems.sys import home
            import os
            import pandas as pd
            path = os.path.join(home(), "apps", "api", "data", "stock_industry.csv")
            if os.path.exists(path):
                df = pd.read_csv(path)
                for _, row in df.iterrows():
                    csv_code = str(row.get("code", "")).strip()
                    if code in csv_code:
                        raw = str(row.get("industry", "")).strip()
                        if raw and raw != "证监会行业分类":
                            return raw
            path2 = os.path.join(home(), "apps", "api", "data", "code_to_industry.csv")
            if os.path.exists(path2):
                df2 = pd.read_csv(path2)
                for _, row in df2.iterrows():
                    if str(row.get("code", "")).strip() == code:
                        return str(row.get("industry", "")).strip()
        except Exception as e:
            logger.warning("Failed to load industry for %s: %s", code, e)
        return None

    def _load_turnover(self, code: str, date_str: str) -> Optional[float]:
        try:
            db = self._get_db()
            bars = list(db.stock_kline_5m.find(
                {"code": code, "date": {"$regex": f"^{date_str}"}}
            ).limit(5))
            if bars:
                total_vol = sum(b.get("volume", 0) for b in bars)
                if total_vol > 0:
                    return min(total_vol / 1_0000, 30)
            daily = db.stock_kline.find_one({"code": code, "date": date_str})
            if daily and daily.get("turnover"):
                return float(daily["turnover"])
        except Exception:
            pass
        return None

    def score(self, code: str, name: str = "",
              date_str: Optional[str] = None) -> Dict[str, Any]:
        if date_str is None:
            date_str = date.today().strftime("%Y-%m-%d")

        if self._is_filtered(code, name):
            return {"code": code, "name": name, "date": date_str,
                    "total": 0, "level": "C",
                    "breakdown": {"price_volume": {}, "fund_chip": {},
                                  "sector_theme": {}, "risk": {}}}

        db = self._get_db()
        klines = list(db.stock_kline.find(
            {"code": code, "date": {"$lte": date_str}}
        ).sort("date", -1).limit(60))

        industry_code = self._load_industry_code(code)
        turnover_pct = self._load_turnover(code, date_str)

        from services.scorer.price_volume import score_price_volume
        from services.scorer.fund_chip import score_fund_chip
        from services.scorer.sector_theme import score_sector_theme
        from services.scorer.risk_check import score_risk

        pv = score_price_volume(klines, date_str)
        fc = score_fund_chip(code, date_str, turnover_pct=turnover_pct)
        st = score_sector_theme(code, date_str, industry_code=industry_code)
        rc = score_risk(code, name, date_str)

        total = pv["total"] + fc["total"] + st["total"] + rc["total"]
        if rc.get("veto") or total == 0:
            total = 0

        if total >= 80:
            level = "S"
        elif total >= 60:
            level = "A"
        elif total >= 40:
            level = "B"
        else:
            level = "C"

        return {
            "code": code, "name": name, "date": date_str,
            "total": total, "level": level,
            "breakdown": {
                "price_volume": pv,
                "fund_chip": fc,
                "sector_theme": st,
                "risk": rc,
            },
        }
