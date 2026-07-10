"""筹码分布 — 基于 K 线 + 换手率的估算模型

核心算法:
  Chip_s(p) = sum_{t=1..s} [C_t(p) * W(t,s)]

  每日成交均匀分配: C_t(p) = Vol_t * step / (high_t - low_t)
  衰减权重:          W(t,s) = exp(-sum_{k=t+1..s} Turn_k)

参考实现: 通达信/同花顺筹码分布算法，指数衰减，λ=1
"""
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

PRICE_BIN = 0.01
DECAY_LAMBDA = 1.0
WINDOW_DAYS = 250
DEFAULT_AVG_TURNOVER = 0.05


def _turnover_rate(k: Dict, avg_turn: float, avg_vol: float) -> float:
    if k.get("turnover"):
        return float(k["turnover"]) / 100.0
    vol = k.get("volume", 0)
    if avg_vol > 0 and avg_turn > 0:
        return (vol / avg_vol) * avg_turn
    return DEFAULT_AVG_TURNOVER


def compute_chip_distribution(
    klines: List[Dict],
    date_str: str,
    turnover_pct: Optional[float] = None,
) -> Dict[str, Any]:
    if not klines or len(klines) < 5:
        return {"avg_cost": 0, "profit_ratio": 0,
                "concentration_70": 0, "concentration_90": 0,
                "total_chips": 0}

    sorted_k = [k for k in klines if k.get("date", "") <= date_str]
    if len(sorted_k) > WINDOW_DAYS:
        sorted_k = sorted_k[-WINDOW_DAYS:]
    sorted_k.sort(key=lambda x: x["date"])

    avg_vol = sum(k.get("volume", 0) for k in sorted_k) / len(sorted_k) if sorted_k else 0

    if turnover_pct is not None:
        avg_turn = turnover_pct / 100.0
    else:
        avg_turn = DEFAULT_AVG_TURNOVER

    price_min = min(k.get("low", 0) for k in sorted_k)
    price_max = max(k.get("high", 0) for k in sorted_k)
    if price_max <= price_min:
        price_max = price_min + 1.0

    num_bins = int((price_max - price_min) / PRICE_BIN) + 1
    chips = [0.0] * num_bins

    cum_turn = 0.0
    for k in reversed(sorted_k):
        low = k.get("low", 0)
        high = k.get("high", 0)
        vol = k.get("volume", 0)
        if high <= low or vol <= 0:
            cum_turn += _turnover_rate(k, avg_turn, avg_vol)
            continue

        start_idx = max(0, int((low - price_min) / PRICE_BIN))
        end_idx = min(num_bins - 1, int((high - price_min) / PRICE_BIN))
        num_levels = end_idx - start_idx + 1

        if num_levels <= 0:
            cum_turn += _turnover_rate(k, avg_turn, avg_vol)
            continue

        daily_per_bin = vol / num_levels
        decay = DECAY_LAMBDA * cum_turn
        weight = 1.0 / (1.0 + decay)

        for i in range(start_idx, end_idx + 1):
            chips[i] += daily_per_bin * weight

        cum_turn += _turnover_rate(k, avg_turn, avg_vol)

    total = sum(chips)
    if total <= 0:
        return {"avg_cost": 0, "profit_ratio": 0,
                "concentration_70": 0, "concentration_90": 0,
                "total_chips": 0}

    close = sorted_k[-1].get("close", 0) if sorted_k else 0

    weighted_sum = 0.0
    cum_pct = 0.0
    p5, p30, p70, p95 = price_min, price_min, price_max, price_max
    profit_volume = 0.0

    for i in range(num_bins):
        price = price_min + i * PRICE_BIN
        vol_chip = chips[i]
        if vol_chip <= 0:
            continue
        weighted_sum += price * vol_chip
        prev_cum = cum_pct
        cum_pct += vol_chip / total * 100.0

        if prev_cum < 5 and cum_pct >= 5:
            p5 = price
        if prev_cum < 30 and cum_pct >= 30:
            p30 = price
        if prev_cum < 70 and cum_pct >= 70:
            p70 = price
        if prev_cum < 95 and cum_pct >= 95:
            p95 = price
        if price < close:
            profit_volume += vol_chip

    avg_cost = weighted_sum / total if total > 0 else 0
    profit_ratio = (profit_volume / total * 100.0) if total > 0 else 0
    band_70 = p70 - p30
    band_90 = p95 - p5
    concentration_70 = (band_70 / avg_cost * 100.0) if avg_cost > 0 else 0
    concentration_90 = (band_90 / avg_cost * 100.0) if avg_cost > 0 else 0

    return {
        "avg_cost": round(avg_cost, 2),
        "profit_ratio": round(profit_ratio, 1),
        "concentration_70": round(concentration_70, 1),
        "concentration_90": round(concentration_90, 1),
        "total_chips": round(total, 0),
    }
