from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class ExitRule(BaseModel):
    exit_strategy: str = Field(default="tiered", description="策略: tiered/trailing/fixed")
    stop_loss: float = Field(default=0.05, description="止损比例")
    profit_target: float = Field(default=0.10, description="止盈目标")
    trailing_stop_pct: float = Field(default=0.03, description="追踪止损比例")
    tier_profits: List[float] = Field(default=[0.03, 0.05, 0.08, 0.10], description="分档盈利")
    tier_sell_pcts: List[float] = Field(default=[0.25, 0.25, 0.25, 0.25], description="分档卖出比例")


class Holding(BaseModel):
    user_id: str = Field(..., description="用户ID")
    code: str = Field(..., description="股票代码", min_length=6, max_length=6)
    name: Optional[str] = Field(None, description="股票名称")
    quantity: int = Field(..., description="持仓数量", gt=0)
    average_cost: float = Field(..., description="平均成本价", gt=0)
    highest_price: Optional[float] = Field(None, description="最高价")
    exit_rule: Optional[ExitRule] = Field(None, description="卖出规则")
    tier_triggered: Optional[List[bool]] = Field(default=[False, False, False, False], description="分档触发状态")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class HoldingCreate(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)
    name: Optional[str] = None
    quantity: int = Field(..., gt=0)
    average_cost: float = Field(..., gt=0)


class HoldingUpdate(BaseModel):
    name: Optional[str] = None
    quantity: Optional[int] = Field(None, gt=0)
    average_cost: Optional[float] = Field(None, gt=0)
    highest_price: Optional[float] = None
    exit_rule: Optional[ExitRule] = None
    tier_triggered: Optional[List[bool]] = None


class SellRequest(BaseModel):
    quantity: int = Field(..., gt=0)
    price: float = Field(..., gt=0)


class ExitRuleRequest(BaseModel):
    exit_strategy: str = Field(default="tiered")
    stop_loss: float = Field(default=0.05)
    profit_target: float = Field(default=0.10)
    trailing_stop_pct: float = Field(default=0.03)
    tier_profits: List[float] = Field(default=[0.03, 0.05, 0.08, 0.10])
    tier_sell_pcts: List[float] = Field(default=[0.25, 0.25, 0.25, 0.25])


class HoldingResponse(BaseModel):
    id: str
    user_id: str
    code: str
    name: Optional[str] = None
    quantity: int
    average_cost: float
    highest_price: Optional[float] = None
    exit_rule: Optional[dict] = None
    tier_triggered: Optional[List[bool]] = None
    created_at: datetime
    updated_at: datetime
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    profit_rate: Optional[float] = None