from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class BacktestRequest(BaseModel):
    model_config = {"extra": "forbid"}
    days_back: int = Field(default=360, ge=30, le=730, description="回测天数")
    initial_cash: float = Field(default=100000, ge=10000, description="初始资金")
    commission: float = Field(default=0.001, ge=0, le=0.05, description="佣金比例")
    max_positions: int = Field(default=5, ge=1, le=20, description="最大持仓数")
    max_hold_days: int = Field(default=60, ge=10, le=999, description="最长持有天数")
    cooldown_days: int = Field(default=1, ge=1, le=30, description="冷却天数")


class TradeRecordResponse(BaseModel):
    code: str
    name: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    pnl_pct: float
    hold_days: int
    reason: str
    triggered_rules: List[str] = []
    score_detail: Optional[Dict[str, Any]] = None


class ProgressInfo(BaseModel):
    current: int = 0
    total: int = 0
    status: str = ""
    detail: str = ""


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str = "PENDING"
    progress: Optional[ProgressInfo] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BacktestTaskResponse(BaseModel):
    task_id: str


class BacktestSubmitResponse(BaseModel):
    task_id: str
    message: str = "回测任务已提交，请轮询任务状态"
