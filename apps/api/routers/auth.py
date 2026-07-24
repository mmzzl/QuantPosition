import logging
from datetime import timedelta, datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from bson import ObjectId

from database import get_db
from app.core.auth import AuthenticatedUser, get_password_hash, verify_password, create_access_token
from schemas.user import UserCreate, UserResponse
from schemas.token import Token, LoginRequest
from config.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["认证"])

security_scheme = HTTPBearer(auto_error=False)

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


def _check_account_locked(user: dict) -> None:
    """检查账户是否因多次登录失败被锁定"""
    locked_until = user.get("locked_until")
    if locked_until:
        if isinstance(locked_until, datetime) and locked_until > datetime.now():
            remaining = int((locked_until - datetime.now()).total_seconds() / 60)
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Account is locked, try again in {remaining} minutes"
            )


def _record_login_failure(db, user_id: str) -> None:
    """记录登录失败并锁定账户如果超过最大尝试次数"""
    try:
        user_oid = ObjectId(user_id)
    except Exception:
        return

    result = db.users.update_one(
        {"_id": user_oid},
        {"$inc": {"login_failed_attempts": 1}, "$set": {"updated_at": datetime.now()}}
    )
    if result.modified_count == 0:
        return

    user = db.users.find_one({"_id": user_oid})
    if not user:
        return
    attempts = user.get("login_failed_attempts", 0)
    if attempts >= MAX_LOGIN_ATTEMPTS:
        locked_until = datetime.now() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
        db.users.update_one(
            {"_id": user_oid},
            {"$set": {"locked_until": locked_until}}
        )
        logger.warning(f"Account {user_id} locked until {locked_until} after {attempts} failed attempts")


def _reset_login_attempts(db, user_id: str) -> None:
    """登录成功后重置失败计数和锁定状态"""
    try:
        user_oid = ObjectId(user_id)
    except Exception:
        return
    db.users.update_one(
        {"_id": user_oid},
        {"$set": {
            "login_failed_attempts": 0,
            "locked_until": None,
            "updated_at": datetime.now()
        }}
    )


@router.get("/me")
async def get_current_user_info(
    current_user: AuthenticatedUser = Depends(security_scheme)
):
    """获取当前登录用户信息"""
    db = get_db()
    try:
        user_oid = ObjectId(current_user.user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user ID")

    user = db.users.find_one({"_id": user_oid})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return UserResponse(
        id=str(user["_id"]),
        username=user["username"],
        email=user.get("email"),
        phone=user.get("phone"),
        is_active=user.get("is_active", True),
        created_at=user.get("created_at"),
        updated_at=user.get("updated_at")
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    """用户注册"""
    db = get_db()
    users_collection = db.users

    existing_user = users_collection.find_one({"username": user_data.username})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

    now = datetime.now()
    user_doc = {
        "username": user_data.username,
        "password_hash": get_password_hash(user_data.password),
        "is_active": True,
        "login_failed_attempts": 0,
        "created_at": now,
        "updated_at": now
    }
    if user_data.email:
        user_doc["email"] = user_data.email
    if user_data.phone:
        user_doc["phone"] = user_data.phone

    result = users_collection.insert_one(user_doc)
    user_id = str(result.inserted_id)

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

    user = users_collection.find_one({"username": login_data.username})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    _check_account_locked(user)

    if not verify_password(login_data.password, user["password_hash"]):
        _record_login_failure(db, str(user["_id"]))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    _reset_login_attempts(db, str(user["_id"]))

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )

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