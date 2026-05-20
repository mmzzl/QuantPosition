from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class RoleCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    description: Optional[str] = None
    parent_roles: List[str] = []
    permission_ids: List[str] = []


class RoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=50)
    description: Optional[str] = None
    parent_roles: Optional[List[str]] = None
    permission_ids: Optional[List[str]] = None


class RoleResponse(BaseModel):
    id: str
    name: str
    role_type: str = "custom"
    preset_key: Optional[str] = None
    description: Optional[str] = None
    parent_roles: List[str] = []
    permission_ids: List[str] = []
    locked: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True