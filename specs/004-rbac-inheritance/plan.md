# Implementation Plan: RBAC角色继承与菜单权限联动

**Branch**: `002-auth-rbac-mongodb` | **Date**: 2026-05-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-rbac-inheritance/spec.md`

## Summary

实现角色继承机制与菜单权限联动功能，包括预设角色（超级管理员、系统管理员、普通管理员）、角色继承链、菜单动态显示、权限编辑控制。

## Technical Context

**Language/Version**: Python 3.11, JavaScript (ES6+)  
**Primary Dependencies**: FastAPI, Vue 3, Element Plus, MongoDB (pymongo), bcrypt, python-jose  
**Storage**: MongoDB  
**Testing**: pytest, manual API testing  
**Target Platform**: Linux server, Web browser  
**Project Type**: Web application (backend API + frontend SPA)  
**Performance Goals**: 权限验证 < 100ms, 菜单加载 < 500ms  
**Constraints**: 继承链最大5层深度  
**Scale/Scope**: 1000用户规模，50个菜单项

### 当前项目结构

```text
apps/
├── api/                    # FastAPI 后端
│   ├── routers/            # API路由 (auth.py, roles.py, users.py, permissions.py)
│   ├── services/           # 业务逻辑 (role_service.py, user_service.py)
│   ├── models/             # Pydantic模型 (role.py, permission.py, user.py)
│   ├── schemas/            # 请求/响应schema
│   ├── app/core/           # 核心功能 (auth.py)
│   └── database.py         # MongoDB连接
└── web/                    # Vue 3 前端
    ├── src/
    │   ├── views/          # 页面组件 (admin/Users.vue, admin/Roles.vue)
    │   ├── api/             # API调用 (users.js, roles.js, permissions.js)
    │   ├── router/          # 路由配置
    │   └── utils/          # 工具函数 (auth.js)
    └── vite.config.js
```

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution文件为空，无约束冲突。

| Gate | Status | Notes |
|------|--------|-------|
| 预设角色保护 | PASS | 将在数据模型中标记 role_type="preset" |
| 继承循环检测 | PASS | 将在服务层实现循环检测算法 |
| 菜单权限联动 | PASS | Permission增加 menu_path 字段关联菜单 |

## Project Structure

### Documentation (this feature)

```text
specs/004-rbac-inheritance/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── contracts/           # Phase 1 output (if needed)
```

### Source Code (repository root)

```text
apps/api/
├── routers/
│   └── roles.py         # [MODIFY] 添加继承和权限验证
├── services/
│   └── role_service.py # [MODIFY] 实现继承链计算
├── models/
│   ├── role.py         # [MODIFY] 添加 role_type, parent_roles 字段
│   └── permission.py   # [MODIFY] 添加 menu_path 字段
├── schemas/
│   └── role.py         # [MODIFY] 更新Schema定义
└── deps.py             # [MODIFY] 添加权限验证依赖

apps/web/
├── src/views/admin/
│   └── Roles.vue       # [MODIFY] 添加继承选择和保护逻辑
├── src/router/
│   └── index.js        # [MODIFY] 菜单动态加载
├── src/api/
│   ├── roles.js        # [MODIFY] 权限验证API
│   └── permissions.js  # [MODIFY] 菜单权限获取
└── src/utils/
    └── auth.js        # [MODIFY] 权限数据缓存
```

**Structure Decision**: Web application - FastAPI backend + Vue3 frontend，使用现有目录结构。

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| 无 | - | - |