import logging
import statistics
from typing import Dict, Any, List, Optional
from database import get_db
from utils.stock_api import get_stock_price
from services.transaction_service import TransactionService

logger = logging.getLogger(__name__)


class PortfolioService:

    @staticmethod
    def get_holdings_with_prices(user_id: str) -> List[Dict[str, Any]]:
        db = get_db()
        holdings = list(db.holdings.find({"user_id": user_id}))
        result = []
        for h in holdings:
            current_price = get_stock_price(h["code"])
            market_value = current_price * h["quantity"] if current_price else 0
            unrealized_pnl = (current_price - h["average_cost"]) * h["quantity"] if current_price else 0
            profit_rate = ((current_price - h["average_cost"]) / h["average_cost"] * 100) if current_price and h["average_cost"] > 0 else 0
            result.append({
                "id": str(h["_id"]),
                "user_id": h["user_id"],
                "code": h["code"],
                "name": h.get("name"),
                "quantity": h["quantity"],
                "average_cost": h["average_cost"],
                "current_price": current_price,
                "market_value": round(market_value, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "profit_rate": round(profit_rate, 2),
                "highest_price": h.get("highest_price"),
                "exit_rule": h.get("exit_rule"),
                "tier_triggered": h.get("tier_triggered"),
                "created_at": h["created_at"],
                "updated_at": h["updated_at"],
            })
        return result

    @staticmethod
    def get_portfolio(user_id: str) -> Dict[str, Any]:
        holdings = PortfolioService.get_holdings_with_prices(user_id)

        holdings_count = len(holdings)
        total_cost = sum(h["quantity"] * h["average_cost"] for h in holdings)
        market_value = sum(h.get("market_value", 0) or 0 for h in holdings)
        unrealized_pnl = sum(h.get("unrealized_pnl", 0) or 0 for h in holdings)
        profit_rate = round((unrealized_pnl / total_cost * 100), 2) if total_cost > 0 else 0
        realized_pnl = TransactionService.get_realized_pnl(user_id)

        return {
            "holdings_count": holdings_count,
            "total_cost": round(total_cost, 2),
            "market_value": round(market_value, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "profit_rate": round(profit_rate, 2),
            "realized_pnl": realized_pnl,
            "holdings": holdings,
        }

    @staticmethod
    def get_sector_exposure(user_id: str) -> Dict[str, Any]:
        db = get_db()
        holdings_list = list(db.holdings.find({"user_id": user_id}))
        if not holdings_list:
            return {"sectors": [], "holdings_count": 0}

        codes = [h["code"] for h in holdings_list]
        sectors = list(db.sector_stocks.find({"stock_code": {"$in": codes}}))
        sector_map = {s["stock_code"]: s.get("sector_name", "\u5176\u4ed6") for s in sectors}

        sector_total: Dict[str, float] = {}
        sector_holdings: Dict[str, list] = {}
        for h in holdings_list:
            code = h["code"]
            sec = sector_map.get(code, "\u5176\u4ed6")
            cost = h["quantity"] * h["average_cost"]
            sector_total[sec] = sector_total.get(sec, 0) + cost
            sector_holdings.setdefault(sec, []).append({
                "code": code,
                "name": h.get("name", ""),
                "cost": round(cost, 2),
            })

        total_cost = sum(sector_total.values()) or 1
        sector_list = [
            {
                "sector": sec,
                "cost": round(cost, 2),
                "pct": round(cost / total_cost * 100, 1),
                "stock_count": len(sector_holdings[sec]),
                "stocks": sector_holdings[sec],
            }
            for sec, cost in sorted(sector_total.items(), key=lambda x: -x[1])
        ]

        return {"sectors": sector_list, "holdings_count": len(holdings_list)}

    @staticmethod
    def get_correlation(user_id: str) -> Dict[str, Any]:
        db = get_db()
        holdings_list = list(db.holdings.find({"user_id": user_id}))
        if len(holdings_list) < 2:
            return {"error": "\u81f3\u5c11\u9700\u89812\u53ea\u6301\u80a1\u80a1\u7968"}

        codes = [h["code"] for h in holdings_list]
        names = {h["code"]: h.get("name", "") for h in holdings_list}

        min_bars: Optional[int] = None
        all_returns: Dict[str, List[float]] = {}
        for h in holdings_list:
            klines = list(db.stock_kline.find(
                {"code": h["code"], "frequency": 9},
                sort=[("date", -1)],
                limit=60,
            ))
            if len(klines) < 10:
                continue
            klines.reverse()
            prices = [k["close"] for k in klines]
            returns = [
                (prices[i] - prices[i - 1]) / prices[i - 1]
                for i in range(1, len(prices))
            ]
            all_returns[h["code"]] = returns
            if min_bars is None or len(returns) < min_bars:
                min_bars = len(returns)

        if not all_returns or len(all_returns) < 2:
            return {"error": "K\u7ebf\u6570\u636e\u4e0d\u8db3"}

        codes_with_data = list(all_returns.keys())

        def pearson(x: List[float], y: List[float]) -> float:
            n = len(x)
            mx = sum(x) / n
            my = sum(y) / n
            num = sum((x[i] - mx) * (y[i] - my) for i in range(n))
            den = (sum((xi - mx) ** 2 for xi in x) * sum((yi - my) ** 2 for yi in y)) ** 0.5
            return round(num / den, 4) if den else 0

        matrix: List[Dict[str, Any]] = []
        for c1 in codes_with_data:
            row: Dict[str, Any] = {"code": c1, "name": names.get(c1, "")}
            for c2 in codes_with_data:
                r1 = all_returns[c1][:min_bars]
                r2 = all_returns[c2][:min_bars]
                row[c2] = pearson(r1, r2)
            matrix.append(row)

        return {"codes": codes_with_data, "matrix": matrix}

    @staticmethod
    def get_pnl(user_id: str) -> Dict[str, Any]:
        holdings = PortfolioService.get_holdings_with_prices(user_id)
        total_unrealized_pnl = sum(h.get("unrealized_pnl", 0) or 0 for h in holdings)
        realized_pnl = TransactionService.get_realized_pnl(user_id)
        total_pnl = round(total_unrealized_pnl + realized_pnl, 2)

        return {
            "unrealized_pnl": round(total_unrealized_pnl, 2),
            "realized_pnl": realized_pnl,
            "total_pnl": total_pnl,
        }

    @staticmethod
    def batch_prices(codes: List[str]) -> Dict[str, Any]:
        from utils.stock_api import SinaStockAPI
        prices: Dict[str, Dict[str, Any]] = {}
        for code in codes:
            try:
                info = SinaStockAPI.get_stock_info(code)
                if info:
                    prices[code] = {
                        "price": info.get("price"),
                        "name": info.get("name"),
                        "open": info.get("open"),
                        "high": info.get("high"),
                        "low": info.get("low"),
                        "volume": info.get("volume"),
                        "amount": info.get("amount"),
                    }
            except Exception:
                pass
        return {"prices": prices}