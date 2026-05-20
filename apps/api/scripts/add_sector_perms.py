from pymongo import MongoClient
from bson import ObjectId

client = MongoClient('mongodb://localhost:27017/')
db = client['eastmoney_news']

# 添加板块热力图相关权限
sector_perms = [
    {"name": "sectors:view", "description": "查看板块热力图", "resource": "sectors", "action": "view", "menu_path": "/sectors/heatmap", "menu_label": "板块热力图"},
    {"name": "sectors:stocks", "description": "查看板块股票列表", "resource": "sectors", "action": "stocks", "menu_path": "/sectors/stocks", "menu_label": "板块股票列表"},
]

for perm in sector_perms:
    existing = db.permissions.find_one({"name": perm["name"]})
    if not existing:
        result = db.permissions.insert_one(perm)
        print(f"已添加权限: {perm['name']}, ID: {result.inserted_id}")
    else:
        # 更新已有权限的menu_path和menu_label
        db.permissions.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "menu_path": perm["menu_path"],
                "menu_label": perm["menu_label"],
                "resource": perm["resource"],
                "action": perm["action"]
            }}
        )
        print(f"已更新权限: {perm['name']}")

# 获取所有权限IDs
all_perm_ids = [str(p["_id"]) for p in db.permissions.find()]

# 更新超级管理员角色的权限
db.roles.update_one(
    {"preset_key": "super_admin"},
    {"$set": {"permission_ids": all_perm_ids}}
)
print("已更新超级管理员权限")

# 验证
print("\n板块相关权限:")
for p in db.permissions.find({"name": {"$regex": "^sectors:"}}):
    print(f"  {p.get('name')}: {p.get('menu_path')} - {p.get('menu_label')}")
