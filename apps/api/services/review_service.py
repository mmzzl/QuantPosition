import math
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple


class ReviewService:

    @staticmethod
    def _determine_position(daily_klines: List[Dict]) -> str:
        """定大方向：低位(吸筹区) / 中段(洗盘区) / 高位(出货区)"""
        if len(daily_klines) < 5:
            return "中段"

        closes = [k["close"] for k in daily_klines]
        stage_gain = (closes[-1] - closes[0]) / closes[0]

        if stage_gain > 0.50:
            return "高位"
        elif stage_gain > 0.15:
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
                             pattern: str, tail_signal: str,
                             main_force: Dict[str, Any] = None) -> Dict[str, str]:
        intention = (main_force or {}).get("intention", "")

        # ── 主力意图优先 ──
        if intention == "真出货":
            return {
                "conclusion": "卖出",
                "reason": f"主力真出货：{(main_force or {}).get('intention_detail', '高位派发')}",
                "strategy": "次日开盘不抱有幻想，小幅冲高即全部卖出，规避日内大跌",
            }

        if intention == "吸筹":
            return {
                "conclusion": "持有",
                "reason": f"主力吸筹：{(main_force or {}).get('intention_detail', '低位建仓')}",
                "strategy": "中线看好，缩量回调可加仓，放量滞涨再减仓",
            }

        if intention == "洗盘":
            return {
                "conclusion": "持有",
                "reason": f"主力洗盘：{(main_force or {}).get('intention_detail', '上涨中继清理浮筹')}",
                "strategy": "次日只要不有效跌破均价，全程持有，等冲高放量滞涨再分批卖出",
            }

        if intention == "假出货诱空":
            return {
                "conclusion": "持有",
                "reason": f"诱空假出货：{(main_force or {}).get('intention_detail', '假跳水真洗盘')}",
                "strategy": "主力故意砸盘吓散户，坚定持有，次日修复可加仓",
            }

        # ── 原有信号逻辑作为兜底 ──
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

    # ======================== 主力意图 4 层验证框架 ========================

    @staticmethod
    def _analyze_daily_volume_trend(daily_klines: List[Dict]) -> Dict[str, Any]:
        """量能辨真假：分析日线级别的量价关系"""
        if len(daily_klines) < 10:
            return {"pattern": "数据不足", "up_vol_ratio": 0, "down_vol_shrink": 0, "has_volume_pile": False}

        recent = daily_klines[-20:] if len(daily_klines) >= 20 else daily_klines
        up_vol = sum(k["volume"] for k in recent if k["close"] >= k["open"])
        down_vol = sum(k["volume"] for k in recent if k["close"] < k["open"])
        up_down_ratio = up_vol / max(down_vol, 1)

        up_days = sum(1 for k in recent if k["close"] >= k["open"])
        down_days = sum(1 for k in recent if k["close"] < k["open"])
        avg_up_vol = up_vol / max(up_days, 1)
        avg_down_vol = down_vol / max(down_days, 1)
        down_shrink_ratio = avg_down_vol / max(avg_up_vol, 1)

        vol_list = [k["volume"] for k in recent]
        avg_vol = sum(vol_list) / max(len(vol_list), 1)
        vol_std = (sum((v - avg_vol) ** 2 for v in vol_list) / max(len(vol_list), 1)) ** 0.5
        vol_pile_threshold = avg_vol + vol_std * 1.5
        pile_days = sum(1 for v in vol_list if v > vol_pile_threshold and v > avg_vol * 1.8)

        has_volume_pile = pile_days >= 2

        return {
            "pattern": "吸筹量" if up_down_ratio > 1.3 and down_shrink_ratio < 0.7 and has_volume_pile
                       else "洗盘量" if down_shrink_ratio < 0.6
                       else "出货量" if up_down_ratio < 0.7
                       else "震荡量",
            "up_vol_ratio": round(up_down_ratio, 2),
            "down_shrink_ratio": round(down_shrink_ratio, 2),
            "has_volume_pile": has_volume_pile,
        }

    @staticmethod
    def _detect_kline_pattern(daily_klines: List[Dict]) -> List[str]:
        """识别K线形态：长下影、W底、假破位、避雷针等"""
        if len(daily_klines) < 10:
            return []
        recent = daily_klines[-15:]
        patterns = []

        closes = [k["close"] for k in recent]
        highs = [k["high"] for k in recent]
        lows = [k["low"] for k in recent]
        opens = [k["open"] for k in recent]

        for i in range(-5, 0):
            k = recent[i]
            body = abs(k["close"] - k["open"])
            lower_shadow = min(k["open"], k["close"]) - k["low"]
            upper_shadow = k["high"] - max(k["open"], k["close"])
            if body > 0 and lower_shadow > body * 2:
                patterns.append("长下影")
            if body > 0 and upper_shadow > body * 2:
                patterns.append("避雷针")

        low_10 = min(lows[-10:])
        low_idx = lows[-10:].index(low_10) if len(lows) >= 10 else 0
        if 2 < low_idx < 8:
            patterns.append("W底")

        if len(closes) >= 3:
            prev_close = closes[-3]
            mid_close = closes[-2]
            last_close = closes[-1]
            if prev_close > mid_close and last_close > mid_close:
                if abs(last_close - prev_close) / max(prev_close, 0.01) < 0.03:
                    patterns.append("假破位")

        return list(set(patterns))

    @staticmethod
    def _assess_main_force_intention(
        position: str,
        daily_klines: List[Dict],
        vwap_status: str,
        volume_signal: str,
        pattern: str,
        tail_signal: str,
    ) -> Dict[str, Any]:
        """
        4层验证确定主力意图：吸筹 / 洗盘 / 假出货(诱空) / 真出货 / 震荡

        位置定大方向 → 量能辨真假 → K线/筹码看底仓 → 盘口拆演戏
        """
        vol_trend = ReviewService._analyze_daily_volume_trend(daily_klines)
        daily_patterns = ReviewService._detect_kline_pattern(daily_klines)

        intention = "震荡"
        detail_parts = []
        confidence = "低"

        # ── Layer 1: 位置定大方向 ──
        if position == "低位":
            # Layer 2: 量能验证
            if vol_trend["pattern"] == "吸筹量":
                intention = "吸筹"
                detail_parts.append("低位+上涨放量下跌缩量")
                confidence = "中"
                if vol_trend["has_volume_pile"]:
                    detail_parts.append("持续量堆")
                    confidence = "高"
                if "长下影" in daily_patterns or "W底" in daily_patterns:
                    detail_parts.append("底部形态")
                    confidence = "高"
            elif volume_signal == "洗盘" and vwap_status == "强势":
                intention = "吸筹"
                detail_parts.append("低位+今日洗盘企稳")
                confidence = "中"

        elif position == "中段":
            # Layer 2+4: 量能 + 盘口验证
            is_wash = (
                volume_signal in ("洗盘", "试盘")
                and vwap_status != "弱势"
                and tail_signal != "放量跳水"
            )
            is_fake_dist = (
                volume_signal == "出货"
                and vwap_status != "弱势"
                and tail_signal not in ("放量跳水",)
                and "假破位" in daily_patterns
            )
            is_dist = (
                volume_signal == "出货"
                and vwap_status == "弱势"
                and pattern in ("M头分时", "高开低走阴跌型", "早盘脉冲全天回落")
            )

            if is_dist and is_fake_dist:
                intention = "假出货诱空"
                detail_parts.append("中段+疑似出货但位置不高+形态修复")
                confidence = "中"
            elif is_dist:
                intention = "出货风险"
                detail_parts.append("中段+价量背离+分时弱势")
                confidence = "中"
            elif is_fake_dist:
                intention = "假出货诱空"
                detail_parts.append("中段+假破位+假跳水")
                confidence = "高"
                if "长下影" in daily_patterns:
                    detail_parts.append("长下影确认支撑")
            elif is_wash:
                intention = "洗盘"
                detail_parts.append("中段+缩量回调")
                confidence = "中"
                if vol_trend["pattern"] == "洗盘量" or vol_trend["down_shrink_ratio"] < 0.6:
                    detail_parts.append("量能萎缩主力惜售")
                    confidence = "高"
                if vwap_status == "强势":
                    detail_parts.append("均价支撑")
                    confidence = "高"

        elif position == "高位":
            is_real_dist = (
                volume_signal == "出货"
                or vwap_status == "弱势"
                or pattern in ("M头分时", "高开低走阴跌型", "早盘脉冲全天回落")
                or tail_signal == "放量跳水"
                or "避雷针" in daily_patterns
            )
            if is_real_dist:
                intention = "真出货"
                detail_parts.append("高位+主力派发信号")
                confidence = "高"
                if vol_trend["pattern"] == "出货量":
                    detail_parts.append("阴量放大")
                if tail_signal == "放量跳水":
                    detail_parts.append("尾盘跳水无承接")
            else:
                intention = "高位震荡"
                detail_parts.append("高位+量价尚可")
                confidence = "低"

        # 无明确结论的兜底
        if intention == "震荡" and position in ("低位", "中段"):
            if vwap_status == "强势" and volume_signal != "出货":
                intention = "洗盘" if position == "中段" else "吸筹"
                detail_parts.append(f"{position}+均线支撑")
                confidence = "低"

        intention_detail = "，".join(detail_parts) if detail_parts else "信号不明确"

        return {
            "intention": intention,
            "intention_detail": intention_detail,
            "intention_confidence": confidence,
            "daily_vol_pattern": vol_trend["pattern"],
            "daily_patterns": daily_patterns,
        }

    # ======================== 原有方法保持不变 ========================

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

        # 主力意图 4层验证
        main_force = ReviewService._assess_main_force_intention(
            position, daily_klines, vwap_status, volume_signal, pattern, tail_signal
        )
        conclusion = ReviewService._generate_conclusion(
            position, vwap_status, volume_signal, pattern, tail_signal, main_force
        )

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
            "main_force_intention": main_force["intention"],
            "intention_detail": main_force["intention_detail"],
            "intention_confidence": main_force["intention_confidence"],
            "daily_vol_pattern": main_force["daily_vol_pattern"],
            "daily_patterns": main_force["daily_patterns"],
        }
