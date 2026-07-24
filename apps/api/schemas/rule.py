from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class RuleType(str, Enum):
    buy = "buy"
    sell = "sell"
    risk = "risk"


class RuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: RuleType
    priority: int = Field(3, ge=1, le=10)
    weight: float = Field(0.0, ge=0.0, le=1.0)
    condition: str = Field(..., min_length=1)
    enabled: bool = True


class RuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    type: Optional[RuleType] = None
    priority: Optional[int] = Field(None, ge=1, le=10)
    weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    condition: Optional[str] = None
    enabled: Optional[bool] = None


class ConditionValidate(BaseModel):
    condition: str


class ExploreRequest(BaseModel):
    phases: List[str] = ["template", "llm", "genetic"]


class ValidateRequest(BaseModel):
    scope: str = "all"
    limit: int = Field(500, ge=1, le=5000)
    backtest_days: int = Field(360, ge=30, le=3650)
    max_stocks: int = Field(500, ge=10, le=5000)


class BatchDelete(BaseModel):
    rule_ids: List[int]