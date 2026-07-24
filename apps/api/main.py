import os
import logging
from datetime import datetime

from app.app_factory import create_app
from app.core.auth import get_password_hash
from database import get_db

# RBAC 路由
from routers import auth, users, roles, permissions, menu as menu_module
# 持仓管理路由
from app.endpoints.holdings import router as holdings_router
# 菜单路由
from routers.menu import router as menu_router
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
# 收盘复盘路由
from routers.review import router as review_router

from config.config import settings

logger = logging.getLogger(__name__)

app = create_app(
    title=settings.app_name,
    version=settings.app_version,
    description=settings.app_description,
)

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
# 收盘复盘路由
app.include_router(review_router)


@app.get("/")
def read_root():
    db = get_db()
    settings_doc = db.system_settings.find_one({"_id": "global"})
    site_name = settings_doc.get("site_name", "News API") if settings_doc else settings.app_name
    return {"message": f"{site_name} is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.on_event("startup")
async def startup_event():
    """初始化预设角色、权限和默认管理员"""
    from services.role_service import RoleService
    RoleService.init_preset_roles()
    from routers.permissions import init_default_permissions
    init_default_permissions()
    init_default_admin()
    logger.info("Application startup complete")


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
        logger.info(f"Default admin created: {admin_username}")
    else:
        admin_id = str(existing_admin["_id"])

    existing_link = user_roles_collection.find_one({"user_id": admin_id})
    if not existing_link:
        super_admin_role = roles_collection.find_one({"preset_key": "super_admin"})
        if super_admin_role:
            user_roles_collection.insert_one({
                "user_id": admin_id,
                "role_id": str(super_admin_role["_id"])
            })
            logger.info("Admin bound to super_admin role")
