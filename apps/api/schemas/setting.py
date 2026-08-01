from pydantic import BaseModel
from typing import Optional


class SettingUpdate(BaseModel):
    model_config = {"extra": "ignore"}
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
    site_status: Optional[str] = None
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


class SettingResponse(BaseModel):
    site_name: str
    site_description: str
    site_logo: str
    site_favicon: str
    site_domain: str
    icp_beian: str
    icp_beian_url: str
    official_url: str
    frontend_url: str
    backend_url: str
    site_status: str
    close_tip: str
    timezone: str
    date_format: str
    time_format: str
    session_expire_minutes: int
    dingtalk_webhook: str
    dingtalk_secret: str
    llm_api_url: str
    llm_api_key: str
    llm_model: str
    llm_batch_size: int


SettingResponse.model_rebuild()
