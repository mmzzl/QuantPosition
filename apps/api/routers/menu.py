from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from app.core.auth import AuthenticatedUser, get_current_user

router = APIRouter(prefix="/menu", tags=["菜单"])


class MenuItem(BaseModel):
    id: str
    title: str
    path: str
    icon: Optional[str] = None
    hidden: bool = False
    isTree: bool = False
    children: Optional[List["MenuItem"]] = None
    permission: Optional[List[str]] = None
    action: Optional[int] = None
    feature_id: Optional[str] = None
    module: Optional[str] = None
    is_prms: Optional[bool] = None
    is_func: Optional[bool] = None
    treeHidden: Optional[bool] = None
    level: Optional[int] = None
    menus: Optional[bool] = None
    catalogue_id: Optional[str] = None
    pModule: Optional[str] = None
    opt: Optional[Dict] = None


class MenuResponse(BaseModel):
    menu: List[Dict[str, Any]]
    authority_prms: Dict[str, int]


def get_default_menu(role: str = "user") -> Dict[str, Any]:
    """获取默认菜单配置"""
    
    if role == "admin":
        # 管理员菜单 - 包含所有功能
        admin_menu = [
            {
                "catalogue_id": "holdings_system",
                "feature_id": "holdings",
                "hidden": False,
                "id": "holdings",
                "is_prms": True,
                "level": 1,
                "menus": True,
                "module": "holdings",
                "path": "/",
                "title": "持仓管理",
                "treeHidden": True,
                "children": [
                    {
                        "action": 3,
                        "catalogue_id": "holdings_dashboard",
                        "feature_id": "holdings.dashboard",
                        "hidden": False,
                        "icon": "icon-home",
                        "id": "dashboard",
                        "isTree": True,
                        "is_prms": True,
                        "module": "holdings.dashboard",
                        "path": "/dashboard",
                        "permission": ["holdings:view"],
                        "title": "首页",
                        "treeHidden": True
                    },
                    {
                        "action": 3,
                        "catalogue_id": "holdings_list",
                        "feature_id": "holdings.list",
                        "hidden": False,
                        "icon": "icon-trendcharts",
                        "id": "holdingsList",
                        "isTree": True,
                        "is_prms": True,
                        "module": "holdings.list",
                        "path": "/holdings",
                        "permission": ["holdings:view"],
                        "title": "持仓列表",
                        "treeHidden": True
                    },
                    {
                        "action": 3,
                        "catalogue_id": "holdings_buy",
                        "feature_id": "holdings.buy",
                        "hidden": False,
                        "icon": "icon-plus",
                        "id": "holdingsBuy",
                        "isTree": True,
                        "is_prms": True,
                        "module": "holdings.buy",
                        "path": "/holdings/buy",
                        "permission": ["holdings:edit"],
                        "title": "买入",
                        "treeHidden": True
                    },
                    {
                        "action": 3,
                        "catalogue_id": "holdings_history",
                        "feature_id": "holdings.history",
                        "hidden": False,
                        "icon": "icon-clock",
                        "id": "holdingsHistory",
                        "isTree": True,
                        "is_prms": True,
                        "module": "holdings.history",
                        "path": "/holdings/history",
                        "permission": ["holdings:view"],
                        "title": "历史记录",
                        "treeHidden": True
                    },
                    {
                        "action": 3,
                        "catalogue_id": "holdings_summary",
                        "feature_id": "holdings.summary",
                        "hidden": False,
                        "icon": "icon-dataanalysis",
                        "id": "holdingsSummary",
                        "isTree": True,
                        "is_prms": True,
                        "module": "holdings.summary",
                        "path": "/holdings/summary",
                        "permission": ["holdings:view"],
                        "title": "组合汇总",
                        "treeHidden": True
                    }
                ]
            },
            {
                "catalogue_id": "sectors_heatmap",
                "feature_id": "sectors",
                "hidden": False,
                "id": "sectors",
                "is_prms": True,
                "level": 1,
                "menus": True,
                "module": "sectors",
                "path": "/",
                "title": "板块热力图",
                "treeHidden": True,
                "children": [
                    {
                        "action": 3,
                        "catalogue_id": "sectors_heatmap_view",
                        "feature_id": "sectors.heatmap",
                        "hidden": False,
                        "icon": "icon-trendcharts",
                        "id": "sectorHeatmap",
                        "isTree": True,
                        "is_prms": True,
                        "module": "sectors.heatmap",
                        "path": "/sectors/heatmap",
                        "permission": ["sectors:view"],
                        "title": "热力图",
                        "treeHidden": True
                    }
                ]
            },
            {
                "catalogue_id": "selections_system",
                "feature_id": "selections",
                "hidden": False,
                "id": "selections",
                "is_prms": True,
                "level": 1,
                "menus": True,
                "module": "selections",
                "path": "/",
                "title": "策略选股",
                "treeHidden": True,
                "children": [
                    {
                        "action": 3,
                        "catalogue_id": "selections_dual_ma",
                        "feature_id": "selections.dual_ma",
                        "hidden": False,
                        "icon": "icon-trendcharts",
                        "id": "dualMASelection",
                        "isTree": True,
                        "is_prms": True,
                        "module": "selections.dual_ma",
                        "path": "/selections/dual-ma",
                        "permission": ["selections:view"],
                        "title": "双均线选股",
                        "treeHidden": True
                    },
                    {
                        "action": 3,
                        "catalogue_id": "selections_news",
                        "feature_id": "selections.news",
                        "hidden": False,
                        "icon": "icon-document",
                        "id": "newsSelection",
                        "isTree": True,
                        "is_prms": True,
                        "module": "selections.news",
                        "path": "/selections/news",
                        "permission": ["selections:view"],
                        "title": "新闻选股",
                        "treeHidden": True
                    }
                ]
            },
            {
                "catalogue_id": "news_browse",
                "feature_id": "news",
                "hidden": False,
                "id": "news",
                "is_prms": True,
                "level": 1,
                "menus": True,
                "module": "news",
                "path": "/",
                "title": "新闻浏览",
                "treeHidden": True,
                "children": [
                    {
                        "action": 3,
                        "catalogue_id": "news_list",
                        "feature_id": "news.list",
                        "hidden": False,
                        "icon": "icon-document",
                        "id": "newsView",
                        "isTree": True,
                        "is_prms": True,
                        "module": "news.list",
                        "path": "/news",
                        "permission": ["holdings:view"],
                        "title": "新闻列表",
                        "treeHidden": True
                    }
                ]
            },
            {
                "catalogue_id": "admin_system",
                "feature_id": "admin",
                "hidden": False,
                "id": "admin",
                "is_prms": True,
                "level": 1,
                "menus": True,
                "module": "admin",
                "path": "/",
                "title": "系统管理",
                "treeHidden": True,
                "children": [
                    {
                        "action": 3,
                        "catalogue_id": "admin_users",
                        "feature_id": "admin.users",
                        "hidden": False,
                        "icon": "icon-user",
                        "id": "adminUsers",
                        "isTree": True,
                        "is_prms": True,
                        "module": "admin.users",
                        "path": "/admin/users",
                        "permission": ["users:view", "users:edit"],
                        "title": "用户管理",
                        "treeHidden": True
                    },
{
                        "action": 3,
                        "catalogue_id": "admin_roles",
                        "feature_id": "admin.roles",
                        "hidden": False,
                        "icon": "icon-setting",
                        "id": "adminRoles",
                        "isTree": True,
                        "is_prms": True,
                        "module": "admin.roles",
                        "path": "/admin/roles",
                        "permission": ["roles:view", "roles:edit"],
                        "title": "角色管理",
                        "treeHidden": True
                    },
                    {
                        "action": 3,
                        "catalogue_id": "admin_permissions",
                        "feature_id": "admin.permissions",
                        "hidden": False,
                        "icon": "icon-lock",
                        "id": "adminPermissions",
                        "isTree": True,
                        "is_prms": True,
                        "module": "admin.permissions",
                        "path": "/admin/permissions",
                        "permission": ["permissions:view", "permissions:edit"],
                        "title": "权限管理",
                        "treeHidden": True
                    },
                    {
                        "action": 3,
                        "catalogue_id": "admin_holdings",
                        "feature_id": "admin.holdings",
                        "hidden": False,
                        "icon": "icon-trendcharts",
                        "id": "adminHoldings",
                        "isTree": True,
                        "is_prms": True,
                        "module": "admin.holdings",
                        "path": "/admin/holdings",
                        "permission": ["holdings:view"],
                        "title": "所有持仓",
                        "treeHidden": True
                    },
                    {
                        "action": 3,
                        "catalogue_id": "admin_settings",
                        "feature_id": "admin.settings",
                        "hidden": False,
                        "icon": "icon-setting",
                        "id": "adminSettings",
                        "isTree": True,
                        "is_prms": True,
                        "module": "admin.settings",
                        "path": "/admin/settings",
                        "permission": ["settings:view"],
                        "title": "系统设置",
                        "treeHidden": True
                    }
                ]
            }
        ]
        
        authority_prms = {
            "holdings:view": 3,
            "holdings:edit": 3,
            "users:view": 3,
            "users:edit": 3,
            "roles:view": 3,
            "roles:edit": 3,
            "permissions:view": 3,
            "permissions:edit": 3,
            "settings:view": 3,
            "sectors:view": 3,
            "selections:view": 3,
            "rules:view": 3
        }
    else:
        # 普通用户菜单
        user_menu = [
            {
                "catalogue_id": "holdings_system",
                "feature_id": "holdings",
                "hidden": False,
                "id": "holdings",
                "is_prms": True,
                "level": 1,
                "menus": True,
                "module": "holdings",
                "path": "/",
                "title": "持仓管理",
                "treeHidden": True,
                "children": [
                    {
                        "action": 3,
                        "catalogue_id": "holdings_dashboard",
                        "feature_id": "holdings.dashboard",
                        "hidden": False,
                        "icon": "icon-home",
                        "id": "dashboard",
                        "isTree": True,
                        "is_prms": True,
                        "module": "holdings.dashboard",
                        "path": "/dashboard",
                        "permission": ["holdings:view"],
                        "title": "首页",
                        "treeHidden": True
                    },
                    {
                        "action": 3,
                        "catalogue_id": "holdings_list",
                        "feature_id": "holdings.list",
                        "hidden": False,
                        "icon": "icon-trendcharts",
                        "id": "holdingsList",
                        "isTree": True,
                        "is_prms": True,
                        "module": "holdings.list",
                        "path": "/holdings",
                        "permission": ["holdings:view"],
                        "title": "持仓列表",
                        "treeHidden": True
                    },
                    {
                        "action": 3,
                        "catalogue_id": "holdings_buy",
                        "feature_id": "holdings.buy",
                        "hidden": False,
                        "icon": "icon-plus",
                        "id": "holdingsBuy",
                        "isTree": True,
                        "is_prms": True,
                        "module": "holdings.buy",
                        "path": "/holdings/buy",
                        "permission": ["holdings:edit"],
                        "title": "买入",
                        "treeHidden": True
                    },
                    {
                        "action": 3,
                        "catalogue_id": "holdings_history",
                        "feature_id": "holdings.history",
                        "hidden": False,
                        "icon": "icon-clock",
                        "id": "holdingsHistory",
                        "isTree": True,
                        "is_prms": True,
                        "module": "holdings.history",
                        "path": "/holdings/history",
                        "permission": ["holdings:view"],
                        "title": "历史记录",
                        "treeHidden": True
                    },
                    {
                        "action": 3,
                        "catalogue_id": "selections_dual_ma",
                        "feature_id": "selections.dual_ma",
                        "hidden": False,
                        "icon": "icon-trendcharts",
                        "id": "dualMASelection",
                        "isTree": True,
                        "is_prms": True,
                        "module": "selections.dual_ma",
                        "path": "/selections/dual-ma",
                        "permission": ["selections:view"],
                        "title": "双均线选股",
                        "treeHidden": True
                    },
                    {
                        "action": 3,
                        "catalogue_id": "selections_news",
                        "feature_id": "selections.news",
                        "hidden": False,
                        "icon": "icon-document",
                        "id": "newsSelection",
                        "isTree": True,
                        "is_prms": True,
                        "module": "selections.news",
                        "path": "/selections/news",
                        "permission": ["selections:view"],
                        "title": "新闻选股",
                        "treeHidden": True
                    }
                ]
            },
            {
                "catalogue_id": "news_browse",
                "feature_id": "news",
                "hidden": False,
                "id": "news",
                "is_prms": True,
                "level": 1,
                "menus": True,
                "module": "news",
                "path": "/",
                "title": "新闻浏览",
                "treeHidden": True,
                "children": [
                    {
                        "action": 3,
                        "catalogue_id": "news_list",
                        "feature_id": "news.list",
                        "hidden": False,
                        "icon": "icon-document",
                        "id": "newsView",
                        "isTree": True,
                        "is_prms": True,
                        "module": "news.list",
                        "path": "/news",
                        "permission": ["holdings:view"],
                        "title": "新闻列表",
                        "treeHidden": True
                    }
                ]
            }
        ]
        
        authority_prms = {
            "holdings:view": 3,
            "holdings:edit": 3
        }
    
    return {
        "menu": admin_menu if role == "admin" else user_menu,
        "authority_prms": authority_prms
    }


@router.get("", response_model=MenuResponse)
async def get_menu(current_user: AuthenticatedUser = Depends(get_current_user)):
    """获取用户菜单和权限"""
    from database import get_db
    from bson import ObjectId
    
    db = get_db()
    users_collection = db.users
    
    # 获取用户角色
    role = "user"
    try:
        user_doc = users_collection.find_one({"_id": ObjectId(current_user.user_id)})
        if user_doc:
            role = user_doc.get("role", "user")
    except Exception:
        pass
    
    menu_data = get_default_menu(role)
    
    return menu_data