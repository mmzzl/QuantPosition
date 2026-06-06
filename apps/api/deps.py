from typing import Optional
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from bson import ObjectId

from config.config import settings
from app.core.auth import AuthenticatedUser

security_scheme = HTTPBearer(auto_error=False)

_db = None


def get_db():
    """获取数据库连接"""
    global _db
    if _db is None:
        from database import get_db as _get_db
        _db = _get_db()
    return _db


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建JWT访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """解码JWT令牌"""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme)
) -> AuthenticatedUser:
    """获取当前用户"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception

    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise credentials_exception

    username: str = payload.get("sub")
    user_id: str = payload.get("user_id")

    if username is None or user_id is None:
        raise credentials_exception

    return AuthenticatedUser(user_id=user_id, username=username, is_active=True)


async def get_current_active_user(
    current_user: AuthenticatedUser = Depends(get_current_user)
) -> AuthenticatedUser:
    """获取当前活跃用户"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def require_role_edit_permission(
    target_role_id: str,
    current_user: AuthenticatedUser
):
    """检查当前用户是否有权限编辑目标角色"""
    from services.role_service import RoleService
    from database import get_db

    db = get_db()
    users_collection = db.users

    target_role = RoleService.get_role_by_id(target_role_id)
    if not target_role:
        raise HTTPException(status_code=404, detail="角色不存在")

    user = users_collection.find_one({"_id": ObjectId(current_user.user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    roles = RoleService.get_user_roles(current_user.user_id)
    role_hierarchy = {"super_admin": 3, "system_admin": 2, "normal_admin": 1}
    current_role_type = "user"
    current_level = 0
    for r in roles:
        preset_key = r.get("preset_key")
        level = role_hierarchy.get(preset_key, 0)
        if level > current_level:
            current_level = level
            current_role_type = preset_key or "user"

    if not RoleService.can_edit_role(current_role_type, target_role):
        raise HTTPException(
            status_code=403,
            detail="无权限修改此角色"
        )

    return target_role