from datetime import datetime
from typing import List, Dict, Any, Optional


class ReviewService:

    @staticmethod
    def _determine_position(daily_klines: List[Dict]) -> str:
        if len(daily_klines) < 5:
            return "中段"

        closes = [k["close"] for k in daily_klines]

        stage_gain = (closes[-1] - closes[0]) / closes[0]

        high_volume = max(k.get("volume", 0) for k in daily_klines[-10:])
        avg_volume = sum(k.get("volume", 0) for k in daily_klines[-10:]) / max(len(daily_klines[-10:]), 1)
        volume_ratio = high_volume / avg_volume if avg_volume > 0 else 0

        if stage_gain > 0.40 or volume_ratio > 3.0:
            return "高位"
        elif stage_gain > 0.10:
            return "中段"
        else:
            return "低位"

    @staticmethod
    def _analyze_vwap(bars_5m: List[Dict]) -> tuple:
        if not bars_5m:
            return "震荡", 0

        total_pv = 0.0
        total_v = 0.0
        for bar in bars_5m:
            typical_price = (bar["high"] + bar["low"] + bar["close"]) / 3
            vol = bar["volume"]
            total_pv += typical_price * vol
            total_v += vol

        vwap = total_pv / total_v if total_v > 0 else bars_5m[-1]["close"]

        above_count = sum(1 for b in bars_5m if b["close"] >= vwap)
        ratio = above_count / len(bars_5m)

        first_half = bars_5m[:len(bars_5m)//2]
        second_half = bars_5m[len(bars_5m)//2:]
        vwap_first = sum(b["close"] for b in first_half) / len(first_half) if first_half else vwap
        vwap_second = sum(b["close"] for b in second_half) / len(second_half) if second_half else vwap
        vwap_slope = vwap_second - vwap_first

        if ratio >= 0.65 and vwap_slope > 0:
            return "强势", vwap
        elif ratio <= 0.35 and vwap_slope < 0:
            return "弱势", vwap
        else:
            return "震荡", vwap

    @staticmethod
    def _analyze_volume(bars_5m: List[Dict]) -> tuple:
        if len(bars_5m) < 10:
            return "震荡", "数据不足"

        def avg_vol(bars):
            return sum(b["volume"] for b in bars) / max(len(bars), 1)

        morning_bars = [b for b in bars_5m if b["date"][11:13] in ("09", "10") and b["date"][11:16] <= "10:00"]
        afternoon_bars = [b for b in bars_5m if "10:05" <= b["date"][11:16] <= "14:00"]
        tail_bars = [b for b in bars_5m if b["date"][11:16] >= "14:05"]

        morning_vol = avg_vol(morning_bars) if morning_bars else 0
        afternoon_vol = avg_vol(afternoon_bars) if afternoon_bars else 0
        tail_vol = avg_vol(tail_bars) if tail_bars else 0

        total_vol = sum(b["volume"] for b in bars_5m)
        up_vol = sum(b["volume"] for b in bars_5m if b["close"] >= b["open"])
        down_vol = total_vol - up_vol
        up_down_ratio = up_vol / max(down_vol, 1)
        overall_avg_vol = total_vol / max(len(bars_5m), 1)

        up_close = bars_5m[-1]["close"] >= bars_5m[-1]["open"]

        morning_spike = morning_vol > afternoon_vol * 1.5 and afternoon_vol > 0
        spike_closes = [b["close"] for b in bars_5m[:5]]
        early_rising = len(spike_closes) >= 2 and max(spike_closes) > spike_closes[0]

        if morning_spike and early_rising:
            spike_avg = avg_vol(bars_5m[:3])
            retreat_avg = avg_vol(bars_5m[3:8])
            if retreat_avg < spike_avg * 0.4:
                return "出货", "早盘放量急拉后缩量回落，量价背离"

        if down_vol > up_vol * 1.5 and tail_vol > overall_avg_vol * 1.3 and not up_close:
            return "出货", "下跌放量，尾盘放量跳水"

        if up_down_ratio > 1.5 and tail_vol > overall_avg_vol * 1.2 and up_close:
            return "洗盘", "下跌缩量上涨放量，尾盘放量拉升"

        if len(bars_5m) >= 10:
            first_third = bars_5m[:len(bars_5m)//3]
            max_first_vol = max(b["volume"] for b in first_third) if first_third else 0
            if max_first_vol > overall_avg_vol * 2:
                peak_close = max(b["close"] for b in first_third)
                if peak_close > first_third[0]["close"] * 1.03:
                    after_bars = bars_5m[len(bars_5m)//3:]
                    after_avg = avg_vol(after_bars) if after_bars else 0
                    if after_avg < max_first_vol * 0.3:
                        return "试盘", "盘中突然大单拉升测试抛压"

        return "震荡", "无明显量价背离"

    @staticmethod
    def _recognize_pattern(bars_5m: List[Dict], vwap_status: str, volume_signal: str) -> str:
        if len(bars_5m) < 20:
            return "震荡"

        closes = [b["close"] for b in bars_5m]
        highs = [b["high"] for b in bars_5m]
        first_half = closes[:len(closes)//2]
        second_half = closes[len(closes)//2:]
        avg_first = sum(first_half) / max(len(first_half), 1)
        avg_second = sum(second_half) / max(len(second_half), 1)

        tail_bars = bars_5m[-6:]
        tail_vol_avg = sum(b["volume"] for b in tail_bars) / max(len(tail_bars), 1)
        overall_vol_avg = sum(b["volume"] for b in bars_5m) / max(len(bars_5m), 1)
        tail_price_rising = tail_bars[-1]["close"] > tail_bars[0]["close"] if tail_bars else False

        early_high = max(highs[:6]) if len(highs) >= 6 else 0
        second_peak = max(highs[3:9]) if len(highs) >= 9 else 0
        has_double_top = early_high > 0 and second_peak > 0 and abs(early_high - second_peak) / max(early_high, 0.01) < 0.03

        if tail_vol_avg > overall_vol_avg * 1.5 and tail_price_rising:
            return "尾盘抢筹型"

        if vwap_status == "弱势" and volume_signal == "出货":
            if has_double_top:
                return "M头分时"
            if closes[0] > closes[-1] and closes[0] > closes[len(closes)//4] * 1.02:
                return "高开低走阴跌型"
            if bars_5m[0]["close"] < bars_5m[min(2, len(bars_5m)-1)]["close"] and closes[-1] < closes[0]:
                return "早盘脉冲全天回落"

        if volume_signal == "洗盘":
            if avg_second > avg_first and closes[-1] > closes[0]:
                return "U型洗盘分时"
            if avg_second >= avg_first * 1.01 and closes[-1] > closes[0]:
                return "单边震荡上行"

        if has_double_top:
            return "M头分时"

        return "震荡平衡形态"

    @staticmethod
    def _generate_conclusion(position: str, vwap_status: str, volume_signal: str,
                             pattern: str, tail_signal: str) -> Dict[str, str]:
        sell_signals = 0

        if position == "高位":
            sell_signals += 1
        if vwap_status == "弱势":
            sell_signals += 1
        if volume_signal == "出货":
            sell_signals += 1
        if pattern in ("M头分时", "高开低走阴跌型", "早盘脉冲全天回落"):
            sell_signals += 1
        if tail_signal == "放量跳水":
            sell_signals += 1

        hold_conditions = (
            position in ("低位", "中段")
            and vwap_status == "强势"
            and volume_signal == "洗盘"
            and pattern in ("U型洗盘分时", "单边震荡上行", "尾盘抢筹型")
        )

        if hold_conditions:
            return {
                "conclusion": "持有",
                "reason": f"{position}启动+均价支撑+下跌缩量上涨放量+尾盘稳定",
                "strategy": "次日只要不有效跌破均价，全程持有，等冲高放量滞涨再分批卖出",
            }

        if sell_signals >= 2:
            return {
                "conclusion": "卖出",
                "reason": "高位 均价弱势 量价背离 出货形态",
                "strategy": "次日开盘不抱有幻想，小幅冲高即全部卖出，规避日内大跌",
            }

        return {
            "conclusion": "观望",
            "reason": "多空分歧，无明显方向信号",
            "strategy": "次日减半仓观望，等方向明确后再操作",
        }

    @staticmethod
    def _get_daily_klines(code: str, days: int = 60) -> List[Dict]:
        from database import get_db
        from datetime import timedelta
        db = get_db()
        now = datetime.now()
        start = (now - timedelta(days=days)).strftime("%Y-%m-%d")
        end = now.strftime("%Y-%m-%d") + " 23:59"
        return list(db.stock_kline.find({
            "code": code,
            "frequency": 9,
            "date": {"$gte": start, "$lte": end}
        }).sort("date", 1))

    @staticmethod
    def _get_5m_klines(code: str, date_str: str) -> List[Dict]:
        from database import get_db
        db = get_db()
        return list(db.stock_kline_5m.find({
            "code": code,
            "date": {"$gte": f"{date_str} 00:00", "$lte": f"{date_str} 23:59"}
        }).sort("date", 1))

    @staticmethod
    def analyze(code: str, name: str, date_str: str = None) -> Dict[str, Any]:
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        daily_klines = ReviewService._get_daily_klines(code)
        bars_5m = ReviewService._get_5m_klines(code, date_str)

        if not bars_5m:
            return {"code": code, "name": name, "conclusion": "跳过", "reason": f"{date_str} 无 5 分钟 K 线数据"}

        position = ReviewService._determine_position(daily_klines)
        vwap_status, vwap = ReviewService._analyze_vwap(bars_5m)
        volume_signal, vol_detail = ReviewService._analyze_volume(bars_5m)
        pattern = ReviewService._recognize_pattern(bars_5m, vwap_status, volume_signal)

        tail_bars = bars_5m[-6:]
        tail_vol = sum(b["volume"] for b in tail_bars)
        overall_avg_vol = sum(b["volume"] for b in bars_5m) / max(len(bars_5m), 1)
        if tail_vol > len(tail_bars) * overall_avg_vol * 1.5 and tail_bars[-1]["close"] > tail_bars[0]["close"]:
            tail_signal = "抢筹"
        elif tail_vol > len(tail_bars) * overall_avg_vol * 1.5 and tail_bars[-1]["close"] < tail_bars[0]["close"]:
            tail_signal = "放量跳水"
        else:
            tail_signal = "无量横盘"

        conclusion = ReviewService._generate_conclusion(position, vwap_status, volume_signal, pattern, tail_signal)

        return {
            "code": code,
            "name": name,
            "date": date_str,
            "position": position,
            "vwap_status": vwap_status,
            "volume_signal": volume_signal,
            "volume_detail": vol_detail,
            "pattern": pattern,
            "tail_signal": tail_signal,
            "conclusion": conclusion["conclusion"],
            "reason": conclusion["reason"],
            "strategy": conclusion["strategy"],
        }
