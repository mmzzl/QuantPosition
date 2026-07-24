from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from database import get_db


class StockSelectionService:
    """选股服务"""

    @staticmethod
    def run_dual_ma(short_period: int = 5, long_period: int = 20) -> str:
        """提交双均线选股 Celery 任务，返回 task_id"""
        from tasks.selection_tasks import run_dual_ma_selection
        task = run_dual_ma_selection.delay(
            short_period=short_period,
            long_period=long_period
        )
        return task.id

    @staticmethod
    def save_selection_result(collection, result: dict) -> None:
        """保存单条选股结果到数据库"""
        from copy import deepcopy
        collection.insert_one(deepcopy(result))

    @staticmethod
    def dual_moving_average_selection(
        short_period: int = 5,
        long_period: int = 20,
        period: str = "24h",
        start_date: str = None,
        end_date: str = None
    ) -> Dict[str, Any]:
        """双均线选股：短期均线上穿长期均线"""
        db = get_db()
        kline_collection = db.stock_kline
        selection_collection = db.stock_selections

        # 计算日期范围
        if start_date and end_date:
            start_str = start_date
            end_str = end_date
        else:
            end_dt = datetime.now()
            if period == "7d":
                start_dt = end_dt - timedelta(days=7)
            elif period == "30d":
                start_dt = end_dt - timedelta(days=30)
            else:  # 24h
                start_dt = end_dt - timedelta(days=1)
            start_str = start_dt.strftime("%Y-%m-%d")
            end_str = end_dt.strftime("%Y-%m-%d")

        # 获取所有股票代码
        all_codes = kline_collection.distinct("code", {"frequency": 9})
        
        selected_stocks = []
        
        for code in all_codes:
            # 获取该股票的K线数据
            klines = list(kline_collection.find({
                "code": code,
                "frequency": 9,
                "date": {"$gte": start_str, "$lte": end_str + " 23:59"}
            }).sort("date", 1))
            
            if len(klines) < long_period + 1:
                continue
            
            # 计算均线
            closes = [k["close"] for k in klines]
            dates = [k["date"] for k in klines]
            
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
                    "name": "",  # 后续填充
                    "short_ma": round(short_ma, 2),
                    "long_ma": round(long_ma, 2),
                    "current_price": closes[-1],
                    "change_pct": round(((closes[-1] - closes[0]) / closes[0]) * 100, 2),
                    "selection_date": datetime.now(),
                    "period": period,
                    "strategy": "dual_moving_average",
                    "params": {
                        "short_period": short_period,
                        "long_period": long_period
                    }
                })
        
        # 保存结果到数据库
        if selected_stocks:
            selection_collection.insert_many(selected_stocks)
        
        return {
            "selected_stocks": selected_stocks,
            "total": len(selected_stocks),
            "period": period,
            "start_date": start_str,
            "end_date": end_str,
            "strategy": "dual_moving_average",
            "params": {
                "short_period": short_period,
                "long_period": long_period
            }
        }

    @staticmethod
    def get_selection_results(
        period: str = "24h",
        start_date: str = None,
        end_date: str = None,
        selection_start: str = None,
        selection_end: str = None,
        strategy: str = None,
        sort_by: str = "selection_date",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """获取选股结果"""
        db = get_db()
        selection_collection = db.stock_selections

        # 按选股日期范围筛选（日期筛选仅用于查询，选股本身扫描全量数据）
        now = datetime.now()
        date_filter = {}
        if start_date and end_date:
            date_filter = {
                "selection_date": {
                    "$gte": datetime.strptime(start_date, "%Y-%m-%d"),
                    "$lte": datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
                }
            }
        elif selection_start and selection_end:
            date_filter = {
                "selection_date": {
                    "$gte": datetime.strptime(selection_start, "%Y-%m-%d"),
                    "$lte": datetime.strptime(selection_end, "%Y-%m-%d") + timedelta(days=1)
                }
            }
        elif period == "7d":
            date_filter = {"selection_date": {"$gte": now - timedelta(days=7)}}
        elif period == "30d":
            date_filter = {"selection_date": {"$gte": now - timedelta(days=30)}}
        else:  # 24h
            date_filter = {"selection_date": {"$gte": now - timedelta(days=1)}}

        query = {"strategy": "dual_moving_average"}
        if date_filter:
            query.update(date_filter)

        # 查询总数
        total = selection_collection.count_documents(query)
        
        # 排序
        sort_dir = -1 if sort_order == "desc" else 1
        sort_field = sort_by if sort_by in ("selection_date", "change_pct", "current_price") else "selection_date"
        results = list(selection_collection.find(query)
                       .sort([(sort_field, sort_dir), ("_id", -1)])
                       .skip((page - 1) * page_size).limit(page_size))
        
        # 预加载股票名称映射（后备填充）
        stock_name_map = {}
        for s in db.sector_stocks.find({}, {"stock_code": 1, "stock_name": 1}):
            pure = s["stock_code"].split(".")[-1] if "." in s["stock_code"] else s["stock_code"]
            stock_name_map[pure] = s.get("stock_name", "")

        # 格式化结果
        formatted_results = []
        for r in results:
            code = r.get("code", "")
            name = r.get("name", "") or stock_name_map.get(code, "")
            formatted_results.append({
                "code": code,
                "name": name,
                "short_ma": r.get("short_ma", 0),
                "long_ma": r.get("long_ma", 0),
                "current_price": r.get("current_price", 0),
                "change_pct": r.get("change_pct", 0),
                "selection_date": r.get("selection_date", datetime.now()).strftime("%Y-%m-%d %H:%M"),
                "strategy": r.get("strategy", ""),
                "params": r.get("params", {})
            })
        
        return {
            "results": formatted_results,
            "total": total,
            "page": page,
            "page_size": page_size
        }
