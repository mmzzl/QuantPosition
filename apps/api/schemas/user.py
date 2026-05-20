from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=20, pattern=r'^[a-zA-Z0-9_]+$')
    password: str = Field(..., min_length=6)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: Optional[str] = "user"
    is_active: Optional[bool] = True


class ChangePassword(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)


class UserResponse(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str = "user"
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserInDB(BaseModel):
    id: str
    username: str
    password_hash: str
    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime