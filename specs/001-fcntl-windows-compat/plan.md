# fcntl Windows 兼容实现计划

## 技术栈

- Python 3.x
- 平台检测: `sys.platform`
- Windows 文件锁: `msvcrt` 模块
- Linux 文件锁: `fcntl` 模块

## 数据模型

无需新增数据模型，仅修改现有代码。

## 实现方案

### 平台检测策略
```python
import sys

if sys.platform == 'win32':
    import msvcrt
else:
    import fcntl
```

### 文件路径
- 原文件: `apps/api/systems/single.py`
- 测试文件: `apps/api/systems/test_single.py` (可选)

## 实现阶段

1. **Phase 1**: 修改 single.py，实现跨平台文件锁
2. **Phase 2**: 测试验证 (Windows + Linux)

## 技术约束

- 必须保持向后兼容
- 不能修改现有类的调用方式
- Windows 锁文件需要以二进制模式打开 ('wb')
- Windows 下 PID 文件需要写入内容才能获取锁