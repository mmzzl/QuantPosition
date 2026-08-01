import logging
import math

logger = logging.getLogger(__name__)

# Risk elimination result codes
RISK_OK = 0        # pass risk elimination
RISK_ELIMINATED = -1  # strategy rejection: ST / close<2 / 日均成交额<5000万 / close=0 or volume=0
RISK_MISSING_DATA = -2  # data missing: ma5/ma5_vol None or NaN â skip, return 0

# 近5日日均成交额下限（元）。低于此值视为低流动性剔除 (spec Scenario 4: 日均成交额 < 5000万)
MIN_AVG_TURNOVER = 50_000_000
# volume 单位为手（1手=100股），成交额 = 日均量(手) × 100 × 收盘价
SHARES_PER_LOT = 100


def _is_missing(v) -> bool:
    """True if value is missing: None or NaN."""
    if v is None:
        return True
    try:
        if isinstance(v, float) and math.isnan(v):
            return True
    except TypeError:
        return True
    return False


def _layer1_risk_elimination(ind: dict, is_st: bool = False) -> int:
    if is_st:
        return RISK_ELIMINATED
    close = ind.get("close", 0)
    if _is_missing(close):
        return RISK_MISSING_DATA
    if close <= 0:
        # close=0 -> suspension, treat as un-tradable (spec section 3 exception table)
        return RISK_ELIMINATED
    if close < 2.0:
        return RISK_ELIMINATED

    ma5 = ind.get("ma5")
    if _is_missing(ma5):
        return RISK_MISSING_DATA
    if ma5 <= 0:
        return RISK_ELIMINATED

    volume = ind.get("volume")
    if _is_missing(volume):
        return RISK_MISSING_DATA
    if volume <= 0:
        # volume=0 -> suspension, treat as un-tradable (spec section 3 exception table)
        return RISK_ELIMINATED

    ma5_vol = ind.get("ma5_vol")
    if _is_missing(ma5_vol):
        return RISK_MISSING_DATA
    # ma5_vol 单位为手，换算成近5日日均成交额（元）= 手数 × 100股 × 收盘价
    # spec: 低流动性（近5日日均成交额 < 5000万）→ 直接跳过
    if ma5_vol * SHARES_PER_LOT * close < MIN_AVG_TURNOVER:
        return RISK_ELIMINATED
    return RISK_OK


def _layer2_bias5_score(close: float, ma5: float, volume: float, ma5_vol: float) -> float:
    if _is_missing(close) or _is_missing(ma5) or _is_missing(volume) or _is_missing(ma5_vol):
        return 0.0
    if ma5 <= 0:
        return 0.0
    bias5 = (close - ma5) / ma5
    if bias5 <= -0.03 or bias5 > -0.02 + 1e-9:
        return 0.0
    score = (bias5 + 0.03) / 0.01 * 50
    if volume <= 0:
        score *= 0.8
    elif volume < ma5_vol:
        score *= 1.2
    elif volume > ma5_vol:
        score *= 0.8
    return round(min(score, 50.0), 6)


def _layer3_trend_score(close: float, ma20: float, ma60: float) -> float:
    if _is_missing(close) or _is_missing(ma20) or _is_missing(ma60):
        return 0.0
    if ma20 <= 0:
        return 0.0
    score = 0.0
    if close > ma20:
        score += 15.0
    if abs(close - ma20) / ma20 <= 0.01:
        score += 10.0
    if close > ma20 and close > ma60:
        score += 5.0
    return min(score, 25.0)


def _layer4_sector_score(capital_flow_status: str = None) -> float:
    if capital_flow_status is None:
        return 5.0
    if capital_flow_status == "inflow":
        return 15.0
    if capital_flow_status == "outflow":
        return 0.0
    return 5.0


def _layer5_sentiment_score(
    has_big_drop: bool = False,
    has_chip_support: bool = False,
    has_capital_outflow: bool = False,
    chip_data_available: bool = True,
    capital_data_available: bool = True,
) -> float:
    score = 0.0
    if not has_big_drop:
        score += 4.0
    if chip_data_available and has_chip_support:
        score += 3.0
    if capital_data_available and not has_capital_outflow:
        score += 3.0
    return min(score, 10.0)


def oversold_bounce_score(
    close: float, ma5: float, ma10: float, ma20: float, ma60: float,
    volume: float, ma5_vol: float, high20: float, amplitude: float,
    is_st: bool = False,
    capital_flow_status: str = None,
    has_big_drop: bool = False,
    has_chip_support: bool = False,
    has_capital_outflow: bool = False,
    chip_data_available: bool = True,
    capital_data_available: bool = True,
) -> float:
    ind = {
        "close": close, "ma5": ma5, "ma10": ma10,
        "ma20": ma20, "ma60": ma60,
        "volume": volume, "ma5_vol": ma5_vol,
        "high20": high20, "amplitude": amplitude,
    }
    risk = _layer1_risk_elimination(ind, is_st=is_st)
    if risk == RISK_ELIMINATED:
        return -1.0
    if risk == RISK_MISSING_DATA:
        # data missing: not eliminated, but every subsequent layer also gets 0
        return 0.0
    l2 = _layer2_bias5_score(close, ma5, volume, ma5_vol)
    if l2 <= 0:
        return 0.0
    l3 = _layer3_trend_score(close, ma20, ma60)
    l4 = _layer4_sector_score(capital_flow_status)
    l5 = _layer5_sentiment_score(
        has_big_drop, has_chip_support, has_capital_outflow,
        chip_data_available, capital_data_available,
    )
    total = l2 + l3 + l4 + l5
    return min(total, 100.0)


def score_detail(
    close: float, ma5: float, ma10: float, ma20: float, ma60: float,
    volume: float, ma5_vol: float, high20: float, amplitude: float,
    is_st: bool = False,
    capital_flow_status: str = None,
    has_big_drop: bool = False,
    has_chip_support: bool = False,
    has_capital_outflow: bool = False,
    chip_data_available: bool = True,
    capital_data_available: bool = True,
) -> dict:
    ind = {
        "close": close, "ma5": ma5, "ma10": ma10,
        "ma20": ma20, "ma60": ma60,
        "volume": volume, "ma5_vol": ma5_vol,
        "high20": high20, "amplitude": amplitude,
    }
    risk = _layer1_risk_elimination(ind, is_st=is_st)
    l2 = _layer2_bias5_score(close, ma5, volume, ma5_vol)
    l3 = _layer3_trend_score(close, ma20, ma60)
    l4 = _layer4_sector_score(capital_flow_status)
    l5 = _layer5_sentiment_score(
        has_big_drop, has_chip_support, has_capital_outflow,
        chip_data_available, capital_data_available,
    )
    total = min(l2 + l3 + l4 + l5, 100.0)
    return {
        "total": round(total, 1) if risk != RISK_ELIMINATED else 0.0,
        "risk_eliminated": risk == RISK_ELIMINATED,
        "risk_missing_data": risk == RISK_MISSING_DATA,
        "bias5": round(l2, 1),
        "trend": round(l3, 1),
        "sector": round(l4, 1),
        "sentiment": round(l5, 1),
    }
