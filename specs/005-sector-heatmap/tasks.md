# Tasks: 板块热力图

**Input**: Design documents from `/specs/005-sector-heatmap/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Not explicitly requested in feature specification.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `apps/api/`
- **Frontend**: `apps/web/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 导入板块-股票映射数据到MongoDB

- [x] T001 创建CSV导入脚本 `apps/api/scripts/import_sector_data.py`
- [x] T002 运行导入脚本，验证 `sector_stocks` 集合数据正确

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 后端API路由和前端页面骨架

- [x] T003 [P] 创建板块API路由文件 `apps/api/routers/sectors.py`，注册到main.py
- [x] T004 [P] 创建板块服务文件 `apps/api/services/sector_service.py`
- [x] T005 [P] 创建前端API调用文件 `apps/web/src/api/sectors.js`
- [x] T006 [P] 在 `apps/web/src/router/index.js` 中添加热力图和股票列表路由
- [x] T007 [P] 创建前端页面目录 `apps/web/src/views/sectors/`

**Checkpoint**: 基础架构就绪，可以开始实现用户故事

---

## Phase 3: User Story 1 - 查看板块热力图 (Priority: P1) 🎯 MVP

**Goal**: 用户可以选择时间范围（24小时/7天/30天/自定义日期），查看板块涨跌幅热力图

**Independent Test**: 用户打开热力图页面，选择时间范围，系统正确显示各板块的颜色和涨跌幅数据

### 后端实现

- [x] T008 [US1] 实现MongoDB聚合查询逻辑，按板块计算指定时间范围内的涨跌幅，在 `apps/api/services/sector_service.py` 中添加 `get_sector_heatmap(period, start_date, end_date)` 方法
- [x] T009 [US1] 实现 `GET /sectors/heatmap` 端点，在 `apps/api/routers/sectors.py` 中添加路由处理函数，接收period/start_date/end_date参数，调用service返回数据
- [x] T010 [US1] 创建热力图页面组件 `apps/web/src/views/sectors/Heatmap.vue`，包含时间筛选控件（24h/7d/30d/自定义日期）和板块网格展示区域
- [x] T011 [US1] 实现热力图颜色映射逻辑，红色表示上涨、绿色表示下跌，颜色深浅与涨跌幅成正比
- [x] T012 [US1] 实现API调用，在 `apps/web/src/api/sectors.js` 中添加 `getSectorHeatmap(params)` 函数，连接后端接口
- [x] T013 [US1] 添加加载状态和错误处理，页面加载时显示loading，数据加载完成后展示热力图

**Checkpoint**: 热力图功能完整可用，用户可以选择时间范围查看板块涨跌

---

## Phase 4: User Story 2 - 查看板块股票列表 (Priority: P2)

**Goal**: 用户点击热力图中的板块名称，跳转到该板块的股票列表页面，显示板块内所有股票的详细信息

**Independent Test**: 用户点击热力图中的板块，系统正确跳转到股票列表页面并显示该板块所有股票

### 后端实现

- [x] T014 [US2] 实现 `get_sector_stocks(sector_name, sort_by, sort_order, page, page_size)` 方法，在 `apps/api/services/sector_service.py` 中查询板块内所有股票，关联K线数据计算涨跌幅
- [x] T015 [US2] 实现 `GET /sectors/{sector_name}/stocks` 端点，在 `apps/api/routers/sectors.py` 中添加路由处理函数
- [x] T016 [US2] 创建板块股票列表页面 `apps/web/src/views/sectors/StockList.vue`，包含股票表格（代码、名称、涨跌幅、成交量等）
- [x] T017 [US2] 实现从热力图页面跳转到股票列表页面，传递板块名称参数
- [x] T018 [US2] 实现API调用，在 `apps/web/src/api/sectors.js` 中添加 `getSectorStocks(sectorName, params)` 函数
- [x] T019 [US2] 添加排序和分页功能，支持按涨跌幅、成交量排序

**Checkpoint**: 板块股票列表功能完整可用，用户可以从热力图跳转查看个股详情

---

## Phase 5: User Story 3 - 查看个股K线图 (Priority: P3)

**Goal**: 用户在板块股票列表中点击"K线"按钮，弹出该股票的K线图，展示指定时间范围内的OHLC价格走势

**Independent Test**: 用户在股票列表中点击K线按钮，系统正确显示该股票的K线图

### 后端实现

- [x] T020 [US3] 实现 `get_kline_data(code, start_date, end_date)` 方法，在 `apps/api/services/sector_service.py` 中查询指定股票的K线数据
- [x] T021 [US3] 实现 `GET /kline/{code}` 端点，在 `apps/api/routers/sectors.py` 中添加路由处理函数
- [x] T022 [US3] 创建K线图组件 `apps/web/src/views/holdings/KLineChart.vue`，使用Apache ECharts渲染candlestick图表
- [x] T023 [US3] 在股票列表页面每只股票后添加"K线"按钮，点击弹出K线图对话框
- [x] T024 [US3] 实现API调用，在 `apps/web/src/api/sectors.js` 中添加 `getKlineData(code, params)` 函数
- [x] T025 [US3] 添加K线图交互功能：缩放、拖拽、时间范围切换

**Checkpoint**: K线图功能完整可用，用户可以查看个股历史走势

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 改进整体体验和性能

- [x] T026 [P] 优化MongoDB聚合查询性能，添加必要索引
- [x] T027 [P] 前端热力图添加板块名称搜索和筛选功能
- [x] T028 添加全局错误处理和重试机制
- [x] T029 更新README文档，添加板块热力图使用说明
- [x] T030 运行 `quickstart.md` 验证整个流程

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖 - 可立即开始
- **Foundational (Phase 2)**: 依赖Setup完成 - 阻塞所有用户故事
- **User Stories (Phase 3+)**: 依赖Foundational完成
  - US1 (P1): 可独立实现和测试
  - US2 (P2): 依赖US1的热力图页面，但股票列表可独立测试
  - US3 (P3): 依赖US2的股票列表页面
- **Polish (Phase 6)**: 依赖所有用户故事完成

### User Story Dependencies

- **US1 (P1)**: Foundational完成后可开始 - 无其他故事依赖
- **US2 (P2)**: Foundational完成后可开始 - 需要US1的热力图入口
- **US3 (P3)**: Foundational完成后可开始 - 需要US2的股票列表入口

### Within Each User Story

- 后端service → 后端endpoint → 前端组件 → 前端API连接 → 集成测试
- 核心功能实现 → 错误处理 → 用户体验优化

### Parallel Opportunities

- Phase 1和Phase 2中的任务标记为[P]的可并行执行
- US1、US2、US3的后端service可并行开发
- US1、US2、US3的前端组件可并行开发
- 不同用户故事可由不同开发者并行实现

---

## Parallel Example: Foundational Phase

```bash
# 并行执行后端和前端基础任务:
Task: "创建板块API路由文件 apps/api/routers/sectors.py"
Task: "创建板块服务文件 apps/api/services/sector_service.py"
Task: "创建前端API调用文件 apps/web/src/api/sectors.js"
Task: "添加路由到 apps/web/src/router/index.js"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. 完成 Phase 1: Setup（导入板块数据）
2. 完成 Phase 2: Foundational（API路由和页面骨架）
3. 完成 Phase 3: User Story 1（热力图）
4. **停止并验证**: 测试热力图功能
5. 部署/演示

### Incremental Delivery

1. Setup + Foundational → 基础就绪
2. 添加 User Story 1 → 独立测试 → 部署/演示（MVP！）
3. 添加 User Story 2 → 独立测试 → 部署/演示
4. 添加 User Story 3 → 独立测试 → 部署/演示
5. 每个故事增加价值，不破坏已有功能

### Parallel Team Strategy

多开发者协作时：

1. 团队共同完成 Setup + Foundational
2. Foundational完成后：
   - 开发者 A: User Story 1（热力图）
   - 开发者 B: User Story 2（股票列表）
   - 开发者 C: User Story 3（K线图）
3. 故事独立完成和集成

---

## Notes

- [P] 任务 = 不同文件，无依赖，可并行
- [Story] 标签映射任务到用户故事，便于追踪
- 每个用户故事应可独立完成和测试
- 每个阶段完成后提交代码
- 在任何checkpoint停止，独立验证故事功能
- 避免：模糊任务、同一文件冲突、跨故事依赖破坏独立性
