from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class User(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    password_hash: str
    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    password: str = Field(..., min_length=6)
    email: Optional[str] = None
    phone: Optional[str] = None


class UserUpdate(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None


class UserInDB(BaseModel):
    id: str
    username: str
    password_hash: str
    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class UserResponse(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime