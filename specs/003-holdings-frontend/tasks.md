---

description: "Task list for 持仓管理系统 + Vue3 前端 implementation"
---

# Tasks: 持仓管理系统 + Vue3 前端

**Input**: Design documents from `/specs/003-holdings-frontend/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

---

## Phase 1: Setup (项目初始化)

**Purpose**: Project initialization and basic structure

- [x] T001 Create Vue 3 frontend project structure in apps/web/
- [x] T002 Initialize package.json with Vue 3, Vite, Element Plus, Axios dependencies
- [x] T003 [P] Configure vite.config.js for development server
- [x] T004 [P] Create basic folder structure (components, views, router, store, api)

---

## Phase 2: Foundational (核心基础设施)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Create Holding model in apps/api/models/holding.py
- [x] T006 [P] Create Transaction model in apps/api/models/transaction.py
- [x] T007 Create holding service in apps/api/services/holding_service.py
- [x] T008 Create transaction service in apps/api/services/transaction_service.py
- [x] T009 [P] Implement Sina stock API utility in apps/api/utils/stock_api.py
- [x] T010 Setup JWT authentication middleware in apps/api/app/core/auth.py
- [x] T011 Configure CORS in apps/api/main.py for frontend access

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - 用户注册与登录 (Priority: P1) 🎯 MVP

**Goal**: 用户可以注册新账号、登录系统、登出

**Independent Test**: 可以通过注册新用户、登录、登出操作独立测试

### Backend Implementation

- [x] T012 [P] [US1] Implement register endpoint in apps/api/routers/auth.py
- [x] T013 [P] [US1] Implement login endpoint returning JWT token in apps/api/routers/auth.py
- [x] T014 [US1] Implement logout functionality (token blacklist or client-side removal)
- [x] T015 [US1] Add captcha verification for register/login in apps/api/routers/auth.py

### Frontend Implementation

- [x] T016 [P] [US1] Create Login view in apps/web/src/views/Login.vue
- [x] T017 [P] [US1] Create Register view in apps/web/src/views/Register.vue
- [x] T018 [US1] Create auth API service in apps/web/src/api/auth.js
- [x] T019 [US1] Implement JWT token storage and retrieval in apps/web/src/utils/auth.js
- [x] T020 [US1] Setup Vue Router with auth guards in apps/web/src/router/index.js
- [x] T021 [US1] Create Dashboard view in apps/web/src/views/Dashboard.vue

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - 持仓买入与卖出 (Priority: P1)

**Goal**: 用户可以买入新持仓、卖出已有持仓，系统记录所有交易

**Independent Test**: 可以通过添加持仓、卖出操作独立测试，数据会记录到交易历史

### Backend Implementation

- [x] T022 [P] [US2] Implement POST /holdings/{user_id} buy endpoint in apps/api/app/endpoints/holdings.py
- [x] T023 [P] [US2] Implement POST /holdings/{user_id}/{code}/sell endpoint in apps/api/app/endpoints/holdings.py
- [x] T024 [US2] Implement calculate average cost logic for add to existing holding
- [x] T025 [US2] Implement DELETE /holdings/{user_id}/{code} endpoint
- [x] T026 [US2] Add validation for sell quantity cannot exceed holding quantity
- [x] T027 [US2] Record transaction on every buy/sell operation

### Frontend Implementation

- [x] T028 [P] [US2] Create Holdings list view in apps/web/src/views/holdings/List.vue
- [x] T029 [P] [US2] Create Buy form view in apps/web/src/views/holdings/Buy.vue
- [x] T030 [US2] Create Sell form view in apps/web/src/views/holdings/Sell.vue
- [x] T031 [US2] Create holdings API service in apps/web/src/api/holdings.js
- [x] T032 [US2] Integrate stock price lookup from Sina API in frontend

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - 持仓查看与汇总 (Priority: P1)

**Goal**: 用户可以查看持仓列表、组合汇总、盈亏情况

**Independent Test**: 可以通过访问持仓列表和汇总页面独立测试

### Backend Implementation

- [x] T033 [P] [US3] Implement GET /holdings/{user_id} with pagination in apps/api/app/endpoints/holdings.py
- [x] T034 [P] [US3] Implement GET /holdings/{user_id}/history endpoint in apps/api/app/endpoints/holdings.py
- [x] T035 [P] [US3] Implement GET /transactions/{user_id} endpoint in apps/api/app/endpoints/holdings.py
- [x] T036 [US3] Implement GET /portfolio/{user_id} for portfolio summary in apps/api/app/endpoints/holdings.py
- [x] T037 [US3] Implement GET /pnl/{user_id} for realized P&L in apps/api/app/endpoints/holdings.py
- [x] T038 [US3] Integrate Sina stock API to get current prices for unrealized P&L calculation

### Frontend Implementation

- [x] T039 [P] [US3] Create Holdings list table with price display in apps/web/src/views/holdings/List.vue
- [x] T040 [P] [US3] Create History view in apps/web/src/views/holdings/History.vue
- [x] T041 [P] [US3] Create Transactions view in apps/web/src/views/holdings/Transactions.vue
- [x] T042 [US3] Create Portfolio summary view in apps/web/src/views/holdings/Summary.vue
- [x] T043 [US3] Display real-time stock prices from Sina API in holdings list

**Checkpoint**: At this point, all P1 user stories should be independently functional

---

## Phase 6: User Story 4 - 管理员用户管理 (Priority: P2)

**Goal**: 管理员可以查看用户列表、编辑用户信息、修改密码、分配角色、删除用户

**Independent Test**: 可以通过管理员操作用户 CRUD 独立测试

### Backend Implementation

- [x] T044 [P] [US4] Implement GET /users endpoint (admin only) in apps/api/routers/users.py
- [x] T045 [P] [US4] Implement GET /users/{user_id} endpoint in apps/api/routers/users.py
- [x] T046 [US4] Implement PUT /users/{user_id} endpoint in apps/api/routers/users.py
- [x] T047 [US4] Implement PUT /users/{user_id}/password endpoint in apps/api/routers/users.py
- [x] T048 [US4] Implement PUT /users/{user_id}/role endpoint in apps/api/routers/users.py
- [x] T049 [US4] Implement DELETE /users/{user_id} endpoint in apps/api/routers/users.py

### Frontend Implementation

- [x] T050 [P] [US4] Create Users list view in apps/web/src/views/admin/Users.vue
- [x] T051 [P] [US4] Create User edit dialog in apps/web/src/views/admin/Users.vue
- [x] T052 [US4] Create password change dialog in apps/web/src/views/admin/Users.vue
- [x] T053 [US4] Create role assignment dialog in apps/web/src/views/admin/Users.vue
- [x] T054 [US4] Create users API service in apps/web/src/api/users.js

**Checkpoint**: User Story 4 functional

---

## Phase 7: User Story 5 - 管理员角色与权限管理 (Priority: P2)

**Goal**: 管理员可以创建角色、编辑角色信息、分配权限、删除角色

**Independent Test**: 可以通过管理员操作角色 CRUD 独立测试

### Backend Implementation

- [x] T055 [P] [US5] Implement GET /roles endpoint in apps/api/routers/roles.py
- [x] T056 [P] [US5] Implement POST /roles endpoint in apps/api/routers/roles.py
- [x] T057 [US5] Implement PUT /roles/{role_id} endpoint in apps/api/routers/roles.py
- [x] T058 [US5] Implement DELETE /roles/{role_id} endpoint in apps/api/routers/roles.py
- [x] T059 [US5] Implement PUT /roles/{role_id}/permissions endpoint in apps/api/routers/roles.py
- [x] T060 [US5] Implement GET /permissions endpoint in apps/api/routers/permissions.py

### Frontend Implementation

- [x] T061 [P] [US5] Create Roles list view in apps/web/src/views/admin/Roles.vue
- [x] T062 [P] [US5] Create Role edit dialog with permission tree in apps/web/src/views/admin/Roles.vue
- [x] T063 [US5] Create roles API service in apps/web/src/api/roles.js

**Checkpoint**: User Story 5 functional

---

## Phase 8: User Story 6 - 管理员查看所有用户持仓 (Priority: P2)

**Goal**: 管理员可以查看所有用户的持仓情况

**Independent Test**: 可以通过管理员访问所有用户持仓页面独立测试

### Backend Implementation

- [x] T064 [P] [US6] Implement GET /holdings/admin endpoint in apps/api/app/endpoints/holdings.py
- [x] T065 [P] [US6] Implement GET /pnl/admin endpoint in apps/api/app/endpoints/holdings.py
- [x] T066 [US6] Add admin role verification middleware

### Frontend Implementation

- [x] T067 [P] [US6] Create Admin holdings view in apps/web/src/views/admin/Holdings.vue
- [x] T068 [US6] Create admin holdings API service in apps/web/src/api/admin.js

**Checkpoint**: All user stories functional

---

## Phase 9: Exit Rule (卖出规则)

**Goal**: 实现止损止盈规则功能

### Backend Implementation

- [x] T069 [P] GET /holdings/{user_id}/{code}/exit-rule endpoint
- [x] T070 [P] PUT /holdings/{user_id}/{code}/exit-rule endpoint

### Frontend Implementation

- [x] T071 Create exit rule dialog in apps/web/src/views/holdings/List.vue

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T072 [P] Add loading states and error handling across all views
- [x] T073 [P] Implement responsive layout for different screen sizes
- [x] T074 Add logout confirmation dialog
- [ ] T075 [P] Optimize stock API calls with caching
- [x] T076 Add validation messages for all forms
- [ ] T077 Run quickstart.md validation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-8)**: All depend on Foundational phase completion
  - User stories can proceed in parallel (if staffed) or sequentially in priority order
- **Polish (Phase 10)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **US2 (P1)**: Can start after Foundational - May integrate with US1 but independently testable
- **US3 (P1)**: Can start after Foundational - May integrate with US1/US2 but independently testable
- **US4 (P2)**: Can start after Foundational - Independent from US1-3
- **US5 (P2)**: Can start after Foundational - Independent from US1-4
- **US6 (P2)**: Can start after Foundational - Independent from US1-5

### Within Each User Story

- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- Models within a story marked [P] can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all backend endpoints for User Story 1 together:
Task: "Implement register endpoint in apps/api/routers/auth.py"
Task: "Implement login endpoint in apps/api/routers/auth.py"

# Launch all frontend views for User Story 1 together:
Task: "Create Login view in apps/web/src/views/Login.vue"
Task: "Create Register view in apps/web/src/views/Register.vue"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add US1 → Test independently → Deploy (MVP!)
3. Add US2 → Test independently → Deploy
4. Add US3 → Test independently → Deploy
5. Add US4, US5, US6 → Deploy

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (登录注册)
   - Developer B: User Story 2 (买入卖出)
   - Developer C: User Story 3 (持仓查看)
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence

---

## Summary

| 指标 | 值 |
|------|-----|
| **总任务数** | 77 |
| **用户故事数** | 6 + 1 (Exit Rule) |
| **并行机会** | 约 30 个 [P] 标记任务 |
| **MVP 范围** | Phase 1-3 (US1) |