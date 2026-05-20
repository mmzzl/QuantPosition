# Data Model: 用户角色权限系统 (RBAC)

## 实体定义

### User (用户)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| _id | ObjectId | 主键 | MongoDB自动生成 |
| username | string | 唯一, 必填 | 用户名 |
| password_hash | string | 必填 | BCrypt加密的密码 |
| email | string | 可选 | 邮箱 |
| phone | string | 可选 | 手机号 |
| is_active | boolean | 默认true | 是否激活 |
| created_at | datetime | 自动 | 创建时间 |
| updated_at | datetime | 自动 | 更新时间 |

**关系**: 多对多 → Role (通过UserRole)

---

### Role (角色)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| _id | ObjectId | 主键 | MongoDB自动生成 |
| name | string | 唯一, 必填 | 角色名 |
| description | string | 可选 | 角色描述 |
| created_at | datetime | 自动 | 创建时间 |
| updated_at | datetime | 自动 | 更新时间 |

**关系**: 多对多 → Permission (通过RolePermission)

---

### Permission (权限)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| _id | ObjectId | 主键 | MongoDB自动生成 |
| name | string | 唯一, 必填 | 权限名 |
| resource | string | 必填 | 资源 (如 user, article) |
| action | string | 必填 | 操作 (create, read, update, delete) |
| created_at | datetime | 自动 | 创建时间 |

**示例**:
- `user:create` - 创建用户
- `user:read` - 读取用户
- `user:update` - 更新用户
- `user:delete` - 删除用户

---

### UserRole (用户角色关联)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| _id | ObjectId | 主键 | MongoDB自动生成 |
| user_id | ObjectId | 必填 | 用户ID |
| role_id | ObjectId | 必填 | 角色ID |

**索引**: 复合索引 (user_id, role_id) 唯一

---

### RolePermission (角色权限关联)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| _id | ObjectId | 主键 | MongoDB自动生成 |
| role_id | ObjectId | 必填 | 角色ID |
| permission_id | ObjectId | 必填 | 权限ID |

**索引**: 复合索引 (role_id, permission_id) 唯一

---

## 关系图

```
User ←--- UserRole --→ Role ←--- RolePermission --→ Permission
  ↑                      ↑
  │                      │
  └──────────────────────┘
      多对多关系
```

---

## 验证规则

- **用户名**: 3-20字符, 字母数字下划线
- **密码**: 最少6位
- **角色名**: 2-50字符, 唯一
- **权限名**: 格式 `resource:action`

---

## 索引

| 集合 | 索引 | 唯一 |
|------|------|------|
| users | username | 是 |
| users | email | 否 |
| roles | name | 是 |
| permissions | name | 是 |
| user_roles | (user_id, role_id) | 是 |
| role_permissions | (role_id, permission_id) | 是 |