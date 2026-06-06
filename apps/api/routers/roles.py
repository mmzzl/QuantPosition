from typing import List
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import AuthenticatedUser, get_current_active_user
from services.role_service import RoleService
from schemas.role import RoleCreate, RoleUpdate, RoleResponse
from database import get_db

router = APIRouter(prefix="/roles", tags=["角色管理"])


def _require_roles_edit(user: AuthenticatedUser):
    """检查用户是否有 roles:edit 权限"""
    roles = RoleService.get_user_roles(user.user_id)
    if not any(r.get("preset_key") in ("super_admin", "admin") for r in roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要角色管理权限")


@router.get("", response_model=List[RoleResponse])
async def get_roles(
    skip: int = 0,
    limit: int = 100,
    current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """获取角色列表"""
    roles = RoleService.get_roles(skip=skip, limit=limit)

    result = []
    for role in roles:
        result.append(RoleResponse(
            id=str(role["_id"]),
            name=role["name"],
            role_type=role.get("role_type", "custom"),
            preset_key=role.get("preset_key"),
            description=role.get("description"),
            parent_roles=role.get("parent_roles", []),
            permission_ids=role.get("permission_ids", []),
            locked=role.get("locked", False),
            created_at=role.get("created_at"),
            updated_at=role.get("updated_at")
        ))

    return result


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """创建角色"""
    _require_roles_edit(current_user)
    try:
        if role_data.parent_roles:
            for parent_id in role_data.parent_roles:
                parent = RoleService.get_role_by_id(parent_id)
                if parent and parent.get("locked"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Cannot inherit from a locked role"
                    )

        role = RoleService.create_role(role_data)
        return RoleResponse(
            id=str(role["_id"]),
            name=role["name"],
            role_type=role.get("role_type", "custom"),
            preset_key=role.get("preset_key"),
            description=role.get("description"),
            parent_roles=role.get("parent_roles", []),
            permission_ids=role.get("permission_ids", []),
            locked=role.get("locked", False),
            created_at=role.get("created_at"),
            updated_at=role.get("updated_at")
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: str,
    current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """获取角色详情"""
    role = RoleService.get_role_by_id(role_id)

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    return RoleResponse(
        id=str(role["_id"]),
        name=role["name"],
        role_type=role.get("role_type", "custom"),
        preset_key=role.get("preset_key"),
        description=role.get("description"),
        parent_roles=role.get("parent_roles", []),
        permission_ids=role.get("permission_ids", []),
        locked=role.get("locked", False),
        created_at=role.get("created_at"),
        updated_at=role.get("updated_at")
    )


@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: str,
    role_data: RoleUpdate,
    current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """更新角色"""
    _require_roles_edit(current_user)
    try:
        role = RoleService.update_role(role_id, role_data)

        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
            )

        return RoleResponse(
            id=str(role["_id"]),
            name=role["name"],
            role_type=role.get("role_type", "custom"),
            preset_key=role.get("preset_key"),
            description=role.get("description"),
            parent_roles=role.get("parent_roles", []),
            permission_ids=role.get("permission_ids", []),
            locked=role.get("locked", False),
            created_at=role.get("created_at"),
            updated_at=role.get("updated_at")
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: str,
    current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """删除角色"""
    _require_roles_edit(current_user)
    try:
        success = RoleService.delete_role(role_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{role_id}/users/{user_id}")
async def add_user_to_role(
    role_id: str,
    user_id: str,
    current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """将用户添加到角色"""
    _require_roles_edit(current_user)
    success = RoleService.add_user_to_role(user_id, role_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to add user to role"
        )

    return {"message": "User added to role successfully"}


@router.delete("/{role_id}/users/{user_id}")
async def remove_user_from_role(
    role_id: str,
    user_id: str,
    current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """将用户从角色移除"""
    _require_roles_edit(current_user)
    success = RoleService.remove_user_from_role(user_id, role_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to remove user from role"
        )

    return {"message": "User removed from role successfully"}


@router.get("/{role_id}/permissions")
async def get_role_permissions(
    role_id: str,
    current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """获取角色的直接权限列表"""
    permissions = RoleService.get_role_permissions(role_id)

    result = []
    for perm in permissions:
        result.append({
            "id": str(perm["_id"]),
            "name": perm["name"],
            "resource": perm.get("resource", ""),
            "action": perm.get("action", ""),
            "menu_path": perm.get("menu_path"),
            "menu_label": perm.get("menu_label")
        })

    return result


@router.get("/{role_id}/effective-permissions")
async def get_effective_permissions(
    role_id: str,
    current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """获取角色的有效权限（包含继承链）"""
    from database import get_db
    db = get_db()
    role = db.roles.find_one({"_id": ObjectId(role_id)})
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    perm_ids = RoleService.get_effective_permissions(role_id)
    perms_collection = db.permissions

    object_ids = []
    for pid in perm_ids:
        try:
            object_ids.append(ObjectId(pid))
        except Exception:
            continue

    permissions = list(perms_collection.find({"_id": {"$in": object_ids}}))

    result = []
    for perm in permissions:
        result.append({
            "id": str(perm["_id"]),
            "name": perm["name"],
            "resource": perm.get("resource", ""),
            "action": perm.get("action", ""),
            "menu_path": perm.get("menu_path"),
            "menu_label": perm.get("menu_label")
        })

    return {
        "role_id": role_id,
        "role_name": role["name"],
        "direct_permissions": len(role.get("permission_ids", [])),
        "effective_permissions": result,
        "total_count": len(result)
    }