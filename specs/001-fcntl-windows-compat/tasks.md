---

description: "Task list for fcntl Windows compatibility feature"
---

# Tasks: fcntl Windows 兼容性

**Input**: Design documents from `/specs/001-fcntl-windows-compat/`
**Prerequisites**: plan.md (required), spec.md (required for user stories)

**Tests**: 本项目不需要额外测试文件，直接修改现有代码

**Organization**: 任务按用户故事分组以实现独立实现和测试

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可以并行运行（不同文件，无依赖）
- **[Story]**: 属于哪个用户故事 (例如 US1)
- 描述中包含具体文件路径

---

## Phase 1: 实现 (Implementation)

**Purpose**: 实现跨平台文件锁功能

### Implementation for User Story 1 - 跨平台文件锁

- [ ] T001 [US1] 修改 apps/api/systems/single.py 添加平台检测逻辑
- [ ] T002 [US1] 实现 Windows (msvcrt) 文件锁函数
- [ ] T003 [US1] 实现 Linux (fcntl) 文件锁函数（保留原有实现）
- [ ] T004 [US1] 修改 ScriptSingle 类使用新的跨平台锁函数
- [ ] T005 [US1] 确保 Windows 下文件以二进制模式打开 ('wb')

---

## Phase 2: 验证 (Verification)

**Purpose**: 验证修改在 Windows 和 Linux 上都能正常工作

- [ ] T006 [US1] 验证 Windows 平台文件锁功能正常
- [ ] T007 [US1] 验证 Linux 平台文件锁功能正常（回归测试）
- [ ] T008 [US1] 验证单例模式在不同平台上正常工作

---

## Dependencies & Execution Order

### Phase Dependencies

- **实现 (Phase 1)**: 无依赖 - 可以立即开始
- **验证 (Phase 2)**: 依赖于实现完成

### Within Each Phase

- 平台检测逻辑 → Windows 锁实现 → Linux 锁保留 → 整合到类中
- 修改完成后进行验证测试

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. 完成 Phase 1: 实现跨平台文件锁
2. 完成 Phase 2: 验证 Windows 和 Linux
3. 验证通过后即可完成

### 并行机会

由于任务简单，顺序执行即可，无需并行

---

## Notes

- 本任务直接修改现有文件 `apps/api/systems/single.py`
- 不需要创建新文件
- 保持原有 API 接口不变
- Windows 需要以二进制模式写入 PID