from bson import ObjectId
from datetime import datetime
from typing import List, Optional

from database import get_db
from app.core.auth import get_password_hash, verify_password
from models.user import UserCreate, UserUpdate, UserResponse


class UserService:
    """用户服务"""

    @staticmethod
    def create_user(user_data: UserCreate) -> UserResponse:
        """创建用户"""
        db = get_db()
        users_collection = db.users

        # 检查用户名是否已存在
        existing_user = users_collection.find_one({"username": user_data.username})
        if existing_user:
            raise ValueError("Username already exists")

        # 创建用户
        now = datetime.now()
        user_doc = {
            "username": user_data.username,
            "password_hash": get_password_hash(user_data.password),
            "email": user_data.email,
            "phone": user_data.phone,
            "is_active": True,
            "created_at": now,
            "updated_at": now
        }

        result = users_collection.insert_one(user_doc)

        return UserResponse(
            id=str(result.inserted_id),
            username=user_data.username,
            email=user_data.email,
            phone=user_data.phone,
            is_active=True,
            created_at=now,
            updated_at=now
        )

    @staticmethod
    def get_user_by_id(user_id: str) -> Optional[dict]:
        """根据ID获取用户"""
        db = get_db()
        users_collection = db.users

        try:
            user = users_collection.find_one({"_id": ObjectId(user_id)})
        except Exception:
            return None

        return user

    @staticmethod
    def get_user_by_username(username: str) -> Optional[dict]:
        """根据用户名获取用户"""
        db = get_db()
        users_collection = db.users

        return users_collection.find_one({"username": username})

    @staticmethod
    def get_users(skip: int = 0, limit: int = 100) -> List[dict]:
        """获取用户列表"""
        db = get_db()
        users_collection = db.users

        users = list(users_collection.find().skip(skip).limit(limit))
        return users

    @staticmethod
    def update_user(user_id: str, user_data: UserUpdate) -> Optional[dict]:
        """更新用户"""
        db = get_db()
        users_collection = db.users

        update_data = {}
        if user_data.email is not None:
            update_data["email"] = user_data.email
        if user_data.phone is not None:
            update_data["phone"] = user_data.phone
        if user_data.is_active is not None:
            update_data["is_active"] = user_data.is_active

        if not update_data:
            return UserService.get_user_by_id(user_id)

        update_data["updated_at"] = datetime.now()

        result = users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )

        if result.matched_count == 0:
            return None

        return UserService.get_user_by_id(user_id)

    @staticmethod
    def delete_user(user_id: str) -> bool:
        """删除用户"""
        db = get_db()
        users_collection = db.users

        result = users_collection.delete_one({"_id": ObjectId(user_id)})
        return result.deleted_count > 0

    @staticmethod
    def get_user_roles(user_id: str) -> List[dict]:
        """获取用户的所有角色"""
        from services.role_service import RoleService
        return RoleService.get_user_roles(user_id)