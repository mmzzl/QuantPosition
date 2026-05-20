# Implementation Plan: 用户角色权限系统 (RBAC)

**Branch**: `002-auth-rbac-mongodb` | **Date**: 2026-05-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-auth-rbac-mongodb/spec.md`

## Summary

实现基于MongoDB的用户、角色、权限（RBAC）三全分离认证系统。支持用户名密码登录和JWT令牌认证，提供完整的增删改查API。

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: FastAPI, pymongo, python-jose, passlib[bcrypt]
**Storage**: MongoDB
**Testing**: pytest
**Target Platform**: Linux server
**Project Type**: web-service
**Performance Goals**: 登录<500ms, 权限验证<100ms, 用户创建<1s
**Constraints**: 支持10000并发用户
**Scale**: 中小型应用 (用户量级)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

无宪法约束violations。特征符合Web服务标准实践。

## Project Structure

### Documentation (this feature)

```text
specs/002-auth-rbac-mongodb/
├── plan.md              # This file (/speckit.plan command output)
├── spec.md              # Feature specification
├── data-model.md        # (to be generated)
├── quickstart.md        # (to be generated)
├── auth.py              # 实现文件
└── models/              # 数据模型目录
```

### Source Code (repository root)

```text
apps/api/
├── app/
│   └── core/
│       └── auth.py     # 认证授权核心代码
├── models/             # MongoDB模型
│   ├── user.py
│   ├── role.py
│   └── permission.py
├── schemas/            # Pydantic schemas
│   ├── user.py
│   ├── token.py
│   └── auth.py
├── routers/            # API路由
│   ├── auth.py
│   └── users.py
└── database.py         # MongoDB连接
```

**Structure Decision**: FastAPI项目结构，基于apps/api目录

## Phase 1: Design

### 数据模型

```python
# User - 用户
{
    "_id": ObjectId,
    "username": str (unique),
    "password_hash": str,
    "email": str,
    "phone": str,
    "is_active": bool,
    "created_at": datetime,
    "updated_at": datetime
}

# Role - 角色
{
    "_id": ObjectId,
    "name": str (unique),
    "description": str,
    "permissions": [ObjectId],  # 权限ID列表
    "created_at": datetime,
    "updated_at": datetime
}

# Permission - 权限
{
    "_id": ObjectId,
    "name": str (unique),
    "resource": str,  # 资源，如 "user", "article"
    "action": str,    # 操作，如 "create", "read", "update", "delete"
    "created_at": datetime
}

# UserRole - 用户角色关联
{
    "_id": ObjectId,
    "user_id": ObjectId,
    "role_id": ObjectId
}
```

### API接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /auth/login | 用户登录，返回JWT |
| POST | /auth/register | 用户注册 |
| GET | /users | 获取用户列表 |
| POST | /users | 创建用户 |
| GET | /users/{id} | 获取用户详情 |
| PUT | /users/{id} | 更新用户 |
| DELETE | /users/{id} | 删除用户 |
| GET | /roles | 获取角色列表 |
| POST | /roles | 创建角色 |
| PUT | /roles/{id} | 更新角色 |
| DELETE | /roles/{id} | 删除角色 |
| GET | /permissions | 获取权限列表 |
| POST | /permissions | 创建权限 |

### 实现文件

- `apps/api/app/core/auth.py` - 认证核心逻辑 (已有，需扩展)
- `apps/api/database.py` - MongoDB连接
- `apps/api/models/user.py` - 用户模型
- `apps/api/models/role.py` - 角色模型
- `apps/api/models/permission.py` - 权限模型
- `apps/api/schemas/auth.py` - 认证Schema
- `apps/api/schemas/user.py` - 用户Schema
- `apps/api/routers/auth.py` - 认证路由
- `apps/api/routers/users.py` - 用户管理路由
- `apps/api/routers/roles.py` - 角色管理路由
- `apps/api/routers/permissions.py` - 权限管理路由