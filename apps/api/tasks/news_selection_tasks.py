import re
import copy
from datetime import datetime, timedelta
from celery_config import celery_app
from database import get_db


@celery_app.task(bind=True, name="tasks.news_selection.run")
def run_news_selection(self):
    """新闻选股 Celery 任务：扫描新闻→提取 BK→查股票→计算价格→缓存结果"""
    try:
        self.update_state(state='PROGRESS', meta={'current': 0, 'total': 0, 'status': '开始扫描新闻...'})

        db = get_db()
        cache_collection = db.news_selection_cache

        # 1. 获取有 BK 板块的新闻
        news_list = list(db.news.find(
            {"stockList": {"$ne": []}},
            {"title": 1, "showTime": 1, "stockList": 1}
        ).sort("showTime", -1).limit(100))

        total_news = len(news_list)
        self.update_state(state='PROGRESS', meta={
            'current': 0, 'total': total_news,
            'status': f'共 {total_news} 条新闻，提取板块...'
        })

        # 2. 提取所有 BK 代码（去重）
        bk_set = set()
        for n in news_list:
            for item in n.get("stockList", []):
                m = re.search(r'(BK\d+)', str(item))
                if m:
                    bk_set.add(m.group(1))

        if not bk_set:
            self.update_state(state='PROGRESS', meta={
                'current': total_news, 'total': total_news,
                'status': '未找到板块代码'
            })
            return {"total": 0, "message": "未找到板块代码"}

        # 3. 查 BK→股票映射
        bk_stocks = list(db.bk_stocks.find(
            {"bk_code": {"$in": list(bk_set)}},
            {"bk_code": 1, "bk_name": 1, "stock_code": 1, "stock_name": 1}
        ))
        bk_name_map = {r["bk_code"]: r.get("bk_name", "") for r in bk_stocks}
        stock_codes = list(set(r["stock_code"] for r in bk_stocks))

        self.update_state(state='PROGRESS', meta={
            'current': 0, 'total': len(stock_codes),
            'status': f'扫描 {len(stock_codes)} 只股票的 K 线数据...'
        })

        # 4. 查 K 线数据（60 天）
        now = datetime.now()
        lookback = now - timedelta(days=60)
        klines_raw = list(db.stock_kline.find({
            "code": {"$in": stock_codes},
            "frequency": 9,
            "date": {
                "$gte": lookback.strftime("%Y-%m-%d"),
                "$lte": now.strftime("%Y-%m-%d") + " 23:59"
            }
        }).sort("date", 1))

        stock_klines = {}
        for k in klines_raw:
            c = k["code"]
            if c not in stock_klines:
                stock_klines[c] = []
            stock_klines[c].append(k)

        # 5. 计算每只股票的选股结果
        self.update_state(state='PROGRESS', meta={
            'current': 0, 'total': len(stock_codes),
            'status': '计算推荐结果...'
        })

        # 构建 news→BK 映射
        news_bk_map = {}
        for n in news_list:
            bks = set()
            for item in n.get("stockList", []):
                m = re.search(r'(BK\d+)', str(item))
                if m:
                    bks.add(m.group(1))
            if bks:
                news_bk_map[n["_id"]] = {
                    "title": n.get("title", ""),
                    "showTime": n.get("showTime", ""),
                    "bks": bks
                }

        results = []
        for idx, r in enumerate(bk_stocks):
            code = r["stock_code"]
            bk = r["bk_code"]
            klines = stock_klines.get(code, [])
            if not klines:
                continue

            closes = [k["close"] for k in klines]
            highs = [k["high"] for k in klines]
            lows = [k["low"] for k in klines]

            # 排除ST股票
            name = r.get("stock_name", "")
            if name.startswith("ST") or name.startswith("*ST"):
                continue

            current_price = closes[-1]
            if current_price <= 0:
                continue

            target_price = round(max(highs[-20:]) if len(highs) >= 20 else max(highs), 2)
            stop_loss = round(min(lows[-10:]) if len(lows) >= 10 else min(lows), 2)

            if target_price <= current_price:
                continue

            expected_return = round((target_price - current_price) / current_price * 100, 2)
            risk = round((current_price - stop_loss) / current_price * 100, 2) if stop_loss > 0 else 0

            ma_signal = None
            if len(closes) >= 20:
                short_ma = sum(closes[-5:]) / 5
                long_ma = sum(closes[-20:]) / 20
                prev_short = sum(closes[-6:-1]) / 5
                prev_long = sum(closes[-21:-1]) / 20
                if prev_short <= prev_long and short_ma > long_ma:
                    ma_signal = "golden_cross"

            # 找到关联该 BK 的新闻
            news_titles = []
            news_times = []
            for nid, info in news_bk_map.items():
                if bk in info["bks"]:
                    news_titles.append(info["title"])
                    t = info["showTime"]
                    if isinstance(t, datetime):
                        t = t.strftime("%Y-%m-%d %H:%M")
                    news_times.append(t)

            results.append({
                "code": code,
                "name": r.get("stock_name", ""),
                "bk_code": bk,
                "bk_name": bk_name_map.get(bk, ""),
                "news_titles": news_titles,
                "news_times": news_times,
                "current_price": current_price,
                "target_price": target_price,
                "stop_loss": stop_loss,
                "expected_return": expected_return,
                "risk": risk,
                "ma_signal": ma_signal,
                "created_at": now
            })

            if idx % 100 == 0:
                self.update_state(state='PROGRESS', meta={
                    'current': idx, 'total': len(stock_codes),
                    'status': f'已处理 {idx}/{len(stock_codes)} 只股票'
                })

        # 6. 按股票去重：同股票合并板块和新闻，保留预期收益最高的
        deduped = {}
        for r in results:
            code = r["code"]
            if code in deduped:
                exist = deduped[code]
                # 合并新闻标题
                exist_titles = set(exist.get("news_titles", []))
                for t in r.get("news_titles", []):
                    if t not in exist_titles:
                        exist["news_titles"].append(t)
                        exist_titles.add(t)
                # 合并新闻时间
                for t in r.get("news_times", []):
                    if t not in exist.get("news_times", []):
                        exist["news_times"].append(t)
                # 合并板块
                exist_bks = set(exist.get("_bk_list", []))
                if r.get("bk_code") not in exist_bks:
                    exist.setdefault("_bk_list", []).append(r["bk_code"])
                    exist_bks.add(r["bk_code"])
                # 保留预期收益高的
                if r["expected_return"] > exist["expected_return"]:
                    exist["expected_return"] = r["expected_return"]
                    exist["target_price"] = r["target_price"]
                    exist["stop_loss"] = r["stop_loss"]
                    exist["risk"] = r["risk"]
                    exist["ma_signal"] = r["ma_signal"]
                    exist["current_price"] = r["current_price"]
            else:
                r["_bk_list"] = [r["bk_code"]]
                deduped[code] = r

        for r in deduped.values():
            r.pop("_bk_list", None)

        final_results = list(deduped.values())

        # 7. 缓存到 MongoDB（先清旧数据，深拷贝避免 insert_many 注入 ObjectId）
        cache_collection.delete_many({})
        if final_results:
            cache_collection.insert_many(copy.deepcopy(final_results))

        self.update_state(state='PROGRESS', meta={
            'current': len(stock_codes), 'total': len(stock_codes),
            'status': f'新闻选股完成，选出 {len(results)} 只股票'
        })

        return {"total": len(results), "message": f"新闻选股完成，选出 {len(results)} 只股票"}

    except Exception as e:
        self.update_state(state='FAILURE', meta={'status': f'新闻选股失败: {str(e)}'})
        raise
