from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class PermissionCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    resource: str = Field(..., min_length=1, max_length=50)
    action: str = Field(..., min_length=1, max_length=50)


class PermissionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    resource: Optional[str] = Field(None, min_length=1, max_length=50)
    action: Optional[str] = Field(None, min_length=1, max_length=50)


class PermissionResponse(BaseModel):
    id: str
    name: str
    resource: str
    action: str
    created_at: datetime

    class Config:
        from_attributes = True