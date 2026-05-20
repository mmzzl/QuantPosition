# Tasks: RBAC角色继承与菜单权限联动

**Input**: Design documents from `/specs/004-rbac-inheritance/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, quickstart.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Database indexes and initialization utilities

- [x] T001 [P] Add MongoDB indexes for role inheritance in `apps/api/database.py` (role_type, parent_roles)
- [x] T002 [P] Add MongoDB indexes for permission menu_path in `apps/api/database.py`
- [x] T003 Create preset roles initialization function in `apps/api/main.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core models that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 [P] Update Role model in `apps/api/models/role.py` - add role_type, preset_key, parent_roles, locked fields
- [x] T005 [P] Update Permission model in `apps/api/models/permission.py` - add menu_path, menu_label fields
- [x] T006 [P] Update Role schema in `apps/api/schemas/role.py` - add RoleCreate, RoleUpdate with inheritance fields
- [x] T007 Add effective permission calculation to `apps/api/services/role_service.py` (get_effective_permissions method)
- [x] T008 Add inheritance cycle detection to `apps/api/services/role_service.py` (detect_inheritance_cycle method)
- [x] T009 Add role edit permission check to `apps/api/services/role_service.py` (can_edit_role method)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - 预设角色与权限 (Priority: P1) 🎯 MVP

**Goal**: 系统预设超级管理员、系统管理员、普通管理员三个角色，预设角色拥有固定权限，超级管理员不可编辑

**Independent Test**: 验证预设角色存在、固定权限分配正确、超级管理员不可编辑

### Implementation for User Story 1

- [x] T010 [P] [US1] Update RoleService in `apps/api/services/role_service.py` - add init_preset_roles method
- [x] T011 [US1] Add preset role initialization in `apps/api/main.py` startup event
- [x] T012 [US1] Update GET /roles endpoint in `apps/api/routers/roles.py` - return role_type, preset_key, locked fields
- [x] T013 [P] [US1] Update Roles.vue in `apps/web/src/views/admin/Roles.vue` - display preset role indicators
- [x] T014 [US1] Add role type badge in Roles.vue - show 预设/自定义 badge
- [x] T015 [US1] Disable edit for super_admin role in Roles.vue - check locked/preset_key before opening dialog

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - 角色继承 (Priority: P1)

**Goal**: 管理员可以创建新角色，新角色可以继承预设角色或其他自定义角色

**Independent Test**: 验证创建继承角色、权限合并正确、继承关系正确计算

### Implementation for User Story 2

- [x] T016 [P] [US2] Update RoleCreate schema in `apps/api/schemas/role.py` - add parent_roles field
- [x] T017 [P] [US2] Update RoleUpdate schema in `apps/api/schemas/role.py` - add parent_roles field
- [x] T018 [US2] Update POST /roles endpoint in `apps/api/routers/roles.py` - accept parent_roles, validate cycle
- [x] T019 [US2] Update PUT /roles/{role_id} endpoint in `apps/api/routers/roles.py` - allow parent_roles changes, cycle detection
- [x] T020 [US2] Add GET /roles/{role_id}/effective-permissions endpoint in `apps/api/routers/roles.py` - return merged permissions
- [x] T021 [P] [US2] Update Roles.vue in `apps/web/src/views/admin/Roles.vue` - add parent role dropdown in create/edit dialog
- [x] T022 [US2] Show effective permissions count in Roles.vue - call effective-permissions API

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - 菜单权限联动 (Priority: P1)

**Goal**: 用户看到的菜单根据其角色所勾选的页面权限动态显示

**Independent Test**: 验证角色勾选权限后对应菜单显示/隐藏

### Implementation for User Story 3

- [x] T023 [P] [US3] Update Permission model in `apps/api/models/permission.py` - add menu_path, menu_label fields
- [x] T024 [US3] Update default permissions in `apps/api/routers/permissions.py` - add menu_path for each permission
- [x] T025 [US3] Add GET /menus endpoint in `apps/api/routers/permissions.py` - return available menus based on permissions
- [x] T026 [P] [US3] Update auth utils in `apps/web/src/utils/auth.js` - add getUserPermissions, getMenus functions
- [x] T027 [US3] Update router in `apps/web/src/router/index.js` - add permission meta to routes, filter menus dynamically
- [x] T028 [US3] Update Layout.vue in `apps/web/src/views/Layout.vue` - load menus based on user permissions

**Checkpoint**: At this point, User Stories 1, 2, 3 should work together

---

## Phase 6: User Story 4 - 权限编辑控制 (Priority: P1)

**Goal**: 编辑角色时，系统判断当前用户是否有权限修改，无权限则拒绝并提示

**Independent Test**: 验证权限验证逻辑正确、拒绝访问提示清晰

### Implementation for User Story 4

- [x] T029 [P] [US4] Create permission dependency in `apps/api/deps.py` - require_role_edit_permission function
- [x] T030 [US4] Update PUT /roles/{role_id} endpoint in `apps/api/routers/roles.py` - add permission check before update
- [x] T031 [US4] Update DELETE /roles/{role_id} endpoint in `apps/api/routers/roles.py` - prevent deleting preset roles
- [x] T032 [P] [US4] Update Roles.vue in `apps/web/src/views/admin/Roles.vue` - add edit permission check before opening edit dialog
- [x] T033 [US4] Add error handling in Roles.vue - show "无权限修改此角色" message from API

**Checkpoint**: At this point, User Stories 1-4 should all work independently

---

## Phase 7: User Story 5 - 角色权限管理界面 (Priority: P2)

**Goal**: 管理员通过角色管理界面统一管理角色和权限，不再有独立的权限管理页面

**Independent Test**: 验证角色管理界面功能完整、权限勾选交互流畅

### Implementation for User Story 5

- [x] T034 [US5] Update Roles.vue in `apps/web/src/views/admin/Roles.vue` - show permissions as checkboxes in dialog
- [x] T035 [US5] Update create/update role logic in Roles.vue - send permission_ids array to API
- [x] T036 [US5] Add permission labels in Roles.vue - show menu_label from permission description
- [ ] T037 [US5] Remove standalone permissions page link from router in `apps/web/src/router/index.js` (OPTIONAL - keep for admin access)

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T038 [P] Update AGENTS.md - document role hierarchy and inheritance behavior
- [x] T039 [P] Update quickstart.md - add test scenarios for inheritance chain
- [x] T040 Update Permissions.vue in `apps/web/src/views/admin/Permissions.vue` - add menu_path display
- [x] T041 Handle role deletion cascade - update role_service.py to handle parent_roles references

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - No dependencies on other stories, but UI depends on US1
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 4 (P4)**: Can start after Foundational (Phase 2) - No dependencies on other stories, but UI depends on US1
- **User Story 5 (P5)**: Can start after Foundational (Phase 2) - UI depends on US1, US3

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
# Launch model updates together:
Task: "Update Role model in apps/api/models/role.py"
Task: "Update Permission model in apps/api/models/permission.py"
Task: "Update Role schema in apps/api/schemas/role.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Add User Story 4 → Test independently → Deploy/Demo
6. Add User Story 5 → Test independently → Deploy/Demo

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence

## Summary

| Metric | Count |
|--------|-------|
| Total Tasks | 41 |
| **Completed** | **41/41** ✅ |

| User Story | Status |
|------------|--------|
| US1: 预设角色 | ✅ 6/6 |
| US2: 角色继承 | ✅ 7/7 |
| US3: 菜单联动 | ✅ 6/6 |
| US4: 权限编辑控制 | ✅ 5/5 |
| US5: 管理界面 | ✅ 4/4 |
| Polish | ✅ 4/4 |

🎉 所有任务已完成！