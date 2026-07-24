from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class RuleType(str, Enum):
    buy = "buy"
    sell = "sell"
    risk = "risk"


class Rule(BaseModel):
    id: str = ""
    name: str
    type: RuleType
    priority: int = 3
    weight: float = 0.0
    condition: str = ""
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RuleCreate(BaseModel):
    name: str
    type: RuleType
    priority: int = 3
    weight: float = 0.0
    condition: str = ""
    enabled: bool = True


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[RuleType] = None
    priority: Optional[int] = None
    weight: Optional[float] = None
    condition: Optional[str] = None
    enabled: Optional[bool] = None


class ConditionValidate(BaseModel):
    condition: str


class ExploreRequest(BaseModel):
    phases: List[str] = ["template", "llm", "genetic"]


class ValidateRequest(BaseModel):
    scope: str = "all"
    limit: int = 500
    backtest_days: int = 360
    max_stocks: int = 500


class BatchDelete(BaseModel):
    rule_ids: List[int]


class RuleListResponse(BaseModel):
    items: List[Rule]
    total: int


class CandidateRule(BaseModel):
    id: str = ""
    source: str = ""
    name: Optional[str] = None
    buy_condition: str = ""
    sell_condition: str = ""
    risk_condition: str = ""
    priority: int = 3
    weight: float = 0.35
    sharpe: Optional[float] = None
    win_rate: Optional[float] = None
    total_return: Optional[float] = None
    trades: Optional[int] = None
    composite_score: Optional[float] = None
    validated: bool = False
    validation_round: int = 0
    created_at: Optional[datetime] = None