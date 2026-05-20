from bson import ObjectId
from datetime import datetime
from typing import List, Optional

from database import get_db
from models.permission import PermissionCreate, PermissionUpdate


class PermissionService:
    """权限服务"""

    @staticmethod
    def create_permission(perm_data: PermissionCreate) -> dict:
        """创建权限"""
        db = get_db()
        perms_collection = db.permissions

        # 检查权限名是否已存在
        existing = perms_collection.find_one({"name": perm_data.name})
        if existing:
            raise ValueError("Permission name already exists")

        perm_doc = {
            "name": perm_data.name,
            "resource": perm_data.resource,
            "action": perm_data.action,
            "created_at": datetime.now()
        }

        result = perms_collection.insert_one(perm_doc)
        perm_doc["_id"] = result.inserted_id

        return perm_doc

    @staticmethod
    def get_permission_by_id(perm_id: str) -> Optional[dict]:
        """根据ID获取权限"""
        db = get_db()
        perms_collection = db.permissions

        try:
            perm = perms_collection.find_one({"_id": ObjectId(perm_id)})
        except Exception:
            return None

        return perm

    @staticmethod
    def get_permissions(skip: int = 0, limit: int = 100) -> List[dict]:
        """获取权限列表"""
        db = get_db()
        perms_collection = db.permissions

        return list(perms_collection.find().skip(skip).limit(limit))

    @staticmethod
    def update_permission(perm_id: str, perm_data: PermissionUpdate) -> Optional[dict]:
        """更新权限"""
        db = get_db()
        perms_collection = db.permissions

        update_data = {}
        if perm_data.name is not None:
            update_data["name"] = perm_data.name
        if perm_data.resource is not None:
            update_data["resource"] = perm_data.resource
        if perm_data.action is not None:
            update_data["action"] = perm_data.action

        if not update_data:
            return PermissionService.get_permission_by_id(perm_id)

        result = perms_collection.update_one(
            {"_id": ObjectId(perm_id)},
            {"$set": update_data}
        )

        if result.matched_count == 0:
            return None

        return PermissionService.get_permission_by_id(perm_id)

    @staticmethod
    def delete_permission(perm_id: str) -> bool:
        """删除权限"""
        db = get_db()
        perms_collection = db.permissions

        result = perms_collection.delete_one({"_id": ObjectId(perm_id)})
        return result.deleted_count > 0

    @staticmethod
    def get_permissions_by_ids(perm_ids: List[str]) -> List[dict]:
        """根据ID列表获取权限"""
        db = get_db()
        perms_collection = db.permissions

        object_ids = []
        for pid in perm_ids:
            try:
                object_ids.append(ObjectId(pid))
            except Exception:
                continue

        return list(perms_collection.find({"_id": {"$in": object_ids}}))