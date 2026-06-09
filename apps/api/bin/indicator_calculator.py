# -*- coding: utf-8 -*-
"""指标预计算：每天盘后计算全市场股票技术指标存入 stock_indicators 集合

支持两种运行模式：
  1. python bin/indicator_calculator.py        # 每日增量更新（只有今天有数据的股票）
  2. python bin/indicator_calculator.py backfill  # 一次性回填所有历史数据
"""
import sys
import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db
from bin.rule_engine import calc_rsi, calc_atr
from pymongo import UpdateOne

logger = logging.getLogger(__name__)


def compute_stock_indicators(klines):
    """从 K 线列表计算所有技术指标 (pandas 向量化加速)

    Args:
        klines: list of dicts with keys [code, date, open, high, low, close, volume]
                sorted by date ASC. Must include at least 20 bars.

    Returns:
        (dict of {date_str: {ma5, ma10, ..., amplitude}}, or None if insufficient data)
    """
    if len(klines) < 20:
        logger.warning("compute_stock_indicators: 数据不足 %d 条", len(klines))
        return None

    df = pd.DataFrame(klines)
    df['date_str'] = df['date'].str[:10]
    for col in ('open', 'high', 'low', 'close', 'volume'):
        df[col] = df[col].astype(float)

    # 向量化 SMA / rolling
    df['ma5'] = df['close'].rolling(5, min_periods=1).mean()
    df['ma10'] = df['close'].rolling(10, min_periods=1).mean()
    df['ma20'] = df['close'].rolling(20, min_periods=1).mean()
    df['ma60'] = df['close'].rolling(60, min_periods=1).mean()
    df['ma5_vol'] = df['volume'].rolling(5, min_periods=1).mean()
    df['high20'] = df['high'].rolling(20, min_periods=1).max()
    df['low20'] = df['low'].rolling(20, min_periods=1).min()

    df['last_close'] = df['close'].shift(1).fillna(df['close'])
    df['amplitude'] = (df['high'] - df['low']) / df['last_close']
    df.loc[df['last_close'] <= 0, 'amplitude'] = 0.0

    # RSI / ATR / ADX 仍需要逐行计算（Wilder 递归）
    closes_l = df['close'].tolist()
    highs_l = df['high'].tolist()
    lows_l = df['low'].tolist()
    n = len(closes_l)

    rsi_vals = []
    atr_vals = []
    adx_vals = []

    # --- RSI: Wilder 迭代 ---
    if n >= 15:
        gains = []
        losses = []
        for i in range(1, 15):
            d = closes_l[i] - closes_l[i - 1]
            gains.append(d if d > 0 else 0)
            losses.append(-d if d < 0 else 0)
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14
        rsi_vals[:15] = [50] * 15
        rsi_vals[14] = 100 - (100 / (1 + avg_gain / avg_loss)) if avg_loss > 0 else 100
        for i in range(15, n):
            d = closes_l[i] - closes_l[i - 1]
            g = d if d > 0 else 0
            l = -d if d < 0 else 0
            avg_gain = (avg_gain * 13 + g) / 14
            avg_loss = (avg_loss * 13 + l) / 14
            rsi_vals.append(100 - (100 / (1 + avg_gain / avg_loss)) if avg_loss > 0 else 100)
    else:
        rsi_vals = [50] * n

    # --- ATR: Wilder 迭代 ---
    if n >= 2:
        trs = []
        atr_vals.append(0.0)
        for i in range(1, n):
            tr = max(highs_l[i] - lows_l[i],
                     abs(highs_l[i] - closes_l[i - 1]),
                     abs(lows_l[i] - closes_l[i - 1]))
            trs.append(tr)
            atr_vals.append(tr)
        if n >= 15:
            atr = sum(trs[:14]) / 14
            atr_vals[14] = atr
            for i in range(14, len(trs)):
                atr = (atr * 13 + trs[i]) / 14
                atr_vals[i + 1] = atr
    else:
        atr_vals = [0.0] * n

    # --- ADX: 渐进式 O(n) 计算 ---
    adx_vals = [25.0] * n
    if n >= 28:
        trs = [0.0] * (n - 1)
        pdms = [0.0] * (n - 1)
        mdms = [0.0] * (n - 1)
        for i in range(1, n):
            tr = max(highs_l[i] - lows_l[i],
                     abs(highs_l[i] - closes_l[i - 1]),
                     abs(lows_l[i] - closes_l[i - 1]))
            trs[i - 1] = tr
            up = highs_l[i] - highs_l[i - 1]
            down = lows_l[i - 1] - lows_l[i]
            pdms[i - 1] = up if up > down and up > 0 else 0
            mdms[i - 1] = down if down > up and down > 0 else 0

        s_tr = sum(trs[:14]) / 14
        s_pdm = sum(pdms[:14]) / 14
        s_mdm = sum(mdms[:14]) / 14

        dxs = []
        for i in range(14, n - 1):
            s_tr = (s_tr * 13 + trs[i]) / 14
            s_pdm = (s_pdm * 13 + pdms[i]) / 14
            s_mdm = (s_mdm * 13 + mdms[i]) / 14
            pdi = s_pdm / s_tr * 100 if s_tr > 0 else 0
            mdi = s_mdm / s_tr * 100 if s_tr > 0 else 0
            if pdi + mdi > 0:
                dxs.append(abs(pdi - mdi) / (pdi + mdi) * 100)
            else:
                dxs.append(0)

        if len(dxs) >= 14:
            adx_val = sum(dxs[:14]) / 14
            adx_vals[28] = adx_val
            for j in range(14, len(dxs)):
                adx_val = (adx_val * 13 + dxs[j]) / 14
                adx_vals[j + 15] = adx_val

    # --- 组装结果 ---
    results = {}
    for idx, row in df.iterrows():
        results[row['date_str']] = {
            "close": row['close'], "volume": row['volume'],
            "open": row['open'], "high": row['high'], "low": row['low'],
            "ma5": row['ma5'], "ma10": row['ma10'],
            "ma20": row['ma20'], "ma60": row['ma60'],
            "ma5_vol": row['ma5_vol'],
            "last_close": row['last_close'],
            "high20": row['high20'], "low20": row['low20'],
            "rsi": rsi_vals[idx], "atr": atr_vals[idx], "adx": adx_vals[idx],
            "amplitude": row['amplitude'],
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

    def _process(code):
        klines = stock_klines.get(code, [])
        if not klines:
            return False, False
        try:
            indicators = compute_stock_indicators(klines)
            if indicators is None:
                return False, False
            _upsert_indicators(db, code, indicators)
            return True, False
        except Exception as e:
            logger.error("计算 %s 指标失败: %s", code, e)
            return False, True

    updated = 0
    errors = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_process, code) for code in codes]
        for f in as_completed(futures):
            ok, err = f.result()
            if ok:
                updated += 1
            elif err:
                errors += 1

    return updated, errors


def backfill_all_indicators(db, chunk_size=200):
    """回填所有股票的所有历史指标"""
    import time
    all_codes = db.stock_kline.distinct("code", {"frequency": 9})
    total = len(all_codes)
    logger.info("回填指标: 共 %d 只股票", total)

    total_updated = 0
    total_errors = 0
    t_start = time.time()
    for i in range(0, total, chunk_size):
        chunk = all_codes[i:i + chunk_size]
        updated, errors = update_stock_indicators(db, chunk, backfill=True)
        total_updated += updated
        total_errors += errors
        elapsed = time.time() - t_start
        done = min(i + chunk_size, total)
        rate = done / elapsed if elapsed > 0 else 0
        eta = (total - done) / rate if rate > 0 else 0
        logger.info("回填 [%d/%d] 更新%d 错误%d | %.1f只/秒 预计剩余%.0f秒",
                     done, total, total_updated, total_errors, rate, eta)
        sys.stdout.flush()

    logger.info("回填完成: 更新 %d 只, 错误 %d 只, 耗时 %.0f 秒",
                 total_updated, total_errors, time.time() - t_start)
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
