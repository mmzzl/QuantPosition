# Feature Specification: 后台界面重设计（深色量化终端风）

**Feature Branch**: `008-ui-redesign`
**Created**: 2026-08-04
**Status**: Draft
**Input**: 用户需求：后台页面"很难看"，希望重新设计，摆脱 Element Plus 默认模板感

## Summary

将持仓管理系统后台从 Element Plus 默认样式（浅色 + 深蓝侧边栏 #304156 + #409eff）重设计为**深色量化终端风**（类 Bloomberg 专业交易终端）。采用 Element Plus 深色模式 + CSS 变量令牌体系，全局框架（Layout/Login/Dashboard）深定制，核心页精修，其余页面通过令牌自动继承深色主题。

## 已批准的设计决策

| 决策 | 内容 |
|------|------|
| 视觉方向 | A · 深色量化终端（高信息密度，类 Bloomberg） |
| 强调色 | 青绿 Cyan `#22d3ee` |
| 涨跌色 | 红涨绿跌（A股约定） |
| 导航布局 | B · 文字侧边栏（保留现有结构，深色化） |
| 范围 | 全局框架 + 核心页优先，其余页面令牌自动覆盖 |
| 实现方案 | 方案1：EP 深色模式 + CSS 变量令牌体系 |

## Design

### 1. 设计系统

#### 1.1 色彩令牌

| 令牌 | 值 | 用途 |
|------|-----|------|
| `bg-base` | `#0b1220` | 页面底色（深海墨蓝） |
| `bg-sidebar` | `#0d1526` | 侧边栏 |
| `bg-elevated` | `#101c33` | 卡片/表格底 |
| `border` | `#1c2b44` | 边框、分割线 |
| `text-1` | `#dbe4f0` | 主文字 |
| `text-2` | `#7c93b5` | 次要文字 |
| `text-3` | `#4a5b7a` | 弱化文字/占位 |
| `accent` | `#22d3ee` | 强调青绿（激活菜单/主按钮/高亮） |
| `up` | `#f6465d` | 涨（A股红涨） |
| `down` | `#0ecb81` | 跌（A股绿跌） |
| `warning` | `#f5a623` | 警示 |

#### 1.2 字体

- 数字/价格：系统等宽回退栈（`ui-monospace`, `SFMono-Regular`, `Menlo`, `Consolas`），可选自托管 JetBrains Mono
- 界面文字：系统 CJK 栈（PingFang SC / Microsoft YaHei）
- 尺寸：表格 12px、正文 13px、标题 16px、页标题 20px

#### 1.3 密度与圆角

- 紧凑密度（终端感）：卡片 padding 缩紧、表格行高压缩
- 圆角 6px、卡片阴影极浅（深色下靠边框分层）

#### 1.4 布局

- 左侧固定 220px 文字侧边栏（深色）+ 顶部栏（页面标题 + 用户信息 + 退出）
- Element Plus 启用 `html.dark` + CSS 变量覆盖，所有页面自动继承深色

#### 1.5 文件结构

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/styles/theme.css` | 新增 | CSS 变量令牌 + EP 深色覆盖（统一入口，不分 dark.css） |
| `src/views/Layout.vue` | 重做 | 侧边栏 + 顶部栏 + 内容区 |
| `src/App.vue` | 调整 | 全局背景/字体/滚动条 |
| `src/main.js` | 调整 | 挂载 `dark` class + 引入 theme.css |
| `index.html` | 调整 | 等宽字体引入 |

### 2. 框架设计

#### 2.1 全局主题 (theme.css)

- CSS 变量令牌（见 1.1 色彩表）
- 覆盖 EP `--el-*` 变量：背景色、边框、主色 → 深色令牌
- 表格/卡片/按钮等组件自动适配深色

#### 2.2 字体加载 (index.html)

- 数字/价格用系统等宽回退栈（`ui-monospace`, `SFMono-Regular`, `Menlo`, `Consolas`），不引入外部 CDN
- 如视觉验收不满意数字对齐，再自托管 JetBrains Mono 字体包（可选）
- CJK 保持系统栈

#### 2.3 Layout.vue

- 侧边栏 220px，`#0d1526` 底
  - Logo 区：站点名，青色
  - 菜单项：hover 提亮，选中项左侧青色竖条 + 半透明高亮
  - 菜单项加图标（EP 图标库已全量注册）
- 顶部栏 `#0f1a2e` 底：左侧页面标题，右侧用户名 + 角色 tag + 退出按钮
- 内容区 `bg-base` 底色

#### 2.4 main.js

- 保留 `element-plus/dist/index.css` 基础样式 import
- 引入 `element-plus/theme-chalk/dark/css-vars.css`（EP 官方深色变量基底）
- 挂载 `document.documentElement.classList.add('dark')`
- 引入 theme.css 覆盖 EP 变量 → 本项目令牌

#### 2.5 App.vue

- 全局背景 `bg-base`、字体栈、深色滚动条样式

### 3. 核心页设计

#### 3.1 Login.vue

- 全屏 `bg-base` 深色底 + 纯 CSS 网格/斜纹背景质感（终端氛围）
- 居中卡片 `bg-elevated`，圆角 8px，边框 `border`
- 标题：站点名青色等宽感 + 副标题
- 输入框/按钮走 EP 深色，登录按钮青色主色
- 验证码、注册入口保留原逻辑，仅换样式
- 底部可选等宽小字点缀（当前时间/交易提示）

#### 3.2 Dashboard.vue

- 4 个统计卡：`bg-elevated` + 边框，图标色按 up/down/青色
- 数值等宽大字体，市值/盈亏红绿区分（遵循 A股 红涨绿跌，与 SC-004 一致）
- 卡片 hover 轻微上浮
- 快捷操作按钮深色主题
- 新增「今日行情摘要」占位区：**纯静态占位、默认隐藏、不接任何数据接口**（避免范围蔓延）

#### 3.3 深度定制核心页（5 页）

| 页面 | 文件 | 定制重点 |
|------|------|---------|
| 持仓列表 | `holdings/List.vue` | 表格深色化、涨跌红绿、等宽数字、操作按钮 |
| 板块热力图 | `sectors/Heatmap.vue` | 保留 CSS Grid 热力块，色阶适配深色、图例/标题重做 |
| 选股页 | `selections/DualMA.vue` | 表格 + 图表深色化、等宽数字 |
| 策略回测 | `backtest/BacktestDashboard.vue` | 数据密集表格、评分徽章、图表深色适配 |
| 交易规则 | `TradingRules.vue` | 条件构建器深色化、按钮/卡片 |

> 其余页面（admin/*、NewsView、RuleCandidates、RuleOptimized、selections/NewsSelection、HeatmapSelection、holdings 子页、backtest/Detail、sectors/StockList 等）通过令牌自动继承深色，后续迭代再精修。

### 4. 模拟盘模块移除（前后端）

#### 4.1 后端 (apps/api)

| 文件 | 操作 |
|------|------|
| `main.py` | 移除 import + include `paper_trading_router` |
| `routers/paper_trading.py` | 删除 |
| `services/paper_trade_service.py` | 删除 |
| `routers/menu.py` | 移除 `/paper-trading` 菜单项 |
| `config/menus.json` | 移除 `/paper-trading` 菜单条目（权限菜单事实来源，`routers/permissions.py` 动态读取） |
| `database.py` | 移除 `paper_positions` 三个索引创建（66-68 行） |
| `tests/test_paper_trade.py` | 删除 |

#### 4.2 前端 (apps/web)

| 文件 | 操作 |
|------|------|
| `views/paper/PaperTrading.vue` | 删除 |
| `views/paper/` 目录 | 删除 |
| `api/paperTrading.js` | 删除 |
| `router/index.js` | 移除 import + 路由 `paper-trading` |

## Success Criteria

### Measurable Outcomes

- **SC-001**: 登录后所有页面（含未深度定制的）均呈现深色主题，无白色刺眼区域
- **SC-002**: Layout 侧边栏/顶部栏/内容区三区配色符合令牌，选中菜单有青色竖条
- **SC-003**: 核心 5 页（持仓列表/热力图/选股/回测/交易规则）表格、图表、按钮均为深色终端风
- **SC-004**: 涨跌红绿在所有页面一致（up=#f6465d, down=#0ecb81），数字等宽对齐
- **SC-005**: 模拟盘前后端移除后，菜单、路由、API 均无 `paper-trading` 残留
- **SC-006**: `npm run build` 通过，无 ESLint 报错；后端 `pytest` 通过（移除相关测试后）

### Acceptance Scenarios

1. **Given** 用户访问登录页，**Then** 显示深色终端风登录卡片 + 网格背景，登录成功后进入深色 Dashboard
2. **Given** 用户浏览持仓列表/热力图等核心页，**Then** 表格/图表/按钮为深色主题，涨跌红绿、数字等宽
3. **Given** 用户进入非核心页（如系统设置），**Then** 页面自动为深色，无浅色残留
4. **Given** 用户打开菜单，**Then** 不存在「模拟盘」入口，手动访问 `/paper-trading` 返回 404
5. **Given** 执行构建与测试，**Then** 前端 build 成功、后端 pytest 全绿

## Testing Strategy

| Test | Scope | Method |
|------|-------|--------|
| 前端构建 | apps/web | `npm run build` + `npm run lint` |
| 后端测试 | apps/api | `pytest`（移除 paper_trade 测试后全绿） |
| 路由回归 | apps/web | 访问 `/paper-trading` 应 404；菜单无模拟盘 |
| 视觉验收 | 核心页 + 登录/首页 | 每页人工截图检查深色一致性、红绿、等宽数字 |
| API 残留检查 | apps/api | grep 无 `paper_trading` / `paper-trading` 引用 |

## Assumptions

- 系统等宽字体回退栈足够清晰（不引入外部字体 CDN，避免离线/内网部署问题）；如用户要求精确对齐再用 JetBrains Mono 自托管
- 热力图色阶沿用现有 CSS Grid 实现，仅替换颜色值适配深色背景
- ECharts 图表统一在图表初始化处设置深色主题/色板，与页面重构同步

## Self-Check Checklist

- [ ] 无占位符/未填内容
- [ ] 色彩令牌全表引用一致（bg-base/border/accent/up/down 等在本文件内定义）
- [ ] 范围明确：核心页 5 + 框架 3 + 模块移除，其余页面令牌覆盖
- [ ] 无矛盾：模拟盘在「已批准决策」中未列为深度定制，与「第4章移除」一致
