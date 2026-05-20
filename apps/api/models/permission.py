from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class Permission(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    resource: str = Field(..., min_length=1, max_length=50)
    action: str = Field(..., min_length=1, max_length=50)
    menu_path: Optional[str] = None
    menu_label: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)


class PermissionCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    resource: str = Field(..., min_length=1, max_length=50)
    action: str = Field(..., min_length=1, max_length=50)
    menu_path: Optional[str] = None
    menu_label: Optional[str] = None


class PermissionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    resource: Optional[str] = Field(None, min_length=1, max_length=50)
    action: Optional[str] = Field(None, min_length=1, max_length=50)
    menu_path: Optional[str] = None
    menu_label: Optional[str] = None


class PermissionResponse(BaseModel):
    id: str
    name: str
    resource: str
    action: str
    menu_path: Optional[str] = None
    menu_label: Optional[str] = None
    created_at: datetime