from datetime import timedelta, datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from bson import ObjectId

from database import get_db
from app.core.auth import get_password_hash, verify_password, create_access_token
from schemas.user import UserCreate, UserResponse
from schemas.token import Token, LoginRequest
from config.config import settings

router = APIRouter(prefix="/auth", tags=["认证"])

security_scheme = HTTPBearer(auto_error=False)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    """用户注册"""
    db = get_db()
    users_collection = db.users

    # 检查用户名是否已存在
    existing_user = users_collection.find_one({"username": user_data.username})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

    # 创建用户 - 只包含有值的字段，避免 null 触发唯一索引冲突
    now = datetime.now()
    user_doc = {
        "username": user_data.username,
        "password_hash": get_password_hash(user_data.password),
        "is_active": True,
        "created_at": now,
        "updated_at": now
    }
    if user_data.email:
        user_doc["email"] = user_data.email
    if user_data.phone:
        user_doc["phone"] = user_data.phone

    result = users_collection.insert_one(user_doc)
    user_id = str(result.inserted_id)

    # 默认分配普通管理员角色
    roles_collection = db.roles
    user_roles_collection = db.user_roles
    normal_admin_role = roles_collection.find_one({"preset_key": "normal_admin"})
    if normal_admin_role:
        user_roles_collection.insert_one({
            "user_id": user_id,
            "role_id": str(normal_admin_role["_id"])
        })

    return UserResponse(
        id=user_id,
        username=user_data.username,
        email=user_data.email,
        phone=user_data.phone,
        is_active=True,
        created_at=now,
        updated_at=now
    )


@router.post("/login", response_model=Token)
async def login(login_data: LoginRequest):
    """用户登录"""
    db = get_db()
    users_collection = db.users

    # 查找用户
    user = users_collection.find_one({"username": login_data.username})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 验证密码
    if not verify_password(login_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 检查用户是否激活
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )

    # 从系统设置读取 session 过期时长，兼容配置文件
    expire_minutes = settings.jwt_access_token_expire_minutes
    try:
        sys_settings = db.system_settings.find_one({"_id": "global"})
        if sys_settings and sys_settings.get("session_expire_minutes"):
            expire_minutes = sys_settings["session_expire_minutes"]
    except Exception:
        pass

    access_token_expires = timedelta(minutes=expire_minutes)
    access_token = create_access_token(
        data={"sub": user["username"], "user_id": str(user["_id"])},
        expires_delta=access_token_expires
    )

    # 从 user_roles 获取角色
    user_roles_collection = db.user_roles
    roles_collection = db.roles
    user_role = "user"
    user_role_doc = user_roles_collection.find_one({"user_id": str(user["_id"])})
    if user_role_doc:
        role_doc = roles_collection.find_one({"_id": ObjectId(user_role_doc["role_id"])})
        if role_doc:
            user_role = role_doc.get("preset_key") or role_doc.get("name")
    
    return Token(
        access_token=access_token, 
        token_type="bearer",
        user_id=str(user["_id"]),
        role=user_role
    )