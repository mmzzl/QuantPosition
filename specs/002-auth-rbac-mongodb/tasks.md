---

description: "Task list for RBAC user-role-permission system with MongoDB"
---

# Tasks: 用户角色权限系统 (RBAC)

**Input**: Design documents from `/specs/002-auth-rbac-mongodb/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), data-model.md, quickstart.md

**Tests**: 本项目不需要额外测试文件

**Organization**: 任务按用户故事分组以实现独立实现和测试

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可以并行运行（不同文件，无依赖）
- **[Story]**: 属于哪个用户故事 (例如 US1, US2, US3, US4)
- 描述中包含具体文件路径

---

## Phase 1: Setup (项目初始化)

**Purpose**: 项目初始化和基础依赖

- [X] T001 安装依赖: fastapi, uvicorn, pymongo, python-jose, passlib, pydantic
- [X] T002 创建 apps/api/database.py - MongoDB连接配置
- [X] T003 创建 apps/api/config.py - 应用配置 (JWT密钥, 数据库URL等)

---

## Phase 2: Foundational (基础模块)

**Purpose**: 所有用户故事依赖的基础模块

- [X] T004 [P] 创建 apps/api/models/user.py - User模型定义
- [X] T005 [P] 创建 apps/api/models/role.py - Role模型定义
- [X] T006 [P] 创建 apps/api/models/permission.py - Permission模型定义
- [X] T007 [P] 创建 apps/api/schemas/user.py - 用户Schema (创建/更新/响应)
- [X] T008 [P] 创建 apps/api/schemas/role.py - 角色Schema
- [X] T009 [P] 创建 apps/api/schemas/permission.py - 权限Schema
- [X] T010 [P] 创建 apps/api/schemas/token.py - Token Schema (登录响应)

---

## Phase 3: User Story 4 - 认证与授权 (Priority: P1) 🎯 MVP

**Goal**: 用户可以使用用户名密码登录并获取JWT令牌

**Independent Test**: 登录API返回有效令牌，无效凭证返回错误

### Implementation for User Story 4

- [X] T011 [US4] 扩展 apps/api/app/core/auth.py - 实现JWT创建和验证函数
- [X] T012 [US4] 创建 apps/api/routers/auth.py - 登录和注册路由
- [X] T013 [US4] 创建 apps/api/deps.py - 依赖注入 (获取当前用户)

**Checkpoint**: 用户可以注册、登录、获取JWT令牌

---

## Phase 4: User Story 1 - 用户管理 (Priority: P1)

**Goal**: 管理员能够创建、修改、禁用和删除用户

**Independent Test**: 通过API创建用户、查询列表、更新信息、禁用用户

### Implementation for User Story 1

- [X] T014 [P] [US1] 创建 apps/api/services/user_service.py - 用户服务 (CRUD)
- [X] T015 [US1] 创建 apps/api/routers/users.py - 用户管理路由

**Checkpoint**: 用户管理API完整可用

---

## Phase 5: User Story 3 - 权限管理 (Priority: P2)

**Goal**: 管理员能够创建和管理权限，支持资源级别访问控制

**Independent Test**: 通过API创建权限、验证权限

### Implementation for User Story 3

- [X] T016 [P] [US3] 创建 apps/api/services/permission_service.py - 权限服务
- [X] T017 [US3] 创建 apps/api/routers/permissions.py - 权限管理路由

**Checkpoint**: 权限管理API完整可用

---

## Phase 6: User Story 2 - 角色管理 (Priority: P1)

**Goal**: 管理员能够创建、修改和删除角色，绑定权限和用户

**Independent Test**: 通过API创建角色、分配权限、绑定用户

### Implementation for User Story 2

- [X] T018 [P] [US2] 创建 apps/api/services/role_service.py - 角色服务
- [X] T019 [US2] 创建 apps/api/routers/roles.py - 角色管理路由
- [X] T020 [US2] 扩展 apps/api/deps.py - 添加权限检查依赖

**Checkpoint**: 角色管理API完整可用，权限检查生效

---

## Phase 7: Integration (集成)

**Purpose**: 确保所有组件正常工作

- [ ] T021 集成测试: 注册 → 登录 → 获取用户信息
- [ ] T022 集成测试: 创建权限 → 创建角色 → 绑定权限 → 验证权限
- [ ] T023 集成测试: 权限不足时返回403

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖 - 可以立即开始
- **Foundational (Phase 2)**: 依赖于Setup完成
- **User Story 4 (Phase 3)**: 依赖于Foundational - 认证是基础
- **User Story 1 (Phase 4)**: 依赖于Phase 3 (认证)
- **User Story 3 (Phase 5)**: 依赖于Foundational
- **User Story 2 (Phase 6)**: 依赖于Phase 3 (权限) + Phase 5 (权限)

### User Story Dependencies

- **User Story 4 (P1)**: 第一个实现 - 其他所有功能的认证基础
- **User Story 1 (P1)**: 第二个实现 - 用户管理
- **User Story 3 (P2)**: 第三个实现 - 权限管理（角色依赖）
- **User Story 2 (P1)**: 第四个实现 - 角色管理（依赖权限）

### Within Each User Story

- Models → Schemas → Services → Routers
- 核心功能完成后进行集成测试

### Parallel Opportunities

- Phase 2的所有模型和Schema任务可以并行 (T004-T010)
- Phase 3的实现可以与Phase 2并行开始
- Phase 5和Phase 6可以并行（各自独立）

---

## Parallel Example: Phase 2 Foundational

```bash
Task: "创建 apps/api/models/user.py - User模型定义"
Task: "创建 apps/api/models/role.py - Role模型定义"
Task: "创建 apps/api/models/permission.py - Permission模型定义"
Task: "创建 apps/api/schemas/user.py - 用户Schema"
Task: "创建 apps/api/schemas/role.py - 角色Schema"
Task: "创建 apps/api/schemas/permission.py - 权限Schema"
```

---

## Implementation Strategy

### MVP First (User Story 4 Only)

1. 完成 Phase 1: Setup
2. 完成 Phase 2: Foundational (T004-T010)
3. 完成 Phase 3: User Story 4 - 认证授权
4. **STOP and VALIDATE**: 用户可以注册、登录
5. 部署MVP

### Incremental Delivery

1. 完成 Phase 1 + Phase 2 → 基础就绪
2. 添加 Phase 3 → 用户可以注册登录 (MVP!)
3. 添加 Phase 4 → 用户管理功能
4. 添加 Phase 5 → 权限管理功能
5. 添加 Phase 6 → 角色管理功能 (完整RBAC!)
6. 每阶段独立测试验证

---

## Notes

- 本项目不需要单独测试文件，直接实现功能代码
- 认证(US4)应该是第一个实现的用户故事，因为其他所有功能都依赖它
- 权限(US3)需要在角色(US2)之前实现，因为角色需要绑定权限
- 使用BCrypt进行密码加密
- 使用JWT进行令牌认证