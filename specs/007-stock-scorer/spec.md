# Feature Specification: 统一短线评分系统

**Feature Branch**: `007-stock-scorer`
**Created**: 2026-07-10
**Status**: Draft
**Input**: User requirements: 一套统一的评分规则，应用于整个项目（回测、实盘买入推荐、收盘选股），短线 1~10 交易日的独立打分模型

## Summary

创建 `StockScorer` 统一评分模块，为全市场 A 股提供 0-100 的短线评分（1~10 个交易日），集成日线量价分析、外部资金流数据（同花顺/东方财富/新浪）、板块热度、极简风控。评分体系独立于现有规则引擎（`rule_engine.py`），作为第二层排序/筛选依据。

## User Scenarios & Testing

### User Story 1 - 收盘选股按评分排序 (Priority: P1)

每个交易日 17:30，`review_picker.py` 调用 `StockScorer.score()` 对全市场 5000+ A 股打分，排除 ST/退市/指数，取总分 >= 60 的股票推送 Top 10。

**Acceptance Scenarios**:
1. **Given** 交易日 17:30，**When** 执行 `review_picker.py`，**Then** 输出按 `total` 降序的 Top 10 股票
2. **Given** 推送消息，**Then** 每只股票显示总分、评分等级、各维度得分
3. **Given** 股票满足 ST/退市/380 条件，**Then** 总分 = 0，不进入排名
4. **Given** 某维度 akshare 接口异常，**Then** 该维度 = 0，其他维度正常评分

### User Story 2 - 盘中推荐按评分排序 (Priority: P1)

每 5 分钟 `rule_engine.py` 执行规则后，候选买入股票用 `StockScorer.score()` 排序，买入信号只推送评分 >= 60 的股票。

**Acceptance Scenarios**:
1. **Given** rule_engine 产生多条买入候选，**When** 按评分排序，**Then** 只推送评分 >= 60 的股票
2. **Given** 候选股票评分 < 60，**Then** 不推送买入信号

### User Story 3 - 回测按评分筛选 (Priority: P2)

`backtest_engine.py` 在每个调仓日调用 `StockScorer.score()`，只买入评分 >= 60 的股票。

**Acceptance Scenarios**:
1. **Given** 回测第 N 日，**When** 筛选买入候选，**Then** 只考虑评分 >= 60 的股票
2. **Given** 多只候选股票，**When** 仓位有限，**Then** 按评分降序分配

### Edge Cases

- akshare 网络超时或返回空数据 → 对应维度计 0 分，记录 warning 日志，不影响其他维度
- 股票无日线 K 线数据（停牌/刚上市） → 量价维度 0 分
- 筹码分布接口失败 → 筹码因子 0 分，总分不受影响
- 东方财富接口被封 → 仍可用同花顺 (`stock_fund_flow_individual`) 获取资金流
- 全市场评分性能优化：量价维度纯本地计算（快），资金流用 `stock_fund_flow_individual("3日排行")` 一次获取全市场 top，join 查单只

## Requirements

### Functional Requirements

- **FR-001**: `StockScorer` MUST 提供 `score(code, name, date_str=None)` 统一入口，返回 `{total, breakdown, level, code, name, date}`
- **FR-002**: 总分范围 0-100，评分等级：S(>=80), A(60-79), B(40-59), C(<40)
- **FR-003**: `breakdown` MUST 包含四个维度：`price_volume`, `fund_chip`, `sector_theme`, `risk`
- **FR-004**: 量价维度 (40分) MUST 包含：均线多头+5日线站稳(15)、近3日放量上涨+回调缩量(12)、突破压力(8)、振幅适中(5)
- **FR-005**: 量价维度的扣分项（连续放量大跌/跌破20日线/高位放量滞涨）在规则触发时 MUST 使量价总分 = 0
- **FR-006**: 资金筹码维度 (35分) MUST 包含：主力资金净流入(12)、龙虎榜机构买入(10)、筹码集中度(8)、换手率(5)
- **FR-007**: 资金筹码维度的扣分项（连续大额资金流出）在规则触发时 MUST 使资金筹码总分 = 0
- **FR-008**: 题材板块维度 (20分) MUST 包含：板块资金热度(12)、板块指数涨幅(5)、概念热点(3)
- **FR-009**: 题材板块扣分项（行业指数 3 日跌 > 3%） MUST 使题材总分 = 0
- **FR-010**: 风控 (5分) MUST 为硬否决项：ST/退市预警/减持 → 总分 = 0
- **FR-011**: 所有 akshare 调用 MUST 使用 try/except 包裹，失败时对应维度 = 0，记录 logging.warning
- **FR-012**: akshare 数据在同一次运行内 MUST 做内存缓存（LRU），避免重复调用

### Key Entities

- **StockScorer**: 统一评分入口类，协调四个维度模块
- **评分维度模块**: `price_volume.py` / `fund_chip.py` / `sector_theme.py` / `risk_check.py`，每个模块独立 `score()` 函数
- **akshare LRU Cache**: 同一进程内缓存外部 API 结果，key = `(api_name, params_hash)`

## Success Criteria

### Measurable Outcomes

- **SC-001**: 全市场 5000+ 股票评分在 60 秒内完成（量价本地 + 资金流 batch + 板块 batch）
- **SC-002**: 单只股票评分 < 50ms（含缓存命中）
- **SC-003**: 外部 API 异常时维度降级不影响其他维度评分
- **SC-004**: 评分 >= 60 的股票在 3 个交易日内涨幅跑赢沪深 300 > 2%（回测验证）

## Assumptions

- 同花顺 `stock_fund_flow_individual()` 接口稳定可用，提供全市场资金流排名
- 新浪 `stock_lhb_detail_daily_sina()` 接口稳定可用，提供龙虎榜数据
- 东方财富 `stock_cyq_em()` 可能被封，对应维度 fallback 为 0
- 日线 K 线数据在 `stock_kline` 集合中可用
- 5 分钟 K 线数据（用于换手率等）在 `stock_kline_5m` 中可用

## Design

### Data Flow - K-Line Source

`StockScorer.score(code, name, date_str)` 内部自动从 MongoDB 获取数据，调用方无需传入 kline_data：

```
score(code, name, date_str=None)
  │
  ├─ date_str = date_str or today_str
  ├─ daily_klines = db.stock_kline.find({code, date <= date_str}).sort(date).limit(60)
  ├─ 传给 price_volume 子模块
  └→ _price_volume.score(daily_klines, date_str)    // 资金筹码子模块自取 5m 数据
```

**为什么不自外传入？** 三个调用方（review_picker/rule_engine/backtest）获取 K 线的方式不同，让 `StockScorer` 统一管理数据获取逻辑，避免重复代码。子模块 `price_volume.py` 接受显式 kline_data 参数方便单元测试。

### Architecture

```
StockScorer.score(code, name, date_str)
    │
    ├─ [从 MongoDB 获取 daily_klines + 5m_bars]
    │
    ├── _price_volume.score(daily_klines, date_str)   ← 纯本地，无外部依赖
    │      ├── check_ma_trend()          → 0-15
    │      ├── check_volume_price()      → 0-12
    │      ├── check_breakthrough()      → 0-8
    │      ├── check_amplitude()         → 0-5
    │      └── penalty_rules()           → 0 or skip
    │
    ├── _fund_chip.score(code, date_str)            ← akshare batch + single
    │      ├── fetch_fund_flow_rank()    → batch: 全市场排名
    │      ├── fetch_lhb()               → batch: 当日龙虎榜
    │      ├── fetch_cyq(code)            → single: 筹码分布 (try)
    │      └── turnover_rate(code)        → from kline_5m
    │
    ├── _sector_theme.score(code, date_str)         ← akshare batch
    │      ├── fetch_industry_fund_flow() → batch: 行业资金排名
    │      └── fetch_concept_fund_flow()  → batch: 概念资金排名
    │
    └── _risk_check.score(code)                    ← 纯本地 + akshare
           ├── is_st()                    → 硬否决 (本地前缀匹配)
           ├── is_delisting_risk()        → 硬否决 (本地名单)
           └── check_restricted_release() → 硬否决 (akshare try/except)

    └── aggregate: total = sum(4 dimensions)
                    level = S/A/B/C based on total
```

### Files to Create

| File | Type | Description |
|------|------|-------------|
| `specs/007-stock-scorer/spec.md` | 文档 | 本规格文档 |
| `services/stock_scorer.py` | 入口 | `StockScorer` 类，聚合四个维度 |
| `services/scorer/__init__.py` | 包 | 初始化空包，暴露各模块 |
| `services/scorer/price_volume.py` | 模块 | 量价趋势评分 (40分) |
| `services/scorer/fund_chip.py` | 模块 | 资金筹码评分 (35分) + akshare 缓存 |
| `services/scorer/sector_theme.py` | 模块 | 题材板块评分 (20分) |
| `services/scorer/risk_check.py` | 模块 | 极简风控 (5分) |

### Files to Modify

| File | Description |
|------|-------------|
| `bin/review_picker.py` | 替换 `calc_score()` 为 `StockScorer.score()` |
| `bin/rule_engine.py` | 候选买入用 `StockScorer.score()` 排序，过滤 >=60 |
| `services/backtest_engine.py` | 调仓日用 `StockScorer.score()` 排序 |

### Scoring Detail - 量价趋势 (40分)

#### 因子 1.1 短期均线多头+站稳5日线 (15分)

| 条件 | 得分 |
|------|:----:|
| MA5 > MA10 > MA20（多头排列） | 10 |
| close > MA5 | 5 |
| close < MA5 但 > MA10 | 2 |
| MA5 < MA20（空头排列） | 0 |

#### 因子 1.2 近3日放量上涨、回调缩量 (12分)

| 条件 | 得分 |
|------|:----:|
| 今日 volume > 5日均量 × 1.2（放量） | 4 |
| 今日 close > 3日前 close（上涨） | 4 |
| 3日内最大回撤日 volume < 5日均量（回调缩量） | 4 |

#### 因子 1.3 突破关键压力位 (8分)

| 条件 | 得分 |
|------|:----:|
| close > 近 20 日高点（箱体突破） | 8 |
| close > 近 10 日高点（短期突破） | 4 |
| 未突破 | 0 |

#### 因子 1.4 振幅适中 (5分)

| 5日平均振幅 | 得分 |
|-------------|:----:|
| 3%~8% | 5 |
| 2%~3% 或 8%~12% | 3 |
| <2% 或 >12% | 0 |

#### 扣分项（任何一项 → 量价总分 = 0）

- 连续放量大跌：近 3 日累跌 > 5% 且 每根 volume > 均量 × 1.5
- 跌破 20 日线：close < MA20
- 高位放量滞涨：近 20 日涨幅 > 30% 且 volume > 均量 × 1.3 且 当日涨幅 < 0.5%

### Scoring Detail - 资金筹码 (35分)

#### 因子 2.1 主力资金净流入 (12分)

数据源: `stock_fund_flow_individual("3日排行")`（同花顺）

| 条件 | 得分 |
|------|:----:|
| 近 3 日净流入为正 且 排名全市场前 500 | 12 |
| 近 3 日净流入为正 | 8 |
| 净流入为负 | 0 |
| API 异常 | 0 (log warning) |

#### 因子 2.2 龙虎榜机构买入 (10分)

数据源: `stock_lhb_detail_daily_sina()`（新浪）

| 条件 | 得分 |
|------|:----:|
| 今日上榜且净买入 > 0 | 10 |
| 今日上榜且净买入 < 0 | 0 |
| 今日未上榜 | 5 (中性) |
| API 异常 | 5 (中性) |

#### 因子 2.3 筹码集中度 (8分)

数据源: `stock_cyq_em()`（东方财富，try/except，失败跳0）

| 90% 成本集中度 | 得分 |
|----------------|:----:|
| < 10%（强控盘） | 8 |
| 10%~20%（集中） | 5 |
| > 20%（分散） | 2 |
| API 异常 | 0 |

#### 因子 2.4 换手率 (5分)

| 今日换手率 | 得分 |
|------------|:----:|
| 5%~18% | 5 |
| 3%~5% 或 18%~25% | 3 |
| <3% 或 >25% | 0 |

#### 扣分项（触发 → 资金筹码总分 = 0）

近 3 日主力净流入均为负，且累计流出 > 1 亿

> **性能注意**: `stock_cyq_em()` 是逐股调用，全市场 5000+ 逐一请求不可行。策略：如果接口可用，只对已通过量价门槛的候选股票（~前 200 只）调用；如果接口被封，直接跳过该因子（0 分）。

### Scoring Detail - 题材板块 (20分)

#### 因子 3.1 板块资金热度 (12分)

数据源: `stock_fund_flow_industry("3日排行")`（同花顺）

| 行业排名（按资金净流入） | 得分 |
|--------------------------|:----:|
| 前 5 | 12 |
| 前 10 | 8 |
| 前 20 | 4 |
| > 20 或 API 异常 | 0 |

#### 因子 3.2 板块指数涨幅 (5分)

| 板块指数 3 日涨幅 | 得分 |
|------------------|:----:|
| > 3% | 5 |
| > 1% | 3 |
| <= 1% | 0 |

#### 因子 3.3 概念热点加持 (3分)

数据源: `stock_fund_flow_concept("3日排行")`（同花顺）

| 条件 | 得分 |
|------|:----:|
| 个股所在概念板块资金排名前 5 | 3 |
| 其他 | 0 |

#### 扣分项（触发 → 题材总分 = 0）

行业指数 3 日涨幅 < -3%（冷门下跌板块）

### Scoring Detail - 风控 (5分, 硬否决，总分为 0 时其他维度不计分)

**数据源**:
- ST: 本地过滤（代码前缀 `300`/`688` 及名称含 ST/*ST/N/退）
- 退市预警: 本地维护名单（从公告/状态获取）
- 解禁减持: `stock_restricted_release_detail_em()`（东方财富，try/except 兜底）

| 条件 | 处理 |
|------|------|
| 非 ST | +2, 否则 总分=0 |
| 无退市预警 | +2, 否则 总分=0 |
| 当日无解禁/减持公告 | +1, 否则 总分=0 |
| 解禁 API 异常 | +1（无法确认时默认通过，不退市股票风险可控） |

### Data Caching Strategy

```python
class AkshareCache:
    """LRU 缓存，同次运行内避免重复请求"""
    _cache: dict = {}
    _ttl: int = 3600  # 1小时

    @classmethod
    def get(cls, key: str):
        return cls._cache.get(key)

    @classmethod
    def set(cls, key: str, value):
        cls._cache[key] = value

    @classmethod
    def clear(cls):
        cls._cache.clear()
```

缓存 key 设计:
- `fund_flow_rank:{period}` — 全市场资金流排名
- `lhb:{date}` — 当日龙虎榜
- `industry_flow:{period}` — 行业资金排名
- `concept_flow:{period}` — 概念资金排名
- `cyq:{code}` — 个股筹码分布

### Integration Points

#### `review_picker.py` 改动

```python
# 旧
rank = calc_score(rank)

# 新
from services.stock_scorer import StockScorer
result = StockScorer.score(row["code"], row.get("name", ""))
rank["total"] = result["total"]
rank["breakdown"] = result["breakdown"]
rank["level"] = result["level"]
```

#### `rule_engine.py` 改动

```python
# 旧
buy_candidates.sort(key=lambda x: x["buy_score"], reverse=True)
best = buy_candidates[0]

# 新
for c in buy_candidates:
    result = StockScorer.score(c["code"], c["name"])
    c["scorer_total"] = result["total"]
    c["scorer_level"] = result["level"]

qualified = [c for c in buy_candidates if c["scorer_total"] >= 60]
if not qualified:
    continue  # 不推送
qualified.sort(key=lambda x: x["scorer_total"], reverse=True)
best = qualified[0]
```

#### `backtest_engine.py` 改动

```python
# 旧
_, _, buy_score, _ = engine.run(ctx)
if buy_score > 0:
    buy_candidates.append((buy_score, code))

# 新
_, _, buy_score, _ = engine.run(ctx)
if buy_score > 0:
    result = StockScorer.score(code, "", date_str)
    if result["total"] >= 60:
        buy_candidates.append((result["total"], code))
```

### Testing Strategy

| Test | Scope | Method |
|------|-------|--------|
| 量价评分单元测试 | `price_volume.py` | mock kline data, verify each factor score |
| 资金流 mock 测试 | `fund_chip.py` | mock akshare return, verify scoring/warning/fallback |
| 板块 mock 测试 | `sector_theme.py` | mock akshare return, verify scoring |
| 风控测试 | `risk_check.py` | test ST/退市/减持 detection |
| 集成测试 | `stock_scorer.py` | full score() call with real klines |
| 异常测试 | all modules | simulate API timeout, empty response |
| 回测验证 | `backtest_engine.py` | compare old vs new scoring, measure win rate |

## Open Questions

- [ ] 东方财富 `stock_cyq_em()` 在当前网络环境是否可用？需部署后验证
- [ ] 新浪 `stock_lhb_detail_daily_sina()` 延迟（T+1 还是盘中更新）？
- [ ] `backtest.py` 回测历史周期时，akshare 数据是否回溯？需确认历史资金流数据可用性
- [ ] 全市场 5000+ 评分时，batch flow rank 是否能在 30 秒内返回？
- [ ] review_picker 和 rule_engine 共用同一份 akshare cache，是否跨进程？当前 cache 是进程级，不影响（picker 和 engine 分时运行）
