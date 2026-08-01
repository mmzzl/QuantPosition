# DEPRECATED: replaced by services.scoring.oversold_bounce. Do not use in new code.
"""量价趋势评分 (40分)"""
from typing import List, Dict, Any

VOL_HIGH_THRESHOLD = 1.2
DROP_VOL_THRESHOLD = 1.5
HIGH_POS_VOL_THRESHOLD = 1.3
STAGE_GAIN_THRESHOLD = 0.30
GAIN_TODAY_THRESHOLD = 0.005
DROP_PCT_THRESHOLD = -0.05
AMP_LOW = 0.03
AMP_HIGH = 0.08
AMP_LOW2 = 0.02
AMP_HIGH2 = 0.12


def _penalty_below_ma20(sorted_k, ma20, close):
    return len(sorted_k) >= 3 and ma20 > 0 and close < ma20


def _penalty_consecutive_drop(sorted_k, vol5):
    if len(sorted_k) < 4 or vol5 <= 0:
        return False
    recent_3 = sorted_k[:3]
    total_drop_pct = (recent_3[0]["close"] - recent_3[2]["close"]) / recent_3[2]["close"]
    if total_drop_pct >= DROP_PCT_THRESHOLD:
        return False
    return all(k["volume"] > vol5 * DROP_VOL_THRESHOLD for k in recent_3)


def _penalty_high_position(sorted_k, close, vol5, today):
    if len(sorted_k) < 20 or len(sorted_k) < 2:
        return False
    price_20d_ago = sorted_k[19]["close"]
    if price_20d_ago <= 0:
        return False
    stage_gain = (close - price_20d_ago) / price_20d_ago
    if stage_gain <= STAGE_GAIN_THRESHOLD:
        return False
    if vol5 <= 0 or today["volume"] <= vol5 * HIGH_POS_VOL_THRESHOLD:
        return False
    gain_today = (close - sorted_k[1]["close"]) / sorted_k[1]["close"]
    return gain_today < GAIN_TODAY_THRESHOLD


def _compute_ma(sorted_k, n):
    vals = [k["close"] for k in sorted_k[:n] if k["close"]]
    return sum(vals) / len(vals) if vals else 0


def _compute_vol_avg(sorted_k, n):
    vals = [k["volume"] for k in sorted_k[:n] if k["volume"]]
    return sum(vals) / len(vals) if vals else 0


def score_price_volume(klines: List[Dict], date_str: str) -> Dict[str, Any]:
    if not klines or len(klines) < 5:
        return {
            "total": 0,
            "breakdown": {"ma_trend": 0, "volume_price": 0, "breakthrough": 0, "amplitude": 0},
        }

    sorted_k = sorted(klines, key=lambda x: x["date"], reverse=True)
    today = sorted_k[0]
    close = today["close"]
    ma5 = _compute_ma(sorted_k, 5)
    ma10 = _compute_ma(sorted_k, 10)
    ma20 = _compute_ma(sorted_k, 20)
    vol5 = _compute_vol_avg(sorted_k, 5)

    ma_trend = 0
    if ma5 > ma10 > ma20 and close > ma5:
        ma_trend = 15
    elif close > ma5:
        ma_trend = 5 + (5 if ma5 > ma10 else 0)
    elif close > ma10 and ma10 > ma20:
        ma_trend = 2

    volume_price = 0
    if len(sorted_k) >= 3:
        day3_ago = sorted_k[3]["close"] if len(sorted_k) > 3 else sorted_k[-1]["close"]
        if close > day3_ago:
            volume_price += 4
        if vol5 > 0 and today["volume"] > vol5 * VOL_HIGH_THRESHOLD:
            volume_price += 4
        last_3_closes = [k["close"] for k in sorted_k[:3]]
        if len(last_3_closes) >= 3:
            retracement_volumes = []
            for i in range(1, 3):
                if sorted_k[i]["close"] < sorted_k[i - 1]["close"]:
                    retracement_volumes.append(sorted_k[i]["volume"])
            if retracement_volumes and all(v < vol5 for v in retracement_volumes):
                volume_price += 4

    breakthrough = 0
    high_10 = None
    if len(sorted_k) >= 20:
        high_20 = max(k["close"] for k in sorted_k[:20])
        if close >= high_20:
            breakthrough = 8
    if breakthrough == 0 and len(sorted_k) >= 10:
        if high_10 is None:
            high_10 = max(k["close"] for k in sorted_k[:10])
        if close >= high_10:
            breakthrough = 4

    amplitude = 0
    amp_vals = []
    for k in sorted_k[:5]:
        if k.get("high") and k.get("low") and k["close"]:
            amp = (k["high"] - k["low"]) / k["close"]
            amp_vals.append(amp)
    if amp_vals:
        avg_amp = sum(amp_vals) / len(amp_vals)
        if AMP_LOW <= avg_amp <= AMP_HIGH:
            amplitude = 5
        elif (AMP_LOW2 <= avg_amp < AMP_LOW) or (AMP_HIGH < avg_amp <= AMP_HIGH2):
            amplitude = 3

    total = ma_trend + volume_price + breakthrough + amplitude
    if _penalty_below_ma20(sorted_k, ma20, close):
        total = 0
    elif _penalty_consecutive_drop(sorted_k, vol5):
        total = 0
    elif _penalty_high_position(sorted_k, close, vol5, today):
        total = 0

    return {
        "total": min(total, 40),
        "breakdown": {
            "ma_trend": ma_trend,
            "volume_price": volume_price,
            "breakthrough": breakthrough,
            "amplitude": amplitude,
        },
    }
