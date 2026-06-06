import copy
from datetime import datetime, timedelta
from typing import Dict, Any, List
from celery_config import celery_app
from database import get_db


@celery_app.task(bind=True, name="tasks.selection.run_dual_ma_selection")
def run_dual_ma_selection(
    self,
    short_period: int = 5,
    long_period: int = 20
) -> Dict[str, Any]:
    """双均线选股Celery任务"""
    try:
        self.update_state(state='PROGRESS', meta={'current': 0, 'total': 0, 'status': '开始选股...'})
        
        db = get_db()
        kline_collection = db.stock_kline
        selection_collection = db.stock_selections

        # 扫描固定历史范围用于均线计算（日期筛选只影响结果查询，不影响选股扫描范围）
        scan_days = 60
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=scan_days)
        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = end_dt.strftime("%Y-%m-%d")

        # 预加载股票名称映射
        stock_name_map = {}
        for s in db.sector_stocks.find({}, {"stock_code": 1, "stock_name": 1}):
            pure = s["stock_code"].split(".")[-1] if "." in s["stock_code"] else s["stock_code"]
            if pure not in stock_name_map:
                stock_name_map[pure] = s.get("stock_name", "")

        # 获取所有股票代码
        all_codes = kline_collection.distinct("code", {"frequency": 9})
        total_codes = len(all_codes)
        
        self.update_state(state='PROGRESS', meta={
            'current': 0,
            'total': total_codes,
            'status': f'共{total_codes}只股票，开始扫描...'
        })
        
        selected_stocks = []
        
        for idx, code in enumerate(all_codes):
            # 更新进度
            if idx % 100 == 0:
                self.update_state(state='PROGRESS', meta={
                    'current': idx,
                    'total': total_codes,
                    'status': f'已扫描{idx}/{total_codes}只股票'
                })
            
            # 获取该股票的K线数据
            klines = list(kline_collection.find({
                "code": code,
                "frequency": 9,
                "date": {"$gte": start_str, "$lte": end_str + " 23:59"}
            }).sort("date", 1))
            
            if len(klines) < long_period + 1:
                continue

            # 排除ST股票
            name = stock_name_map.get(code, "")
            if name.startswith("ST"):
                continue

            # 计算均线
            closes = [k["close"] for k in klines]
            
            # 计算最近一天的均线
            short_ma = sum(closes[-short_period:]) / short_period
            long_ma = sum(closes[-long_period:]) / long_period
            
            # 计算前一天的均线
            prev_short_ma = sum(closes[-short_period-1:-1]) / short_period
            prev_long_ma = sum(closes[-long_period-1:-1]) / long_period
            
            # 金叉条件：短期均线从下方穿越长期均线
            if prev_short_ma <= prev_long_ma and short_ma > long_ma:
                selected_stocks.append({
                    "code": code,
                    "name": stock_name_map.get(code, ""),
                    "short_ma": round(short_ma, 2),
                    "long_ma": round(long_ma, 2),
                    "current_price": closes[-1],
                    "change_pct": round(((closes[-1] - closes[0]) / closes[0]) * 100, 2),
                    "selection_date": datetime.now(),
                    "strategy": "dual_moving_average",
                    "params": {
                        "short_period": short_period,
                        "long_period": long_period
                    }
                })
        
        # 保存结果到数据库（深拷贝避免 insert_many 注入 ObjectId）
        if selected_stocks:
            selection_collection.insert_many(copy.deepcopy(selected_stocks))

        # 返回结果中 datetime 转字符串（Celery JSON 序列化要求）
        return_stocks = []
        for s in selected_stocks:
            return_stocks.append({
                "code": s["code"],
                "name": s["name"],
                "short_ma": s["short_ma"],
                "long_ma": s["long_ma"],
                "current_price": s["current_price"],
                "change_pct": s["change_pct"],
                "selection_date": s["selection_date"].strftime("%Y-%m-%d %H:%M:%S"),
                "strategy": s["strategy"],
                "params": s["params"]
            })
        
        self.update_state(state='PROGRESS', meta={
            'current': total_codes,
            'total': total_codes,
            'status': f'选股完成，选出{len(selected_stocks)}只股票'
        })
        
        return {
            "selected_stocks": return_stocks,
            "total": len(return_stocks),
            "strategy": "dual_moving_average",
            "params": {
                "short_period": short_period,
                "long_period": long_period
            }
        }
        
    except Exception as e:
        self.update_state(state='FAILURE', meta={'status': f'选股失败: {str(e)}'})
        raise
