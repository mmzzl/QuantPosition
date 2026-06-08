# -*- coding: utf-8 -*-
"""指标预计算：每天盘后计算全市场股票技术指标存入 stock_indicators 集合

支持两种运行模式：
  1. python bin/indicator_calculator.py        # 每日增量更新（只有今天有数据的股票）
  2. python bin/indicator_calculator.py backfill  # 一次性回填所有历史数据
"""
import sys
import os
import logging
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db
from bin.rule_engine import calc_sma, calc_rsi, calc_atr, calc_adx
from pymongo import UpdateOne

logger = logging.getLogger(__name__)


def compute_stock_indicators(klines):
    """从 K 线列表计算所有技术指标

    Args:
        klines: list of dicts with keys [code, date, open, high, low, close, volume]
                sorted by date ASC. Must include at least 20 bars.

    Returns:
        (dict of {date_str: {ma5, ma10, ..., amplitude}}, or None if insufficient data)
    """
    if len(klines) < 20:
        logger.warning("compute_stock_indicators: 数据不足 %d 条", len(klines))
        return None

    closes = [k["close"] for k in klines]
    volumes = [k["volume"] for k in klines]
    highs = [k["high"] for k in klines]
    lows = [k["low"] for k in klines]

    results = {}
    for i in range(len(klines)):
        date_str = klines[i]["date"][:10]
        cur_close = closes[i]
        prev_close = closes[i - 1] if i >= 1 else cur_close
        open_val = klines[i].get("open", 0)

        window_closes = closes[:i + 1]
        window_volumes = volumes[:i + 1]
        window_highs = highs[:i + 1]
        window_lows = lows[:i + 1]

        high20 = max(window_highs[-20:]) if len(window_highs) >= 20 else window_highs[-1]
        low20 = min(window_lows[-20:]) if len(window_lows) >= 20 else window_lows[-1]
        amplitude = (highs[i] - lows[i]) / prev_close if prev_close > 0 else 0

        results[date_str] = {
            "close": cur_close,
            "volume": volumes[i],
            "ma5": calc_sma(window_closes, 5),
            "ma10": calc_sma(window_closes, 10),
            "ma20": calc_sma(window_closes, 20),
            "ma60": calc_sma(window_closes, 60),
            "ma5_vol": calc_sma(window_volumes, 5),
            "last_close": prev_close,
            "high20": high20,
            "low20": low20,
            "open": open_val,
            "rsi": calc_rsi(window_closes),
            "atr": calc_atr(window_highs, window_lows, window_closes),
            "adx": calc_adx(window_highs, window_lows, window_closes),
            "amplitude": amplitude,
        }

    return results


def get_codes_with_klines_today(db, today_str):
    """查询今天有 K 线数据的股票代码列表"""
    today_end = f"{today_str} 15:00"
    codes = db.stock_kline.distinct("code", {
        "frequency": 9,
        "date": today_end,
    })
    return codes


def update_stock_indicators(db, codes, warmup_days=60, backfill=False):
    """为指定股票更新区间内的指标（upsert 到 stock_indicators）

    Args:
        db: MongoDB 数据库对象
        codes: 股票代码列表
        warmup_days: 每日更新时加载的历史天数
        backfill: 是否回填所有历史

    Returns:
        (updated_count, error_count)
    """
    if backfill:
        start_str = "2000-01-01"
        end_str = datetime.now().strftime("%Y-%m-%d") + " 23:59"
    else:
        today = datetime.now()
        start_str = (today - timedelta(days=warmup_days)).strftime("%Y-%m-%d")
        end_str = today.strftime("%Y-%m-%d") + " 23:59"

    stock_klines = _batch_load_klines(db, codes, start_str, end_str)

    updated = 0
    errors = 0
    for code in codes:
        klines = stock_klines.get(code, [])
        if not klines:
            continue
        try:
            indicators = compute_stock_indicators(klines)
            if indicators is None:
                continue
            _upsert_indicators(db, code, indicators)
            updated += 1
        except Exception as e:
            logger.error("计算 %s 指标失败: %s", code, e)
            errors += 1

    return updated, errors


def backfill_all_indicators(db, chunk_size=200):
    """回填所有股票的所有历史指标"""
    all_codes = db.stock_kline.distinct("code", {"frequency": 9})
    logger.info("回填指标: 共 %d 只股票", len(all_codes))

    total_updated = 0
    total_errors = 0
    for i in range(0, len(all_codes), chunk_size):
        chunk = all_codes[i:i + chunk_size]
        updated, errors = update_stock_indicators(db, chunk, backfill=True)
        total_updated += updated
        total_errors += errors
        logger.info("回填进度: %d/%d (更新 %d, 错误 %d)",
                     min(i + chunk_size, len(all_codes)), len(all_codes),
                     total_updated, total_errors)

    logger.info("回填完成: 更新 %d 只, 错误 %d 只", total_updated, total_errors)
    return total_updated, total_errors


def _batch_load_klines(db, codes, start_str, end_str):
    """批量加载给定股票在时间范围内的 K 线"""
    raw = list(db.stock_kline.find(
        {"code": {"$in": codes}, "frequency": 9,
         "date": {"$gte": start_str, "$lte": end_str}},
        {"code": 1, "date": 1, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}
    ).sort("date", 1))

    result = {}
    for k in raw:
        result.setdefault(k["code"], []).append(k)
    return result


def _upsert_indicators(db, code, indicators):
    """批量 upsert 指标数据到 stock_indicators (使用 bulk_write 加速)"""
    requests = []
    now = datetime.now()
    for date_str, vals in indicators.items():
        requests.append(UpdateOne(
            {"code": code, "date": date_str},
            {"$set": {"code": code, "date": date_str, **vals, "updated_at": now},
             "$setOnInsert": {"created_at": now}},
            upsert=True,
        ))
    if requests:
        db.stock_indicators.bulk_write(requests, ordered=False)


def run_daily_update():
    """每日更新：为今天有 K 线的股票计算指标"""
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    db = get_db()
    today_str = datetime.now().strftime("%Y-%m-%d")
    codes = get_codes_with_klines_today(db, today_str)
    logger.info("今日有 K 线的股票: %d 只", len(codes))
    if not codes:
        logger.info("今日无新 K 线数据，跳过")
        return
    updated, errors = update_stock_indicators(db, codes)
    logger.info("每日指标更新完成: 成功 %d 只, 失败 %d 只", updated, errors)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "backfill":
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s [%(levelname)s] %(message)s")
        db = get_db()
        backfill_all_indicators(db)
    else:
        run_daily_update()
