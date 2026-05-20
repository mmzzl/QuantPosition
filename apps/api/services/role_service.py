from bson import ObjectId
from datetime import datetime
from typing import List, Optional

from database import get_db
from models.role import RoleCreate, RoleUpdate, PRESET_ROLE_KEYS


class RoleService:
    """角色服务"""

    @staticmethod
    def create_role(role_data: RoleCreate) -> dict:
        """创建角色"""
        db = get_db()
        roles_collection = db.roles

        existing = roles_collection.find_one({"name": role_data.name})
        if existing:
            raise ValueError("Role name already exists")

        now = datetime.now()
        role_doc = {
            "name": role_data.name,
            "description": role_data.description,
            "role_type": "custom",
            "parent_roles": role_data.parent_roles,
            "permission_ids": role_data.permission_ids,
            "locked": False,
            "created_at": now,
            "updated_at": now
        }

        result = roles_collection.insert_one(role_doc)
        role_doc["_id"] = result.inserted_id

        return role_doc

    @staticmethod
    def get_role_by_id(role_id: str) -> Optional[dict]:
        """根据ID获取角色"""
        db = get_db()
        roles_collection = db.roles

        try:
            role = roles_collection.find_one({"_id": ObjectId(role_id)})
        except Exception:
            return None

        return role

    @staticmethod
    def get_roles(skip: int = 0, limit: int = 100) -> List[dict]:
        """获取角色列表"""
        db = get_db()
        roles_collection = db.roles

        return list(roles_collection.find().skip(skip).limit(limit))

    @staticmethod
    def update_role(role_id: str, role_data: RoleUpdate) -> Optional[dict]:
        """更新角色"""
        db = get_db()
        roles_collection = db.roles

        target_role = roles_collection.find_one({"_id": ObjectId(role_id)})
        if not target_role:
            return None

        if target_role.get("locked"):
            raise ValueError("This role is locked and cannot be updated")

        if target_role.get("preset_key") == "super_admin":
            raise ValueError("Super admin role cannot be updated")

        update_data = {}
        if role_data.name is not None:
            update_data["name"] = role_data.name
        if role_data.description is not None:
            update_data["description"] = role_data.description
        if role_data.parent_roles is not None:
            update_data["parent_roles"] = role_data.parent_roles
        if role_data.permission_ids is not None:
            update_data["permission_ids"] = role_data.permission_ids

        if not update_data:
            return RoleService.get_role_by_id(role_id)

        update_data["updated_at"] = datetime.now()

        result = roles_collection.update_one(
            {"_id": ObjectId(role_id)},
            {"$set": update_data}
        )

        if result.matched_count == 0:
            return None

        return RoleService.get_role_by_id(role_id)

    @staticmethod
    def delete_role(role_id: str) -> bool:
        """删除角色"""
        db = get_db()
        roles_collection = db.roles

        role = roles_collection.find_one({"_id": ObjectId(role_id)})
        if not role:
            return False

        if role.get("role_type") == "preset":
            raise ValueError("Cannot delete preset roles")

        if role.get("locked"):
            raise ValueError("Cannot delete locked roles")

        RoleService.handle_role_deletion_cascade(role_id)

        result = roles_collection.delete_one({"_id": ObjectId(role_id)})
        return result.deleted_count > 0

    @staticmethod
    def get_effective_permissions(role_id: str, visited: List[str] = None) -> List[str]:
        """获取角色的有效权限（包含继承链）"""
        if visited is None:
            visited = []

        if role_id in visited:
            return []

        visited = visited + [role_id]
        if len(visited) > 5:
            return []

        role = RoleService.get_role_by_id(role_id)
        if not role:
            return []

        all_permissions = set(role.get("permission_ids", []))

        for parent_id in role.get("parent_roles", []):
            try:
                parent_perms = RoleService.get_effective_permissions(parent_id, visited)
                all_permissions.update(parent_perms)
            except Exception:
                continue

        return list(all_permissions)

    @staticmethod
    def detect_inheritance_cycle(role_id: str, new_parent: str, visited: List[str] = None) -> bool:
        """检测是否形成循环继承"""
        if visited is None:
            visited = []

        if new_parent == role_id:
            return True

        if new_parent in visited:
            return False

        visited = visited + [new_parent]
        parent_role = RoleService.get_role_by_id(new_parent)
        if not parent_role:
            return False

        for grandparent_id in parent_role.get("parent_roles", []):
            if RoleService.detect_inheritance_cycle(role_id, grandparent_id, visited):
                return True

        return False

    @staticmethod
    def can_edit_role(current_user_role_type: str, target_role: dict) -> bool:
        """检查当前用户是否有权限编辑目标角色"""
        if target_role.get("locked"):
            return False

        if target_role.get("preset_key") == "super_admin":
            return False

        role_hierarchy = {"super_admin": 3, "system_admin": 2, "normal_admin": 1}
        current_level = role_hierarchy.get(current_user_role_type, 0)
        target_level = role_hierarchy.get(target_role.get("preset_key", ""), 0)

        return current_level > target_level

    @staticmethod
    def init_preset_roles():
        """初始化预设角色"""
        db = get_db()
        roles_collection = db.roles
        permissions_collection = db.permissions

        all_permission_ids = [str(p["_id"]) for p in permissions_collection.find()]

        preset_roles = [
            {
                "name": "超级管理员",
                "preset_key": "super_admin",
                "role_type": "preset",
                "locked": True,
                "description": "拥有系统全部权限，不可编辑",
                "permission_ids": all_permission_ids
            },
            {
                "name": "系统管理员",
                "preset_key": "system_admin",
                "role_type": "preset",
                "locked": False,
                "description": "可管理用户、角色和持仓"
            },
            {
                "name": "普通管理员",
                "preset_key": "normal_admin",
                "role_type": "preset",
                "locked": False,
                "description": "可查看和编辑持仓"
            }
        ]

        for preset in preset_roles:
            existing = roles_collection.find_one({"preset_key": preset["preset_key"]})
            if not existing:
                preset["parent_roles"] = []
                if "permission_ids" not in preset:
                    preset["permission_ids"] = []
                preset["created_at"] = datetime.now()
                preset["updated_at"] = datetime.now()
                roles_collection.insert_one(preset)
            else:
                if not existing.get("permission_ids") or len(existing.get("permission_ids", [])) == 0:
                    roles_collection.update_one(
                        {"_id": existing["_id"]},
                        {"$set": {"permission_ids": all_permission_ids, "updated_at": datetime.now()}}
                    )

    @staticmethod
    def add_user_to_role(user_id: str, role_id: str) -> bool:
        """将用户添加到角色"""
        db = get_db()
        user_roles_collection = db.user_roles

        existing = user_roles_collection.find_one({
            "user_id": user_id,
            "role_id": role_id
        })

        if existing:
            return True

        user_roles_collection.insert_one({
            "user_id": user_id,
            "role_id": role_id,
            "created_at": datetime.now()
        })

        return True

    @staticmethod
    def remove_user_from_role(user_id: str, role_id: str) -> bool:
        """将用户从角色移除"""
        db = get_db()
        user_roles_collection = db.user_roles

        result = user_roles_collection.delete_one({
            "user_id": user_id,
            "role_id": role_id
        })

        return result.deleted_count > 0

    @staticmethod
    def get_user_roles(user_id: str) -> List[dict]:
        """获取用户的所有角色"""
        db = get_db()
        user_roles_collection = db.user_roles
        roles_collection = db.roles

        user_roles = list(user_roles_collection.find({"user_id": user_id}))
        role_ids = [ur["role_id"] for ur in user_roles]

        object_ids = []
        for rid in role_ids:
            try:
                object_ids.append(ObjectId(rid))
            except Exception:
                continue

        return list(roles_collection.find({"_id": {"$in": object_ids}}))

    @staticmethod
    def handle_role_deletion_cascade(role_id: str) -> dict:
        """处理角色删除时的级联更新"""
        db = get_db()
        roles_collection = db.roles

        child_roles = list(roles_collection.find({"parent_roles": role_id}))

        if child_roles:
            for child in child_roles:
                new_parent_roles = [p for p in child.get("parent_roles", []) if p != role_id]
                roles_collection.update_one(
                    {"_id": child["_id"]},
                    {"$set": {"parent_roles": new_parent_roles, "updated_at": datetime.now()}}
                )

        return {"updated_roles": len(child_roles)}

    @staticmethod
    def get_role_permissions(role_id: str) -> List[dict]:
        """获取角色的所有权限"""
        db = get_db()
        roles_collection = db.roles
        perms_collection = db.permissions

        role = roles_collection.find_one({"_id": ObjectId(role_id)})
        if not role:
            return []

        perm_ids = role.get("permission_ids", [])
        object_ids = []
        for pid in perm_ids:
            try:
                object_ids.append(ObjectId(pid))
            except Exception:
                continue

        return list(perms_collection.find({"_id": {"$in": object_ids}}))