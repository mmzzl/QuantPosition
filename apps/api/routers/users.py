from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId

from app.core.auth import AuthenticatedUser, get_current_active_user, verify_password
from services.user_service import UserService
from schemas.user import UserCreate, UserUpdate, UserResponse, ChangePassword
from database import get_db
from app.core.auth import get_password_hash

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.get("", response_model=List[UserResponse])
async def get_users(
    skip: int = 0,
    limit: int = 100,
    current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """获取用户列表"""
    users = UserService.get_users(skip=skip, limit=limit)

    result = []
    for user in users:
        result.append(UserResponse(
            id=str(user["_id"]),
            username=user["username"],
            email=user.get("email"),
            phone=user.get("phone"),
            is_active=user.get("is_active", True),
            created_at=user.get("created_at"),
            updated_at=user.get("updated_at")
        ))

    return result


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """创建用户"""
    try:
        return UserService.create_user(user_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """获取用户详情"""
    user = UserService.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return UserResponse(
        id=str(user["_id"]),
        username=user["username"],
        email=user.get("email"),
        phone=user.get("phone"),
        is_active=user.get("is_active", True),
        created_at=user.get("created_at"),
        updated_at=user.get("updated_at")
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """更新用户"""
    db = get_db()
    users_collection = db.users
    
    target_user = users_collection.find_one({"_id": ObjectId(user_id)})
    if target_user and target_user.get("username") == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能修改管理员用户"
        )

    user = UserService.update_user(user_id, user_data)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return UserResponse(
        id=str(user["_id"]),
        username=user["username"],
        email=user.get("email"),
        phone=user.get("phone"),
        is_active=user.get("is_active", True),
        created_at=user.get("created_at"),
        updated_at=user.get("updated_at")
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """删除用户"""
    db = get_db()
    users_collection = db.users
    
    target_user = users_collection.find_one({"_id": ObjectId(user_id)})
    if target_user and target_user.get("username") == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除管理员账户"
        )
    
    success = UserService.delete_user(user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )


@router.put("/{user_id}/password")
async def change_password(
    user_id: str,
    password_data: ChangePassword,
    current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """修改用户密码（仅限本人或管理员）"""
    if current_user.user_id != user_id:
        from services.role_service import RoleService
        roles = RoleService.get_user_roles(current_user.user_id)
        if not any(r.get("preset_key") == "super_admin" for r in roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权修改他人密码")

    db = get_db()
    users_collection = db.users

    user = users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not verify_password(password_data.old_password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect old password"
        )

    users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "password_hash": get_password_hash(password_data.new_password),
            "updated_at": datetime.now()
        }}
    )

    return {"message": "Password changed successfully"}


@router.put("/{user_id}/role")
async def assign_user_role(
    user_id: str,
    role_data: dict,
    current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """为用户分配角色"""
    from services.role_service import RoleService
    role_id = role_data.get("role_id")
    if not role_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="role_id is required")

    success = RoleService.add_user_to_role(user_id, role_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to assign role")

    return {"message": "Role assigned successfully"}


@router.get("/me/roles")
async def get_my_roles(
    current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """获取当前用户的角色列表"""
    from services.role_service import RoleService

    roles = RoleService.get_user_roles(current_user.user_id)

    return [
        {
            "id": str(role["_id"]),
            "name": role["name"],
            "role_type": role.get("role_type", "custom"),
            "preset_key": role.get("preset_key")
        }
        for role in roles
    ]