# Data Model: RBAC角色继承与菜单权限联动

**Feature**: 004-rbac-inheritance
**Date**: 2026-05-14

## Entity: Role

角色实体，支持继承关系和预设角色标识。

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| _id | ObjectId | Yes | Auto | MongoDB主键 |
| name | string | Yes | - | 角色名称，唯一 |
| role_type | string | No | "custom" | "preset"=预设角色, "custom"=自定义 |
| preset_key | string | No | null | 预设角色标识键，如 "super_admin" |
| description | string | No | null | 角色描述 |
| parent_roles | List[string] | No | [] | 继承的角色ID列表 |
| permission_ids | List[string] | No | [] | 直接分配的权限ID列表 |
| created_at | datetime | Yes | Auto | 创建时间 |
| updated_at | datetime | Yes | Auto | 更新时间 |

### Validation Rules

- `name`: 长度 2-50 字符
- `role_type`: 仅允许 "preset" 或 "custom"
- `parent_roles`: 不能包含自身ID，不能形成循环

### State Transitions

- 自定义角色: custom → 可删除
- 预设角色: preset → 不可删除
- 预设超级管理员: preset + locked → 不可编辑

---

## Entity: Permission

页面级权限实体，关联菜单路径。

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| _id | ObjectId | Yes | Auto | MongoDB主键 |
| name | string | Yes | - | 权限标识，如 "holdings:view" |
| description | string | No | null | 权限描述 |
| resource | string | Yes | - | 资源标识，如 "holdings" |
| action | string | Yes | - | 操作类型，如 "view", "edit" |
| menu_path | string | No | null | 关联菜单路径，如 "/holdings" |
| menu_label | string | No | null | 菜单显示名称 |
| created_at | datetime | Yes | Auto | 创建时间 |

### Validation Rules

- `name`: 唯一索引
- `menu_path`: 可选，用于菜单联动

---

## Entity: UserRole

用户角色关联表。

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| _id | ObjectId | Yes | Auto | MongoDB主键 |
| user_id | string | Yes | - | 用户ID |
| role_id | string | Yes | - | 角色ID |
| created_at | datetime | Yes | Auto | 绑定时间 |

### Indexes

- `{user_id: 1, role_id: 1}`: 唯一索引，防止重复绑定

---

## Relationships

```
User (1) ─── (N) UserRole (N) ─── (1) Role (N) ─── (N) Permission
                                                        │
                                                        └── menu_path ─── Menu
```

### 继承关系 (Role → Role)

```
Role A ──parent_roles──> [Role B, Role C]
           │
           └── 获取最终权限: A.permission_ids ∪ B.effective_permissions ∪ C.effective_permissions
```

---

## Default Data

### 预设角色

| preset_key | name | role_type | permissions |
|------------|------|-----------|--------------|
| super_admin | 超级管理员 | preset | * (全部权限) |
| system_admin | 系统管理员 | preset | holdings:view, holdings:edit, users:view, users:edit, roles:view |
| normal_admin | 普通管理员 | preset | holdings:view |

### 默认权限

| name | resource | action | menu_path | menu_label |
|------|----------|--------|-----------|------------|
| holdings:view | holdings | view | /holdings | 持仓管理 |
| holdings:edit | holdings | edit | /holdings | 持仓管理 |
| users:view | users | view | /admin/users | 用户管理 |
| users:edit | users | edit | /admin/users | 用户管理 |
| roles:view | roles | view | /admin/roles | 角色管理 |
| roles:edit | roles | edit | /admin/roles | 角色管理 |
| permissions:view | permissions | view | /admin/permissions | 权限管理 |
| permissions:edit | permissions | edit | /admin/permissions | 权限管理 |

---

## Indexes

### Role Collection

```javascript
db.roles.createIndex({ "name": 1 }, { unique: true })
db.roles.createIndex({ "role_type": 1 })
db.roles.createIndex({ "parent_roles": 1 })
```

### Permission Collection

```javascript
db.permissions.createIndex({ "name": 1 }, { unique: true })
db.permissions.createIndex({ "menu_path": 1 }, { sparse: true })
```

### UserRole Collection

```javascript
db.user_roles.createIndex({ "user_id": 1, "role_id": 1 }, { unique: true })
db.user_roles.createIndex({ "role_id": 1 })
```