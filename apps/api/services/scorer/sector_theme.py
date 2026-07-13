"""题材板块评分 (20分) — 本地 MongoDB 聚合，无外部 API 依赖"""
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

INDUSTRY_MAP = {
    "A01": "农业", "A02": "林业", "A03": "畜牧业", "A04": "渔业",
    "B06": "煤炭", "B07": "石油石化", "B08": "钢铁", "B09": "有色金属",
    "C13": "食品饮料", "C14": "食品饮料", "C15": "食品饮料",
    "C17": "纺织服装", "C18": "纺织服装",
    "C20": "轻工制造", "C21": "轻工制造", "C22": "轻工制造",
    "C23": "轻工制造", "C24": "轻工制造",
    "C25": "石油石化", "C26": "化工", "C27": "医药生物", "C28": "化工",
    "C29": "化工", "C30": "建筑材料", "C31": "钢铁", "C32": "有色金属",
    "C33": "机械设备", "C34": "机械设备", "C35": "机械设备",
    "C36": "汽车", "C37": "国防军工", "C38": "电力设备", "C39": "电子",
    "C40": "机械设备", "C41": "综合", "C42": "综合",
    "D44": "公用事业", "D45": "公用事业", "D46": "公用事业",
    "E47": "建筑装饰", "E48": "建筑装饰", "E49": "建筑装饰", "E50": "建筑装饰",
    "F51": "商贸零售", "F52": "商贸零售",
    "G53": "交通运输", "G54": "交通运输", "G55": "交通运输", "G56": "交通运输",
    "G58": "交通运输", "G59": "交通运输", "G60": "交通运输",
    "H61": "社会服务", "H62": "社会服务",
    "I63": "通信", "I64": "传媒", "I65": "计算机",
    "J66": "银行", "J67": "非银金融", "J68": "非银金融", "J69": "非银金融",
    "K70": "房地产",
    "L71": "社会服务", "L72": "社会服务",
    "M73": "社会服务", "M74": "社会服务", "M75": "综合",
    "N76": "公用事业", "N77": "公用事业", "N78": "综合",
    "P83": "社会服务",
    "Q84": "医药生物",
    "R86": "传媒", "R87": "传媒", "R88": "传媒",
    "S91": "综合",
}

_INDUSTRY_RANK_CACHE: Dict[str, Any] = {}


def clear_cache():
    _INDUSTRY_RANK_CACHE.clear()


def _extract_prefix(industry_code: str) -> str:
    if industry_code in INDUSTRY_MAP:
        return industry_code
    for prefix in sorted(INDUSTRY_MAP.keys(), key=len, reverse=True):
        if industry_code.startswith(prefix):
            return prefix
    return industry_code


def _compute_industry_rankings(date_str: str) -> Dict:
    """从 MongoDB 聚合计算行业平均涨跌幅排名，按 date_str 缓存"""
    if date_str in _INDUSTRY_RANK_CACHE:
        return _INDUSTRY_RANK_CACHE[date_str]

    from database import get_db
    db = get_db()

    sectors = list(db.sector_stocks.find({}, {"stock_code": 1, "sector_code": 1}))
    code_ind = {}
    for s in sectors:
        code = (s.get("stock_code") or "").split(".")[-1]
        sc = s.get("sector_code", "")
        prefix = _extract_prefix(sc) if sc else sc
        mapped = INDUSTRY_MAP.get(prefix)
        if code and mapped:
            code_ind[code] = mapped

    if not code_ind:
        result = {"rankings": {}, "_meta": {"total": 0}}
        _INDUSTRY_RANK_CACHE[date_str] = result
        return result

    pipeline = [
        {"$match": {"code": {"$in": list(code_ind.keys())}, "frequency": 9}},
        {"$sort": {"date": -1}},
        {"$group": {
            "_id": "$code",
            "closes": {"$push": "$close"},
        }},
        {"$project": {
            "close": {"$arrayElemAt": ["$closes", 0]},
            "prev_close": {"$arrayElemAt": ["$closes", 1]},
        }},
    ]

    ind_stocks = {}
    for row in db.stock_kline.aggregate(pipeline, allowDiskUse=True):
        code = row["_id"]
        ind = code_ind.get(code)
        if not ind:
            continue
        close = row.get("close")
        prev_close = row.get("prev_close")
        if close and prev_close and prev_close > 0:
            ret = (close - prev_close) / prev_close * 100
            ind_stocks.setdefault(ind, []).append(ret)

    ind_avg = {ind: sum(rets) / len(rets) for ind, rets in ind_stocks.items() if rets}
    ranked = sorted(ind_avg.items(), key=lambda x: x[1], reverse=True)

    result = {
        "rankings": {
            ind: {"rank": i + 1, "return": ret, "total": len(ranked)}
            for i, (ind, ret) in enumerate(ranked)
        },
        "_meta": {"total": len(ranked)},
    }
    _INDUSTRY_RANK_CACHE[date_str] = result
    return result


def score_sector_theme(code: str, date_str: str,
                       industry_code: Optional[str] = None,
                       concepts: Optional[List[str]] = None) -> Dict[str, Any]:
    breakdown = {"industry_rank": 0, "industry_return": 0}
    industry_return_val = None

    if industry_code is not None:
        try:
            rankings = _compute_industry_rankings(date_str)
            total_industries = rankings["_meta"]["total"]
            if total_industries > 0:
                prefix = _extract_prefix(industry_code)
                mapped_industry = INDUSTRY_MAP.get(prefix)
                if mapped_industry and mapped_industry in rankings["rankings"]:
                    info = rankings["rankings"][mapped_industry]
                    rank = info["rank"]
                    industry_return_val = info["return"]
                    if rank <= 5:
                        breakdown["industry_rank"] = 12
                    elif rank <= 10:
                        breakdown["industry_rank"] = 8
                    elif rank <= 20:
                        breakdown["industry_rank"] = 4
                    if industry_return_val > 3:
                        breakdown["industry_return"] = 5
                    elif industry_return_val > 1:
                        breakdown["industry_return"] = 3
        except Exception:
            logger.warning("industry ranking failed for %s", industry_code)

    total = sum(breakdown.values())
    if industry_return_val is not None and industry_return_val < -3:
        total = 0

    return {"total": total, "breakdown": breakdown}
