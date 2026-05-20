# fcntl Windows 兼容性规格说明

## 概述 (Overview)

将 `apps/api/systems/single.py` 中的 fcntl 文件锁实现改为跨平台兼容，支持 Linux 和 Windows。

## 用户故事 (User Stories)

### P0 - 核心需求
- **US1**: 作为开发者，我希望在 Windows 上运行应用时能够正常使用单例/文件锁功能，而不会因为 fcntl 不存在而报错

## 功能需求 (Functional Requirements)

### FR-001: 跨平台文件锁
- 使用 msvcrt (Windows) 或 fcntl (Linux) 实现文件锁
- 保持原有的 API 接口不变
- 自动检测平台并选择对应的实现

### FR-002: 锁类型兼容
- LOCK_EX (排他锁) → Windows 使用 msvcrt.LK_LOCK
- LOCK_NB (非阻塞) → Windows 使用 msvcrt.LK_NBLCK
- LOCK_UN (解锁) → Windows 使用 msvcrt.LK_UNLCK

### FR-003: 错误处理兼容
- Windows 和 Linux 抛出不同的异常类型
- 需要统一的异常处理方式

## 验收标准 (Success Criteria)

### SC-001: Windows 测试通过
- 在 Windows 上运行不报错，能够正常获取/释放文件锁
- 单例模式在 Windows 上正常工作

### SC-002: Linux 兼容保持
- 修改后的代码在 Linux 上仍然正常工作
- 不破坏现有的 Linux 功能

### SC-003: API 兼容性
- 类名、方法名、参数列表保持不变
- 现有代码无需修改即可继续使用