from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.core.auth import AuthenticatedUser, get_current_user
from database import get_db

router = APIRouter(prefix="/settings", tags=["系统设置"])


DEFAULTS = {
    "site_name": "持仓管理系统",
    "site_description": "",
    "site_logo": "",
    "site_favicon": "",
    "site_domain": "",
    "icp_beian": "",
    "icp_beian_url": "",
    "official_url": "",
    "frontend_url": "",
    "backend_url": "",
    "site_status": "open",
    "close_tip": "系统维护中，请稍后再试",
    "timezone": "Asia/Shanghai",
    "date_format": "YYYY-MM-DD",
    "time_format": "HH:mm:ss",
    "session_expire_minutes": 30,
    "dingtalk_webhook": "",
    "dingtalk_secret": "",
    "llm_api_url": "https://api.openai.com/v1",
    "llm_api_key": "",
    "llm_model": "gpt-4o-mini",
    "llm_batch_size": 100,
}


@router.get("/public")
async def get_public_settings():
    """公开设置（无需登录）"""
    db = get_db()
    doc = db.system_settings.find_one({"_id": "global"}) or {}
    return {k: doc.get(k, v) for k, v in DEFAULTS.items()
            if k in ("site_name", "site_description", "site_logo",
                     "site_favicon", "site_domain", "icp_beian",
                     "icp_beian_url", "site_status", "close_tip",
                     "timezone", "date_format", "time_format")}


class SystemSettings(BaseModel):
    site_name: Optional[str] = None
    site_description: Optional[str] = None
    site_logo: Optional[str] = None
    site_favicon: Optional[str] = None
    site_domain: Optional[str] = None
    icp_beian: Optional[str] = None
    icp_beian_url: Optional[str] = None
    official_url: Optional[str] = None
    frontend_url: Optional[str] = None
    backend_url: Optional[str] = None
    site_status: Optional[str] = None          # open / closed
    close_tip: Optional[str] = None
    timezone: Optional[str] = None
    date_format: Optional[str] = None
    time_format: Optional[str] = None
    session_expire_minutes: Optional[int] = None
    dingtalk_webhook: Optional[str] = None
    dingtalk_secret: Optional[str] = None
    llm_api_url: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    llm_batch_size: Optional[int] = None


@router.get("")
async def get_settings(
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """获取全部系统设置"""
    db = get_db()
    doc = db.system_settings.find_one({"_id": "global"}) or {}
    return {k: doc.get(k, v) for k, v in DEFAULTS.items()}


@router.put("")
async def update_settings(
    settings: SystemSettings,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """更新系统设置（管理员）"""
    from services.role_service import RoleService
    roles = RoleService.get_user_roles(current_user.user_id)
    if not any(r.get("preset_key") in ("super_admin", "admin", "system_admin") for r in roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")

    update = {k: v for k, v in settings.model_dump().items() if v is not None}
    update["updated_at"] = datetime.now()

    db.system_settings.update_one({"_id": "global"}, {"$set": update}, upsert=True)

    return {"message": "设置已保存", **update}
