from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from bson import ObjectId

from database import get_db
from app.core.auth import AuthenticatedUser, get_current_user
from services.role_service import RoleService

router = APIRouter(prefix="/permissions", tags=["权限管理"])


class PermissionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    menu_path: Optional[str] = None
    menu_label: Optional[str] = None


class PermissionResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    menu_path: Optional[str] = None
    menu_label: Optional[str] = None
    created_at: datetime


DEFAULT_PERMISSIONS = [
    {"name": "holdings:view", "description": "查看持仓", "resource": "holdings", "action": "view", "menu_path": "/holdings", "menu_label": "持仓列表"},
    {"name": "holdings:edit", "description": "编辑持仓", "resource": "holdings", "action": "edit", "menu_path": "/holdings", "menu_label": "持仓管理"},
    {"name": "users:view", "description": "查看用户", "resource": "users", "action": "view", "menu_path": "/admin/users", "menu_label": "用户管理"},
    {"name": "users:edit", "description": "管理用户", "resource": "users", "action": "edit", "menu_path": "/admin/users", "menu_label": "用户管理"},
    {"name": "roles:view", "description": "查看角色", "resource": "roles", "action": "view", "menu_path": "/admin/roles", "menu_label": "角色管理"},
    {"name": "roles:edit", "description": "管理角色", "resource": "roles", "action": "edit", "menu_path": "/admin/roles", "menu_label": "角色管理"},
    {"name": "settings:view", "description": "查看系统设置", "resource": "settings", "action": "view", "menu_path": "/admin/settings", "menu_label": "系统设置"},
    {"name": "rules:view", "description": "查看交易规则", "resource": "rules", "action": "view", "menu_path": "/rules", "menu_label": "交易规则"},
]


def init_default_permissions():
    """初始化默认权限"""
    db = get_db()
    permissions_collection = db.permissions

    for perm in DEFAULT_PERMISSIONS:
        existing = permissions_collection.find_one({"name": perm["name"]})
        if not existing:
            permissions_collection.insert_one({
                "name": perm["name"],
                "description": perm["description"],
                "resource": perm.get("resource", ""),
                "action": perm.get("action", ""),
                "menu_path": perm.get("menu_path"),
                "menu_label": perm.get("menu_label"),
                "created_at": datetime.now()
            })
        else:
            if not existing.get("menu_path"):
                permissions_collection.update_one(
                    {"name": perm["name"]},
                    {"$set": {
                        "menu_path": perm.get("menu_path"),
                        "menu_label": perm.get("menu_label"),
                        "resource": perm.get("resource", ""),
                        "action": perm.get("action", "")
                    }}
                )

    # 同步所有权限到超级管理员角色
    all_perm_ids = [str(p["_id"]) for p in permissions_collection.find()]
    db.roles.update_one(
        {"preset_key": "super_admin"},
        {"$set": {"permission_ids": all_perm_ids}}
    )


@router.get("")
async def get_permissions(
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """获取权限列表"""
    db = get_db()
    permissions_collection = db.permissions

    permissions = list(permissions_collection.find())

    return {
        "items": [
            {
                "id": str(p["_id"]),
                "name": p["name"],
                "description": p.get("description"),
                "menu_path": p.get("menu_path"),
                "menu_label": p.get("menu_label"),
                "created_at": p.get("created_at")
            }
            for p in permissions
        ]
    }


@router.post("")
async def create_permission(
    permission: PermissionCreate,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """创建权限"""
    db = get_db()
    permissions_collection = db.permissions

    existing = permissions_collection.find_one({"name": permission.name})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="权限名已存在"
        )

    perm_doc = {
        "name": permission.name,
        "description": permission.description,
        "menu_path": permission.menu_path,
        "menu_label": permission.menu_label,
        "created_at": datetime.now()
    }

    result = permissions_collection.insert_one(perm_doc)

    return {
        "id": str(result.inserted_id),
        "name": permission.name,
        "description": permission.description,
        "menu_path": permission.menu_path,
        "menu_label": permission.menu_label,
        "created_at": perm_doc["created_at"]
    }


@router.delete("/{permission_id}")
async def delete_permission(
    permission_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """删除权限"""
    db = get_db()
    permissions_collection = db.permissions

    try:
        result = permissions_collection.delete_one({"_id": ObjectId(permission_id)})
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="权限不存在"
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的权限ID"
        )

    return {"message": "删除成功"}


@router.get("/menus")
async def get_menus(
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """获取当前用户可访问的菜单列表"""
    import json
    import os
    
    db = get_db()
    user_roles_collection = db.user_roles
    roles_collection = db.roles
    permissions_collection = db.permissions

    # 从 user_roles 表获取关联的角色
    user_roles = list(user_roles_collection.find({"user_id": current_user.user_id}))
    role_ids = [ur["role_id"] for ur in user_roles]

    # 如果没有关联，尝试从用户表 role 字段映射
    if not role_ids:
        users_collection = db.users
        user = users_collection.find_one({"_id": ObjectId(current_user.user_id)})
        if user and user.get("role"):
            role_map = {
                "admin": "super_admin",
                "system_admin": "system_admin", 
                "normal_admin": "normal_admin"
            }
            preset_key = role_map.get(user.get("role"), user.get("role"))
            role = roles_collection.find_one({"preset_key": preset_key})
            if role:
                role_ids = [str(role["_id"])]

    all_permission_ids = set()
    for role_id in role_ids:
        try:
            effective_perms = RoleService.get_effective_permissions(role_id)
            all_permission_ids.update(effective_perms)
        except Exception:
            continue

    # 获取权限名称集合
    perm_names = set()
    for pid in all_permission_ids:
        try:
            perm = permissions_collection.find_one({"_id": ObjectId(pid)})
            if perm:
                perm_names.add(perm["name"])
        except Exception:
            continue

    # 读取菜单配置文件
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'config', 'menus.json'
    )
    
    with open(config_path, 'r', encoding='utf-8') as f:
        menu_config = json.load(f)
    
    # 根据用户权限过滤菜单
    menus = []
    for menu_group in menu_config.get("menus", []):
        # 检查父菜单权限
        parent_perm = menu_group.get("permission")
        if parent_perm and parent_perm not in perm_names:
            continue
        
        # 过滤子菜单
        children = []
        for child in menu_group.get("children", []):
            child_perm = child.get("permission")
            if not child_perm or child_perm in perm_names:
                children.append(child)
        
        if children:
            menus.append({
                "path": menu_group["path"],
                "label": menu_group["label"],
                "permission": menu_group.get("permission"),
                "children": children
            })
        elif not menu_group.get("children"):
            # 没有子菜单的父菜单直接添加
            menus.append({
                "path": menu_group["path"],
                "label": menu_group["label"],
                "permission": menu_group.get("permission")
            })

    return {"menus": menus}


init_default_permissions()