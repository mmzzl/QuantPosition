from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ReviewStockItemResponse(BaseModel):
    code: str
    name: str
    score: float
    grade: str
    conclusion: str
    pattern: str
    intention: str
    reason: str
    strategy: str


class SectorAnalysisResponse(BaseModel):
    sector_name: str
    avg_score: float
    stock_count: int
    top_stocks: List[str]


class ReviewReportResponse(BaseModel):
    date: str
    generated_at: str
    summary: str
    top_stocks: List[ReviewStockItemResponse]
    sector_analysis: List[SectorAnalysisResponse]
    holdings_analyzed: int
    total_scored: int


class ReviewListResponse(BaseModel):
    total: int
    items: List[ReviewReportResponse]
