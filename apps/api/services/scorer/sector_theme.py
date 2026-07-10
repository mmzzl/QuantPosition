"""题材板块评分 (20分)"""
import logging
from typing import Dict, Any, Optional, List

import akshare

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

_cache: Dict[str, Any] = {}


def clear_cache():
    _cache.clear()


def _extract_prefix(industry_code: str) -> str:
    if industry_code in INDUSTRY_MAP:
        return industry_code
    for i in range(1, len(industry_code)):
        if industry_code[i:].isdigit() and not industry_code[:i].isdigit():
            return industry_code[:i]
    return industry_code


def score_sector_theme(code: str, date_str: str,
                       industry_code: Optional[str] = None,
                       concepts: Optional[List[str]] = None) -> Dict[str, Any]:
    breakdown = {"industry_rank": 0, "industry_return": 0, "concept": 0}
    industry_return_val = None

    if concepts is None:
        concepts = []

    # 3.1 板块资金热度 (12pts) & 3.2 板块指数涨幅 (5pts)
    if industry_code is not None:
        prefix = _extract_prefix(industry_code)
        mapped_industry = INDUSTRY_MAP.get(prefix)
        try:
            cache_key = "industry_flow:3日排行"
            if cache_key not in _cache:
                _cache[cache_key] = akshare.stock_fund_flow_industry("3日排行")
            df_ind = _cache[cache_key]
            if mapped_industry is not None and df_ind is not None and not df_ind.empty:
                match = df_ind[df_ind["行业"].astype(str).str.contains(mapped_industry)]
                if not match.empty:
                    row = match.iloc[0]
                    rank = match.index[0] + 1
                    industry_return_val = float(row["行业-涨跌幅"])
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
            logger.warning("stock_fund_flow_industry failed for %s", industry_code)

    # 3.3 概念热点 (3pts)
    if concepts:
        try:
            cache_key_concept = "concept_flow:3日排行"
            if cache_key_concept not in _cache:
                _cache[cache_key_concept] = akshare.stock_fund_flow_concept("3日排行")
            df_concept = _cache[cache_key_concept]
            if df_concept is not None and not df_concept.empty:
                top5 = set(df_concept["概念"].astype(str).head(5).tolist())
                if any(c in top5 for c in concepts):
                    breakdown["concept"] = 3
        except Exception:
            logger.warning("stock_fund_flow_concept failed")

    total = sum(breakdown.values())
    if industry_return_val is not None and industry_return_val < -3:
        total = 0

    return {"total": total, "breakdown": breakdown}
