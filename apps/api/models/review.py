from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ReviewStockItem(BaseModel):
    code: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    score: float = Field(..., description="综合评分")
    grade: str = Field(..., description="评级 S/A/B/C")
    conclusion: str = Field(..., description="结论: 持有/卖出/观望")
    pattern: str = Field(..., description="分时形态")
    intention: str = Field(..., description="主力意图")
    reason: str = Field(..., description="核心推荐理由")
    strategy: str = Field(..., description="次日策略")


class SectorAnalysis(BaseModel):
    sector_name: str = Field(..., description="板块名称")
    avg_score: float = Field(..., description="板块平均评分")
    stock_count: int = Field(..., description="板块内股票数")
    top_stocks: List[str] = Field(default_factory=list, description="板块内评分Top 3股票代码")


class ReviewReport(BaseModel):
    date: str = Field(..., description="复盘日期 YYYY-MM-DD")
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    summary: str = Field(..., description="市场综述")
    top_stocks: List[ReviewStockItem] = Field(default_factory=list, description="评分 Top N 个股")
    sector_analysis: List[SectorAnalysis] = Field(default_factory=list, description="板块热度排序")
    holdings_analyzed: int = Field(0, description="分析的持仓数量")
    total_scored: int = Field(0, description="评分的股票总数")
