import logging
from typing import Dict, Any, Optional, Set
from datetime import date

from database import get_db

logger = logging.getLogger(__name__)


def _pure_code(code: str) -> str:
    return code.split(".")[-1] if "." in code else code


class StockScorer:
    MODE_SHORT = "short"
    _industry_cache: Optional[Dict[str, str]] = None
    INTENTION_BONUS = {
        "吸筹": 15,
        "洗盘": 10,
        "假出货诱空": 10,
        "高位震荡": 0,
        "出货风险": -50,
        "真出货": -999,
        "震荡": 0,
    }

    def __init__(self, db=None):
        self._db = db

    def _get_db(self):
        if self._db is None:
            self._db = get_db()
        return self._db

    def _is_filtered(self, code: str, name: str) -> bool:
        pure = _pure_code(code)
        if not (pure.isdigit() and len(pure) == 6):
            return True
        if pure.startswith(("300", "688")):
            return True
        if name:
            n = name.upper().replace("*", "")
            if "ST" in n or "退" in name:
                return True
        return False

    @classmethod
    def _load_industry_cache(cls):
        if cls._industry_cache is not None:
            return
        cls._industry_cache = {}
        try:
            from systems.sys import home
            import os
            import pandas as pd
            path = os.path.join(home(), "apps", "api", "data", "stock_industry.csv")
            if os.path.exists(path):
                df = pd.read_csv(path)
                for _, row in df.iterrows():
                    csv_code = str(row.get("code", "")).strip()
                    raw = str(row.get("industry", "")).strip()
                    if raw and raw != "证监会行业分类":
                        pure = _pure_code(csv_code)
                        if pure.isdigit() and len(pure) == 6:
                            cls._industry_cache[pure] = raw
        except Exception as e:
            logger.warning("Failed to load industry cache: %s", e)

    def _load_industry_code(self, code: str) -> Optional[str]:
        self._load_industry_cache()
        pure = _pure_code(code)
        return self._industry_cache.get(pure) if self._industry_cache else None

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
                    "breakdown": {
                        "price_volume": {"total": 0, "breakdown": {}},
                        "fund_chip": {"total": 0, "breakdown": {}},
                        "sector_theme": {"total": 0, "breakdown": {}},
                        "risk": {"total": 0, "breakdown": {}},
                    }}

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
        fc = score_fund_chip(code, date_str, klines=klines, turnover_pct=turnover_pct)
        st = score_sector_theme(code, date_str, industry_code=industry_code)
        rc = score_risk(code, name, date_str)

        total = pv["total"] + fc["total"] + st["total"] + rc["total"]
        if rc.get("veto") or total == 0:
            total = 0

        if total >= 60:
            level = "S"
        elif total >= 45:
            level = "A"
        elif total >= 30:
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

    @staticmethod
    def _calc_grade(total_score: int) -> str:
        if total_score >= 80:
            return "S"
        elif total_score >= 60:
            return "A"
        elif total_score >= 40:
            return "B"
        else:
            return "C"

    @staticmethod
    def _build_dimensions(breakdown: dict) -> dict:
        max_map = {
            "price_volume": 40,
            "fund_chip": 13,
            "sector_theme": 20,
            "risk": 5,
        }
        result = {}
        for key, value in breakdown.items():
            result[key] = {
                "score": value["total"],
                "max": max_map.get(key, 0),
                "detail": value["breakdown"],
            }
        return result

    @classmethod
    def unify(cls, score_result: dict,
              intention_info: Optional[dict] = None,
              conclusion: str = "观望",
              strategy: str = "") -> dict:
        if intention_info is None:
            intention_info = {}

        code = score_result["code"]
        name = score_result["name"]
        date_str = score_result["date"]
        quantitative = score_result["total"]
        quantitative_level = score_result["level"]

        intention = intention_info.get("intention", "")
        bonus = intention_info.get("bonus", 0)
        confidence = intention_info.get("confidence", "")
        detail = intention_info.get("detail", "")

        bonus_clamped = max(bonus, 0)
        total_score = min(100, max(0, quantitative + bonus_clamped))

        if intention == "真出货":
            total_score = 0
            grade = "C"
        else:
            grade = cls._calc_grade(total_score)

        dimensions = cls._build_dimensions(score_result["breakdown"])

        return {
            "code": code,
            "name": name,
            "date": date_str,
            "dimensions": dimensions,
            "quantitative_score": quantitative,
            "quantitative_level": quantitative_level,
            "main_force_intention": intention,
            "intention_bonus": bonus,
            "intention_confidence": confidence,
            "intention_detail": detail,
            "conclusion": conclusion,
            "strategy": strategy,
            "total_score": total_score,
            "grade": grade,
        }
