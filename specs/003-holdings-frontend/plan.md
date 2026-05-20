# Implementation Plan: 持仓管理系统 + Vue3 前端

**Branch**: `002-auth-rbac-mongodb` | **Date**: 2026-05-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-holdings-frontend/spec.md`

## Summary

实现一个完整的持仓管理系统，包含：
1. 后端：完善 holdings.py 的全部 API（买入、卖出、持仓列表、历史记录、交易记录、盈亏计算、组合汇总、卖出规则）
2. 前端：Vue 3 + Element Plus 管理后台（登录、注册、用户管理、角色管理、持仓管理）
3. 股票行情：接入新浪行情 API 获取 A 股实时价格

## Technical Context

**Language/Version**: Python 3.11 (后端) | Vue 3 (前端)  
**Primary Dependencies**: FastAPI, MongoDB (pymongo), JWT (python-jose), Vue 3, Vite, Element Plus, Axios  
**Storage**: MongoDB  
**Testing**: pytest (后端) | 手动测试 (前端)  
**Target Platform**: Web 浏览器 (桌面端 1024px+)  
**Project Type**: Web Service + Web Application  
**Performance Goals**: 页面加载 ≤2秒  
**Constraints**: 无特殊约束  
**Scale/Scope**: 单用户到多用户系统

## Constitution Check

* constitution.md 为空/模板状态，跳过检查 *

## Project Structure

### Documentation (this feature)

```text
specs/003-holdings-frontend/
├── plan.md              # 本文件
├── research.md          # Phase 0 研究结果
├── data-model.md        # Phase 1 数据模型
├── quickstart.md        # Phase 1 快速开始
├── contracts/           # Phase 1 接口契约
│   └── api-contracts.md
└── tasks.md            # Phase 2 任务列表 (由 /speckit.tasks 生成)
```

### Source Code (repository root)

```text
apps/
├── api/                 # FastAPI 后端 (现有)
│   ├── main.py
│   ├── database.py
│   ├── models/
│   ├── services/
│   ├── routers/
│   ├── schemas/
│   └── app/endpoints/
│       └── holdings.py  # 持仓 API (待实现)
└── web/                 # Vue 3 前端 (新建)
    ├── src/
    │   ├── components/
    │   ├── views/
    │   ├── router/
    │   ├── store/
    │   ├── api/
    │   └── utils/
    ├── package.json
    └── vite.config.js
```

**Structure Decision**: 采用前后端分离结构，后端位于 apps/api，前端位于 apps/web

## Complexity Tracking

> 无复杂度违规

---

## Phase 0: Research

Research.md 已生成，包含技术决策：
- 新浪行情 API 集成方案
- Vue 3 + Element Plus 最佳实践
- JWT 认证流程
- MongoDB 持仓数据模型设计

## Phase 1: Design

已生成：
- data-model.md - 数据模型定义
- quickstart.md - 快速开始指南
- contracts/api-contracts.md - API 接口契约