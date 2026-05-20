# Implementation Plan: 板块热力图

**Branch**: `005-sector-heatmap` | **Date**: 2026-05-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-sector-heatmap/spec.md`

## Summary

基于MongoDB中的K线数据实现板块热力图功能，包括：
1. 后端新增板块聚合查询接口，按时间范围计算板块涨跌幅
2. 前端新增热力图页面，使用颜色映射展示板块涨跌
3. 新增板块股票列表页面，展示板块内个股详情
4. 新增K线图组件，展示个股OHLC价格走势
5. 将CSV板块-股票映射数据导入MongoDB

## Technical Context

**Language/Version**: Python 3.12 (后端), JavaScript/TypeScript (前端)  
**Primary Dependencies**: FastAPI, pymongo, Vue 3 + Element Plus, ECharts (K线图)  
**Storage**: MongoDB (已有K线数据，新增板块-股票映射集合)  
**Testing**: pytest (后端), Vitest (前端)  
**Target Platform**: Linux/Windows server + Web browser  
**Project Type**: Web application (FastAPI backend + Vue 3 frontend)  
**Performance Goals**: 热力图加载 < 3秒，股票列表 < 2秒，K线图渲染 < 1秒  
**Constraints**: MongoDB聚合查询需优化，避免全表扫描；前端大数据量渲染需虚拟化  
**Scale/Scope**: ~100个板块，~5000只股票，K线数据可能数百万条

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

宪法文件为模板状态，无具体约束。遵循项目现有架构和编码规范。

## Project Structure

### Documentation (this feature)

```text
specs/005-sector-heatmap/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
apps/api/
├── routers/
│   └── sectors.py           # 板块热力图API路由
├── services/
│   └── sector_service.py    # 板块聚合计算服务
├── data/
│   └── stock_industry.csv   # 板块-股票映射源文件
└── scripts/
    └── import_sector_data.py # CSV导入脚本

apps/web/
├── src/
│   ├── views/
│   │   ├── sectors/
│   │   │   ├── Heatmap.vue      # 板块热力图页面
│   │   │   └── StockList.vue    # 板块股票列表页面
│   │   └── holdings/
│   │       └── KLineChart.vue   # K线图组件（可复用）
│   ├── api/
│   │   └── sectors.js           # 板块API调用
│   └── router/
│       └── index.js             # 新增路由
```

**Structure Decision**: 采用现有Web应用结构，在 `apps/api/` 下新增板块相关路由和服务，在 `apps/web/` 下新增前端页面和组件。K线图组件放在 `holdings/` 目录下可复用。

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| MongoDB聚合管道 | K线数据量大，需高效聚合计算 | 逐条查询+Python计算太慢 |
| ECharts K线图 | 专业金融图表库，支持OHLC | 自绘复杂度高，交互差 |
