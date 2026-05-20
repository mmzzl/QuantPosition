# Research: RBAC角色继承与菜单权限联动

**Feature**: 004-rbac-inheritance
**Date**: 2026-05-14

## Decision 1: 角色继承数据模型

**Chosen**: 在 Role 实体中添加 `parent_roles: List[str]` 字段存储继承关系

**Rationale**:
- 简化查询，无需额外的关系表
- 支持多继承（角色可继承多个父角色）
- 通过递归算法计算最终权限集

**Implementation**:
```python
class Role(BaseModel):
    name: str
    role_type: str = "custom"  # "preset" | "custom"
    parent_roles: List[str] = []  # 继承的角色ID列表
    permission_ids: List[str] = []  # 直接权限
```

**Alternatives Considered**:
- 单独 RoleInheritance 表 → 增加查询复杂度
- 扁平权限存储 → 权限更新需同步所有子角色

---

## Decision 2: 预设角色标识

**Chosen**: 通过 `role_type: str = "preset"` 字段标识预设角色

**Rationale**:
- 区分预设角色和自定义角色
- 预设角色不可删除
- 预设角色中超级管理员不可编辑

**Implementation**:
```python
PRESET_ROLES = {
    "super_admin": {"name": "超级管理员", "role_type": "preset", "permissions": "*"},
    "system_admin": {"name": "系统管理员", "role_type": "preset"},
    "normal_admin": {"name": "普通管理员", "role_type": "preset"}
}
```

---

## Decision 3: 继承链循环检测

**Chosen**: 递归检测 + 深度限制（最大5层）

**Algorithm**:
```
function detect_cycle(role_id, visited=[]):
    if role_id in visited:
        return True  # 循环检测
    if len(visited) > 5:
        return True  # 深度限制
    for parent in role.parent_roles:
        if detect_cycle(parent, visited + [role_id]):
            return True
    return False
```

---

## Decision 4: 权限计算（继承链合并）

**Chosen**: 递归合并所有祖先角色的权限

**Algorithm**:
```
function get_effective_permissions(role_id):
    role = get_role(role_id)
    permissions = set(role.permission_ids)
    for parent_id in role.parent_roles:
        permissions.update(get_effective_permissions(parent_id))
    return permissions
```

**Caching**: 使用内存缓存避免重复计算

---

## Decision 5: 菜单权限联动

**Chosen**: Permission 模型增加 `menu_path` 字段，前端根据用户权限动态过滤菜单

**Permission Schema**:
```python
class Permission(BaseModel):
    name: str
    resource: str
    action: str
    menu_path: Optional[str] = None  # 关联菜单路径，如 "/holdings"
```

**Frontend Logic**:
```javascript
function filterMenusByPermissions(allMenus, userPermissions) {
    return allMenus.filter(menu =>
        !menu.permission || userPermissions.includes(menu.permission)
    )
}
```

---

## Decision 6: 权限编辑控制

**Chosen**: 角色编辑时验证当前用户是否有权限修改目标角色

**Rules**:
- 超级管理员可编辑所有角色
- 系统管理员只能编辑系统管理员和普通管理员角色
- 普通管理员只能编辑普通管理员角色

**Implementation**:
```python
def can_edit_role(current_user_role, target_role):
    role_hierarchy = {"super_admin": 3, "system_admin": 2, "normal_admin": 1}
    if role_hierarchy.get(target_role.role_type, 0) >= role_hierarchy.get(current_user_role, 0):
        return False
    return True
```

---

## Best Practices

1. **权限缓存**: 用户登录时缓存有效权限，减少数据库查询
2. **延迟删除**: 删除被继承的角色时，先检查继承链，处理后再删除
3. **事务处理**: 权限更新使用 MongoDB 事务确保一致性
4. **日志记录**: 所有权限变更记录操作日志

---

## External References

- MongoDB Role-Based Access Control: https://www.mongodb.com/docs/manual/core/authorization/
- RBAC Best Practices: https://csrc.nist.gov/projects/risk-management/
- Vue Dynamic Routes: https://router.vuejs.org/guide/advanced/dynamic-routing.html