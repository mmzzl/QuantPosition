from pydantic import BaseModel, Field
from typing import Any
from datetime import datetime


DEFAULTS: dict[str, Any] = {
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

PUBLIC_FIELDS: set[str] = {
    "site_name", "site_description", "site_logo",
    "site_favicon", "site_domain", "icp_beian",
    "icp_beian_url", "site_status", "close_tip",
    "timezone", "date_format", "time_format",
}


class SystemSetting(BaseModel):
    site_name: str = Field(default="持仓管理系统")
    site_description: str = ""
    site_logo: str = ""
    site_favicon: str = ""
    site_domain: str = ""
    icp_beian: str = ""
    icp_beian_url: str = ""
    official_url: str = ""
    frontend_url: str = ""
    backend_url: str = ""
    site_status: str = "open"
    close_tip: str = "系统维护中，请稍后再试"
    timezone: str = "Asia/Shanghai"
    date_format: str = "YYYY-MM-DD"
    time_format: str = "HH:mm:ss"
    session_expire_minutes: int = 30
    dingtalk_webhook: str = ""
    dingtalk_secret: str = ""
    llm_api_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_batch_size: int = 100
    updated_at: datetime | None = None
