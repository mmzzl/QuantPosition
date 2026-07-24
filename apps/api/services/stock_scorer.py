import logging
import math
from typing import Dict, Any, Optional, Set, List
from datetime import date, datetime, timezone

from database import get_db

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60
GAIN_WEIGHT = 0.30
QUALITY_WEIGHT = 0.25
MOMENTUM_WEIGHT = 0.25
RISK_WEIGHT = 0.20


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

    def batch_score(self, codes: List[str],
                    name: str = "",
                    date_str: Optional[str] = None) -> Dict[str, float]:
        if date_str is None:
            date_str = date.today().strftime("%Y-%m-%d")

        result = {}
        for code in codes:
            cached = self._cached_score(code)
            if cached:
                result[code] = cached["score"]
                continue

            db = self._get_db()
            klines = list(db.stock_kline.find(
                {"code": code, "date": {"$lte": date_str}}
            ).sort("date", -1).limit(60))

            if not klines:
                result[code] = 0.0
                continue

            indicators = db.stock_indicators.find_one(
                {"code": code},
                sort=[("date", -1)]
            )

            gain = self._gain_score(klines)
            qual = self._quality_score(klines, indicators)
            mom = self._momentum_score(klines)
            risk = self._risk_score(klines)

            unified = (
                gain * GAIN_WEIGHT
                + qual * QUALITY_WEIGHT
                + mom * MOMENTUM_WEIGHT
                + risk * RISK_WEIGHT
            )

            is_st = name and ("ST" in name.upper().replace("*", "") or "退" in name)
            if is_st:
                unified = 0.0

            unified = max(0.0, min(100.0, unified))
            result[code] = round(unified, 2)

            self._save_cached_score(code, unified, {
                "gain": round(gain, 2),
                "quality": round(qual, 2),
                "momentum": round(mom, 2),
                "risk": round(risk, 2),
            })

        return result

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

    def _cached_score(self, code: str) -> Optional[Dict]:
        db = self._get_db()
        doc = db.scorer_score.find_one({"code": code})
        if doc:
            cached_at = doc.get("cached_at")
            if isinstance(cached_at, datetime):
                now = datetime.now(timezone.utc)
                if cached_at.tzinfo is None:
                    cached_at = cached_at.replace(tzinfo=timezone.utc)
                age = (now - cached_at).total_seconds()
                if age < CACHE_TTL_SECONDS:
                    return {
                        "code": doc["code"],
                        "score": doc["score"],
                        "dimensions": doc["dimensions"],
                        "cached_at": cached_at,
                    }
        return None

    def _save_cached_score(self, code: str, score: float, dimensions: dict):
        db = self._get_db()
        doc = {
            "code": code,
            "score": score,
            "dimensions": dimensions,
            "cached_at": datetime.now(timezone.utc),
        }
        db.scorer_score.update_one(
            {"code": code},
            {"$set": doc},
            upsert=True,
        )

    def _gain_score(self, klines: List[Dict]) -> float:
        if not klines or len(klines) < 5:
            return 0.0

        sorted_k = sorted(klines, key=lambda x: x["date"], reverse=True)
        closes = [k["close"] for k in sorted_k[:20]]
        if closes[0] <= 0:
            return 0.0

        decays = [1.0]
        for i in range(1, len(closes)):
            decays.append(decays[-1] * 0.92)
        total_decay = sum(decays)

        weighted_return = 0.0
        for i in range(1, len(closes)):
            if closes[i] > 0:
                daily_return = (closes[0] - closes[i]) / closes[i]
                weighted_return += daily_return * decays[i]

        cumulative = weighted_return / max(total_decay, 0.001)

        if cumulative >= 0:
            raw = 50.0 + min(cumulative, 0.3) / 0.3 * 50.0
        else:
            raw = max(0.0, 50.0 + max(cumulative, -0.3) / 0.3 * 50.0)
        return max(0.0, min(100.0, raw))

    def _risk_score(self, klines: List[Dict]) -> float:
        if not klines or len(klines) < 10:
            return 25.0

        sorted_k = sorted(klines, key=lambda x: x["date"], reverse=True)
        closes = [k["close"] for k in sorted_k[:30]]

        daily_returns = []
        for i in range(1, len(closes)):
            if closes[i] > 0:
                daily_returns.append((closes[i - 1] - closes[i]) / closes[i])

        if not daily_returns:
            return 25.0

        mean = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean) ** 2 for r in daily_returns) / len(daily_returns)
        volatility = math.sqrt(variance)

        max_dd = 0.0
        peak = closes[0]
        for c in closes[1:]:
            if c > peak:
                peak = c
            dd = (peak - c) / max(peak, 0.01)
            if dd > max_dd:
                max_dd = dd

        vol_score = min(100.0, 60.0 / max(volatility, 0.001))
        dd_score = 100.0 * (1.0 - min(max_dd, 0.5) * 2.0)
        raw = vol_score * 0.6 + dd_score * 0.4
        return max(0.0, min(100.0, raw))

    def _momentum_score(self, klines: List[Dict]) -> float:
        if not klines or len(klines) < 20:
            return 25.0

        sorted_k = sorted(klines, key=lambda x: x["date"], reverse=True)
        closes = [k["close"] for k in sorted_k[:30]]

        def ma(values, n):
            return sum(values[:n]) / n if len(values) >= n else sum(values) / len(values)

        ma5 = ma(closes, 5)
        ma10 = ma(closes, 10)
        ma20 = ma(closes, 20)
        ma_trend = 40.0 if (ma5 > ma10 > ma20 and closes[0] > ma5) else (
            20.0 if closes[0] > ma5 else 0.0
        )

        gains = []
        losses = []
        for i in range(1, min(15, len(closes))):
            delta = closes[i - 1] - closes[i]
            if delta > 0:
                gains.append(delta)
            else:
                losses.append(abs(delta))
        avg_gain = sum(gains) / max(len(gains), 1)
        avg_loss = sum(losses) / max(len(losses), 1)
        if avg_gain + avg_loss < 0.0001:
            rsi_val = 50.0
        else:
            rs = avg_gain / max(avg_loss, 0.0001)
            rsi_val = 100.0 - 100.0 / (1.0 + rs)

        rsi_score = max(0.0, min(100.0, rsi_val))
        if 40 <= rsi_val <= 70:
            rsi_score = 80.0 - abs(rsi_val - 55) * 2.0
        elif rsi_val > 70:
            rsi_score = max(10.0, 80.0 - (rsi_val - 70) * 1.0)
        elif rsi_val < 40:
            rsi_score = max(0.0, rsi_val * 1.5)

        macd_score = 0.0
        ema12 = closes[-1]
        ema26 = closes[-1]
        diffs = []
        alpha12 = 2.0 / 13.0
        alpha26 = 2.0 / 27.0
        alpha9 = 2.0 / 10.0
        for c in reversed(closes):
            ema12 = c * alpha12 + ema12 * (1 - alpha12)
            ema26 = c * alpha26 + ema26 * (1 - alpha26)
            diffs.append(ema12 - ema26)
        diff = diffs[-1]
        dea = diffs[-1]
        for d in diffs:
            dea = d * alpha9 + dea * (1 - alpha9)
        macd_bar = 2 * (diff - dea)

        if macd_bar > 0 and diff > 0 and diff > dea:
            macd_score = 60.0
        elif macd_bar > 0:
            macd_score = 40.0
        else:
            macd_score = 20.0

        raw = ma_trend * 0.4 + rsi_score * 0.3 + macd_score * 0.3
        return max(0.0, min(100.0, raw))

    def _quality_score(self, klines: List[Dict], indicators: Optional[Dict] = None) -> float:
        if not klines or len(klines) < 10:
            return 25.0

        sorted_k = sorted(klines, key=lambda x: x["date"], reverse=True)
        turnovers = []
        for k in sorted_k[:20]:
            if k.get("turnover"):
                turnovers.append(float(k["turnover"]))
        if not turnovers:
            volume_ratio = 0.0
            for k in sorted_k[:20]:
                if k.get("volume"):
                    volume_ratio += k["volume"]
            avg_vol = volume_ratio / max(len(sorted_k[:20]), 1)
            turnovers = [min(avg_vol / 1_000_000, 30.0)]

        mean = sum(turnovers) / len(turnovers)
        if len(turnovers) >= 2:
            var = sum((t - mean) ** 2 for t in turnovers) / len(turnovers)
            std = math.sqrt(var)
            cv = std / max(mean, 0.001)
        else:
            cv = 0.5

        stability_score = max(0.0, min(100.0, 100.0 * (1.0 - min(cv, 1.5) / 1.5)))

        optimal = 3.0 <= mean <= 18.0
        optimal_score = 80.0 if optimal else (
            50.0 if 1.5 <= mean <= 25.0 else 20.0
        )

        indicator_bonus = 0.0
        if indicators:
            inst = indicators.get("institutional_holding")
            if isinstance(inst, (int, float)) and inst > 30:
                indicator_bonus = 10.0

        raw = stability_score * 0.5 + optimal_score * 0.4 + indicator_bonus * 0.1
        return max(0.0, min(100.0, raw))

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
