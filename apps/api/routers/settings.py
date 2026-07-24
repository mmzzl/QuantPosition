import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import AuthenticatedUser, get_current_user
from models.setting import DEFAULTS
from schemas.setting import SettingUpdate
from services.setting_service import SettingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["系统设置"])


@router.get("/public")
async def get_public_settings():
    """公开设置（无需登录）"""
    return await SettingService.get_public_settings()


@router.get("")
async def get_settings(
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """获取全部系统设置"""
    return await SettingService.get_all_settings()


@router.put("")
async def update_settings(
    settings: SettingUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """更新系统设置（管理员）"""
    from services.role_service import RoleService
    roles = RoleService.get_user_roles(current_user.user_id)
    if not any(r.get("preset_key") in ("super_admin", "admin", "system_admin") for r in roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")

    update_data = settings.model_dump(exclude_none=True)
    for key in update_data:
        if key not in DEFAULTS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"无效的设置项: {key}")

    await SettingService.batch_update(update_data)
    return {"message": "设置已保存", **update_data}
