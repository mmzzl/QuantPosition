from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class BacktestTask(BaseModel):
    task_id: str = Field(..., description="Celery task ID")
    status: str = Field(default="PENDING", description="PENDING/RUNNING/SUCCESS/FAILURE")
    params: Dict[str, Any] = Field(default_factory=dict, description="回测参数")
    submitted_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class TradeRecord(BaseModel):
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
    shares: Optional[int] = None
    commission: Optional[float] = None


class BacktestMetrics(BaseModel):
    annual_return: float = Field(..., description="年化收益率 (CAGR)")
    sharpe_ratio: float = Field(..., description="夏普比率")
    max_drawdown: float = Field(..., description="最大回撤 (%)")
    win_rate: float = Field(..., description="胜率 (%)")
    total_return: float = Field(..., description="总收益率 (%)")
    total_trades: int = Field(..., description="总交易次数")
    avg_hold_days: Optional[float] = None


class BacktestResult(BaseModel):
    task_id: str
    strategy: str = "portfolio_rule_engine"
    status: str = "SUCCESS"
    equity_curve: List[float] = Field(default_factory=list, description="每日净值序列")
    equity_dates: List[str] = Field(default_factory=list, description="对应日期")
    trades: List[TradeRecord] = Field(default_factory=list)
    metrics: Optional[BacktestMetrics] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    processed: int = 0
    skipped: int = 0
    unique_stocks: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
