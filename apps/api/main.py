# Apply pandas compatibility patch before any other imports
# -*- coding: utf-8 -*-
import os
import logging
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from systems.logs import Log
from config.config import settings
from app.core.error import setup_error_handlers
# from app.endpoints.api_holdings import router as holdings_router

# RBAC 路由
from routers import auth, users, roles, permissions, menu as menu_module
# 持仓管理路由
from app.endpoints.holdings import router as holdings_router
# 菜单路由
from routers.menu import router as menu_router
# 角色服务
from services.role_service import RoleService
from app.core.auth import get_password_hash
from database import get_db
# 板块热力图路由
from routers.sectors import router as sectors_router
# 选股路由
from routers.selections import router as selections_router
# 系统设置路由
from routers.settings import router as settings_router
# 新闻选股路由
from routers.news_selection import router as news_selection_router
# 新闻浏览路由
from routers.news import router as news_router
# 交易规则路由
from routers.rules import router as rules_router
# 回测路由
from routers.backtest import router as backtest_router
# 模拟盘路由
from routers.paper_trading import router as paper_trading_router
# 热力图选股路由
from routers.heatmap_selection import router as heatmap_selection_router

Log("rest_api", log_type=Log.TYPE_FILE, level=logging.INFO)

app = FastAPI(
    title=settings.app_name,
    description=settings.app_description,
    version=settings.app_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_error_handlers(app)
# app.include_router(holdings_router, prefix="/api")

# RBAC 路由注册
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(roles.router)
app.include_router(permissions.router)
# 持仓管理路由
app.include_router(holdings_router)
# 菜单路由
app.include_router(menu_router)
# 板块热力图路由
app.include_router(sectors_router)
# 选股路由
app.include_router(selections_router)
# 系统设置路由
app.include_router(settings_router)
# 新闻选股路由
app.include_router(news_selection_router)
# 新闻浏览路由
app.include_router(news_router)
# 交易规则路由
app.include_router(rules_router)
# 回测路由
app.include_router(backtest_router)
# 模拟盘路由
app.include_router(paper_trading_router)
# 热力图选股路由
app.include_router(heatmap_selection_router)


@app.get("/")
def read_root():
    db = get_db()
    settings_doc = db.system_settings.find_one({"_id": "global"})
    site_name = settings_doc.get("site_name", "News API") if settings_doc else settings.app_name
    return {"message": f"{site_name} is running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.on_event("startup")
async def startup_event():
    """初始化预设角色、权限和默认管理员"""
    RoleService.init_preset_roles()
    from routers.permissions import init_default_permissions
    init_default_permissions()
    init_default_admin()


def init_default_admin():
    """初始化默认管理员用户"""
    db = get_db()
    users_collection = db.users
    user_roles_collection = db.user_roles
    roles_collection = db.roles
    
    admin_username = "admin"
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    
    existing_admin = users_collection.find_one({"username": admin_username})
    if not existing_admin:
        admin_user = {
            "username": admin_username,
            "password_hash": get_password_hash(admin_password),
            "email": "admin@example.com",
            "role": "admin",
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        result = users_collection.insert_one(admin_user)
        admin_id = str(result.inserted_id)
        print(f"默认管理员已创建: {admin_username} / {admin_password}")
    else:
        admin_id = str(existing_admin["_id"])
    
    # 检查是否已有关联
    existing_link = user_roles_collection.find_one({"user_id": admin_id})
    if not existing_link:
        super_admin_role = roles_collection.find_one({"preset_key": "super_admin"})
        if super_admin_role:
            user_roles_collection.insert_one({
                "user_id": admin_id,
                "role_id": str(super_admin_role["_id"])
            })
            print("管理员已绑定超级管理员角色")
