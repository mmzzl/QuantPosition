from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Transaction(BaseModel):
    user_id: str = Field(..., description="用户ID")
    code: str = Field(..., description="股票代码")
    type: str = Field(..., description="类型: buy/sell")
    quantity: int = Field(..., description="数量", gt=0)
    price: float = Field(..., description="价格", gt=0)
    total: float = Field(..., description="总额")
    created_at: datetime = Field(default_factory=datetime.now)


class TransactionCreate(BaseModel):
    code: str
    type: str = Field(..., pattern="^(buy|sell)$")
    quantity: int = Field(..., gt=0)
    price: float = Field(..., gt=0)


class TransactionResponse(BaseModel):
    id: str
    user_id: str
    code: str
    type: str
    quantity: int
    price: float
    total: float
    created_at: datetime