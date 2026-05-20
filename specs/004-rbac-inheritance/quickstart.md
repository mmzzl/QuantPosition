# Quickstart: RBAC角色继承与菜单权限联动

**Feature**: 004-rbac-inheritance
**Date**: 2026-05-14

## 快速开始

### 1. 数据模型变更

#### Role 模型更新

在 `apps/api/models/role.py` 中添加:

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

PRESET_ROLE_KEYS = ["super_admin", "system_admin", "normal_admin"]

class Role(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    role_type: str = Field(default="custom")  # "preset" | "custom"
    preset_key: Optional[str] = None  # 预设角色标识键
    description: Optional[str] = None
    parent_roles: List[str] = Field(default_factory=list)  # 继承的角色ID列表
    permission_ids: List[str] = Field(default_factory=list)  # 直接权限
    locked: bool = Field(default=False)  # 锁定状态
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
```

#### Permission 模型更新

在 `apps/api/models/permission.py` 中添加:

```python
class Permission(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    resource: str = Field(..., min_length=1, max_length=50)
    action: str = Field(..., min_length=1, max_length=50)
    menu_path: Optional[str] = None  # 关联菜单路径
    menu_label: Optional[str] = None  # 菜单显示名称
    created_at: datetime = Field(default_factory=datetime.now)
```

---

### 2. 预设角色初始化

在 `apps/api/main.py` 或数据库初始化时添加:

```python
PRESET_ROLES = [
    {
        "name": "超级管理员",
        "preset_key": "super_admin",
        "role_type": "preset",
        "locked": True,
        "description": "拥有系统全部权限，不可编辑"
    },
    {
        "name": "系统管理员",
        "preset_key": "system_admin",
        "role_type": "preset",
        "locked": False,
        "description": "可管理用户、角色和持仓"
    },
    {
        "name": "普通管理员",
        "preset_key": "normal_admin",
        "role_type": "preset",
        "locked": False,
        "description": "可查看和编辑持仓"
    }
]

def init_preset_roles():
    db = get_db()
    roles_collection = db.roles
    permissions_collection = db.permissions

    # 创建预设角色
    for preset in PRESET_ROLES:
        existing = roles_collection.find_one({"preset_key": preset["preset_key"]})
        if not existing:
            preset["permission_ids"] = []  # 后续关联权限
            preset["parent_roles"] = []
            preset["created_at"] = datetime.now()
            preset["updated_at"] = datetime.now()
            roles_collection.insert_one(preset)
```

---

### 3. 继承链权限计算

在 `apps/api/services/role_service.py` 中添加:

```python
class RoleService:
    # ... existing methods ...

    @staticmethod
    def get_effective_permissions(role_id: str, visited: List[str] = None) -> List[str]:
        """获取角色的有效权限（包含继承链）"""
        if visited is None:
            visited = []

        if role_id in visited:
            return []  # 循环检测，返回空权限

        visited = visited + [role_id]
        if len(visited) > 5:
            return []  # 深度限制

        role = RoleService.get_role_by_id(role_id)
        if not role:
            return []

        # 合并直接权限
        all_permissions = set(role.get("permission_ids", []))

        # 合并继承权限
        for parent_id in role.get("parent_roles", []):
            parent_perms = RoleService.get_effective_permissions(parent_id, visited)
            all_permissions.update(parent_perms)

        return list(all_permissions)

    @staticmethod
    def detect_inheritance_cycle(role_id: str, new_parent: str, visited: List[str] = None) -> bool:
        """检测是否形成循环继承"""
        if visited is None:
            visited = []

        if new_parent == role_id:
            return True

        if new_parent in visited:
            return False

        visited = visited + [new_parent]
        parent_role = RoleService.get_role_by_id(new_parent)
        if not parent_role:
            return False

        for grandparent_id in parent_role.get("parent_roles", []):
            if RoleService.detect_inheritance_cycle(role_id, grandparent_id, visited):
                return True

        return False

    @staticmethod
    def can_edit_role(current_user_role_type: str, target_role: dict) -> bool:
        """检查当前用户是否有权限编辑目标角色"""
        if target_role.get("locked"):
            return False

        role_hierarchy = {"super_admin": 3, "system_admin": 2, "normal_admin": 1}
        current_level = role_hierarchy.get(current_user_role_type, 0)
        target_level = role_hierarchy.get(target_role.get("preset_key", ""), 0)

        return current_level > target_level
```

---

### 4. 菜单权限联动

在 `apps/web/src/router/index.js` 中添加:

```javascript
import { createRouter, createWebHistory } from 'vue-router'
import { getUserPermissions } from '@/utils/auth'
import Layout from '@/views/Layout.vue'

// 菜单配置
const menuConfig = [
  {
    path: 'dashboard',
    name: 'Dashboard',
    component: Dashboard,
    meta: { title: '首页', permission: null }
  },
  {
    path: 'holdings',
    name: 'HoldingsList',
    component: HoldingsList,
    meta: { title: '持仓管理', permission: 'holdings:view' }
  },
  // ... 其他菜单
]

// 动态生成菜单
function generateMenus(userPermissions) {
  return menuConfig.filter(menu => {
    if (!menu.meta?.permission) return true
    return userPermissions.includes(menu.meta.permission)
  })
}

// 路由守卫
router.beforeEach((to, from, next) => {
  const token = getToken()
  if (!token) {
    next('/')
    return
  }

  // 检查菜单权限
  if (to.meta?.permission) {
    const permissions = getUserPermissions()
    if (!permissions.includes(to.meta.permission)) {
      next('/dashboard')
      return
    }
  }

  next()
})
```

---

### 5. 权限编辑控制

在 `apps/api/deps.py` 中添加:

```python
from fastapi import HTTPException, status
from app.core.auth import get_current_active_user, AuthenticatedUser

async def require_role_edit_permission(target_role_id: str, current_user: AuthenticatedUser):
    """检查当前用户是否有权限编辑目标角色"""
    from services.role_service import RoleService
    from services.user_service import UserService

    target_role = RoleService.get_role_by_id(target_role_id)
    if not target_role:
        raise HTTPException(status_code=404, detail="角色不存在")

    current_user_data = UserService.get_user_by_id(current_user.user_id)
    current_role_type = current_user_data.get("role", "normal_admin")

    if not RoleService.can_edit_role(current_role_type, target_role):
        raise HTTPException(
            status_code=403,
            detail="无权限修改此角色"
        )

    return target_role
```

---

### 6. 前端角色编辑权限验证

在 `apps/web/src/views/admin/Roles.vue` 中添加:

```javascript
async function handleEdit(row) {
  // 检查是否有权限编辑
  const currentUserRole = getUserRole()
  const isPresetLocked = row.locked || row.role_type === 'preset' && row.preset_key === 'super_admin'

  if (isPresetLocked) {
    ElMessage.warning('该角色不允许编辑')
    return
  }

  // 检查角色层级
  const roleHierarchy = { super_admin: 3, system_admin: 2, normal_admin: 1 }
  if (roleHierarchy[row.preset_key] >= roleHierarchy[currentUserRole]) {
    ElMessage.error('无权限修改此角色')
    return
  }

  // 继续编辑逻辑
  isEdit.value = true
  // ...
}
```

---

## 测试验证

### API测试

```bash
# 验证预设角色存在
curl http://localhost:8000/roles | jq '.[] | select(.preset_key)'

# 验证继承链计算
curl http://localhost:8000/roles/{role_id}/effective-permissions

# 验证循环检测
curl -X POST http://localhost:8000/roles \
  -H "Content-Type: application/json" \
  -d '{"name": "Test", "parent_roles": ["循环引用ID"]}'

# 验证权限编辑控制
curl -X PUT http://localhost:8000/roles/{super_admin_id} \
  # 应返回 403 Forbidden
```

### 前端测试

1. 使用普通管理员登录，尝试编辑超级管理员角色 → 应提示无权限
2. 创建继承角色，验证权限正确合并
3. 修改角色权限，验证菜单显示/隐藏正确

---

### 继承链测试场景

#### 场景1: 简单继承
```
预设角色: 系统管理员 (持有 holdings:view, users:view)
    ↓ 继承
自定义角色: 持仓管理员
```
**预期结果**: 持仓管理员拥有 holdings:view, users:view 权限

#### 场景2: 多重继承
```
角色A (持有 holdings:edit)
    ↓ 继承
角色B (持有 users:edit)
    ↓ 继承
角色C
```
**预期结果**: 角色C拥有 holdings:edit, users:edit 权限

#### 场景3: 循环继承检测
```
角色A → 继承 → 角色B → 继承 → 角色A
```
**预期结果**: 系统拒绝创建此继承关系，提示"检测到循环继承"

#### 场景4: 继承链深度限制
```
层级1 → 层级2 → 层级3 → 层级4 → 层级5 → 层级6
```
**预期结果**: 超过5层时，系统停止递归合并权限

#### 场景5: 权限覆盖
```
父角色: 持仓管理员 (持有 holdings:view)
子角色: 持仓管理员-受限 (继承持仓管理员，但移除 holdings:view)
```
**预期结果**: 子角色不拥有 holdings:view，因为已显式移除