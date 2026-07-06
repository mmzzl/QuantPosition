# Feature Specification: 收盘分时复盘

**Feature Branch**: `006-close-review`
**Created**: 2026-07-04
**Status**: Draft
**Input**: User requirements: 收盘后分时复盘，完整分析流程，预判次日早盘该卖还是持有

## Summary

收盘后获取全天完整 5 分钟 K 线数据，结合日线位置，对持仓股票和当日早盘推荐的买入股票进行四维分时分析（均价关系、量价匹配、形态识别、尾盘信号），生成次日操作结论并通过钉钉推送。

## User Scenarios & Testing

### User Story 1 - 收盘分时复盘推送 (Priority: P1)

每个交易日 16:00 后，系统自动爬取全市场 A 股 5 分钟 K 线数据。16:15 自动分析用户持仓股票和当日早盘规则引擎买入推荐股票，生成分时复盘结论并通过钉钉推送。

**Why this priority**: 收盘复盘是每日必做功课，自动分析持仓和推荐的股票，节省大量时间，直接指导次日操作。

**Independent Test**: 收盘后查看钉钉，收到分时复盘推送消息，包含股票名称、日线定位、均价分析、量能分析、形态识别和次日操作结论。

**Acceptance Scenarios**:

1. **Given** 交易日 16:00 后，**When** 系统执行分时复盘，**Then** 钉钉收到持仓和推荐股票的分时复盘消息
2. **Given** 用户收到复盘推送，**Then** 消息包含完整的四维分析结果
3. **Given** 分析完成出货信号，**Then** 结论为"次日早盘逢高卖出"
4. **Given** 分析完成洗盘/吸筹信号，**Then** 结论为"次日持有等待拉升"
5. **Given** 当日无持仓且无推荐股票，**Then** 不推送消息

### Edge Cases

- 当日非交易日（周六/周日/节假日），不执行爬虫和分析
- 股票当天停牌，无 5 分钟 K 线数据，跳过分析并标注
- 5 分钟 K 线数据不足 48 根（数据未完整），标注数据不完整
- 钉钉推送失败时记录日志，不重试
- 爬虫失败时标记爬取状态，分析任务跳过对应日期

## Requirements

### Functional Requirements

- **FR-001**: 系统 MUST 在交易日 16:00 爬取全市场 A 股 5 分钟 K 线数据
- **FR-002**: 5 分钟 K 线数据 MUST 存储在独立集合 `stock_kline_5m` 中，与日线数据分离
- **FR-003**: 每条 5 分钟 K 线记录 MUST 包含：股票代码、时间、开/收/高/低价、成交量、成交额
- **FR-004**: 系统 MUST 在交易日 16:15 读取 `holdings` 集合获取用户持仓股票列表
- **FR-005**: 系统 MUST 在交易日 16:15 读取当日 `alert_log` 中 `trigger_type="buy"` 的记录作为推荐股票
- **FR-006**: 系统 MUST 对每只目标股票执行四维分时分析：日线定位、均价分析、量能分析、形态识别
- **FR-007**: 日线定位 MUST 区分三种位置：高位出货区（涨幅>40%）、上涨中段（10%-30%）、低位启动区
- **FR-008**: 均价分析 MUST 计算当日 VWAP 并判断股价相对于均价线的位置关系
- **FR-009**: 量能分析 MUST 分割早盘(9:30-10:00)、午盘(10:00-14:00)、尾盘(14:30-15:00)三段判断量价关系
- **FR-010**: 形态识别 MUST 匹配 M 头、U 型、单边上行、高开低走阴跌、尾盘抢筹等分时形态
- **FR-011**: 系统 MUST 综合所有维度生成结论：卖出 / 持有 / 观望
- **FR-012**: 分析结果 MUST 通过钉钉推送，包含股票名称、各维度分析结论和次日操作策略
- **FR-013**: 系统 MUST 在 `inputs.conf` 中配置定时任务，使用现有 APScheduler 调度

### Key Entities

- **5 分钟 K 线数据**: 每 5 分钟一根的 OHLCV 数据，存储在 `stock_kline_5m` 集合
- **分时复盘结论**: 分析引擎输出的结构化分析结果，包含位置、均价、量能、形态、尾盘信号和最终结论
- **持仓股票**: 用户持有的股票，来自 `holdings` 集合
- **推荐股票**: 当日早盘规则引擎产生的买入推荐，来自 `alert_log` 集合

## Success Criteria

### Measurable Outcomes

- **SC-001**: 全市场 5000+ 只股票的 5 分钟 K 线数据在 15 分钟内爬取完成
- **SC-002**: 每只目标股票的分析时间 < 1 秒
- **SC-003**: 钉钉推送在 16:20 前完成
- **SC-004**: 分析引擎对出货信号的识别准确率 > 80%
- **SC-005**: 分析引擎对洗盘信号的误判率 < 20%

## Assumptions

- 腾讯 `mkline` API 稳定可用，提供 5 分钟 K 线数据
- 全市场 A 股可通过 `sector_stocks` 或 `all_stock.csv` 获取
- 钉钉 webhook 已配置
- 持仓股票和推荐股票的总数通常在 20-50 只以内
- A 股交易时间 9:30-15:00，5分钟 K 线共 48 根

## Design

### Architecture

```
inputs.conf (cron)
  │
  ├── 16:00 → bin/review_spider.py
  │              │
  │              ├── 读取全市场股票代码
  │              ├── 爬取 Tencent 5-min K-line API
  │              └── 写入 MongoDB stock_kline_5m
  │
  └── 16:15 → bin/review_runner.py
                 │
                 ├── 查询 holdings + alert_log
                 ├── 读取 stock_kline_5m 数据
                 ├── 调用 services/review_service.py 分析
                 └── send_dingtalk_message() 推送
```

### Data Model - 5-Minute K-Line

**Collection**: `stock_kline_5m`

```json
{
  "code": "600000",
  "name": "浦发银行",
  "date": "2026-07-04 09:35",
  "open": 10.00,
  "close": 10.05,
  "high": 10.08,
  "low": 9.98,
  "volume": 10000,
  "amount": 100500.0,
  "crawl_time": "2026-07-04T16:00:01"
}
```

**Indexes**:
- `(code, date)` — 唯一索引，upsert 去重
- `(code, crawl_time)` — 按股票查询最新数据

### Crawler - `bin/review_spider.py`

- 复用 `kline_spider.py` 的模式和 Tencent API 调用
- API: `https://web.ifzq.gtimg.cn/appstock/app/kline/mkline?param={market}{code},m5,,100`
- 使用 `ThreadPoolExecutor(workers=10)` 并行爬取
- 只保留当天的 5 分钟 K 线（以当前日期过滤）
- Bulk write 到 `stock_kline_5m`，去重键 `(code, date)`
- 每次爬取先清空当天旧数据再写入（避免重复）
- 记录爬取日志：成功数量、失败数量

### Analysis Engine - `services/review_service.py`

**Position Analysis** (`_determine_position`):
```
输入: 60 天日线 K 线
输出: "高位" | "中段" | "低位"

高位条件: 阶段涨幅 > 40% 或 换手率 > 15% 或 高位放量长上影
中段条件: 涨幅 10%-30% 且 均线多头 且 无巨量阴线
低位条件: 底部突破 或 首板/二板 或 长期横盘后放量
```

**VWAP Analysis** (`_analyze_vwap`):
```
VWAP = Σ((high+low+close)/3 * volume) / Σ(volume)

强势: 股价 > VWAP 占比 > 70% 且 均价向上倾斜
弱势: 股价 < VWAP 占比 > 70% 且 均价向下倾斜
震荡: 两者都不满足
```

**Volume Analysis** (`_analyze_volume`):
```
三段分割: 09:35-10:00 (早盘) / 10:05-14:00 (午盘) / 14:05-15:00 (尾盘)

出货信号: 早盘放量急拉+二次缩量 或 上涨缩量下跌放量 或 尾盘放量跳水
洗盘信号: 下跌缩量反弹放量 或 早盘缩量下杀+放量收回 或 尾盘放量拉升
试盘信号: 盘中突然拉直线+不持续+快速回落+无出货量能
```

**Pattern Recognition** (`_recognize_pattern`):
```
出货类: M头 | 高开低走阴跌 | 早盘脉冲全天回落
洗盘类: U型洗盘 | 单边震荡上行 | 尾盘抢筹
```

**Conclusion** (`_generate_conclusion`):
```
卖出条件(任意2条): 高位 + 均价弱势 + 量价背离 + M头 + 尾盘跳水
持有条件(全部满足): 低位/中段 + 均价强势 + 量价配合 + U型/上行 + 尾盘抢筹
观望: 震荡平衡形态 + 无明显信号
```

### Scheduler Configuration - `config/inputs.conf`

```ini
[script://bin/review_spider.py]
enable = true
cron=hour=16,minute=0,day_of_week=0-4

[script://bin/review_runner.py]
enable = true
cron=hour=16,minute=15,day_of_week=0-4
```

### DingTalk Message Format

```markdown
📊 收盘分时复盘 600000 浦发银行
━━━━━━━━━━━━━━━━━━━
📌 日线定位：上涨中段
趋势完好，主力动作：洗盘震仓

📈 均价分析：强势 ✅
全天站均价上方，均价向上倾斜

📊 量能分析：洗盘信号
下跌缩量，上涨放量，资金承接积极

🔍 分时形态：U型洗盘分时
早盘缩量下杀后放量收回

🌙 尾盘信号：抢筹 ✅
尾盘持续大单买入

━━━━━━━━━━━━━━━━━━━
🎯 结论：次日持有等待拉升
策略：不破均价则持有，冲高放量滞涨再卖
```

### Files to Create

| File | Type | Description |
|------|------|-------------|
| `bin/review_spider.py` | 爬虫 | 全市场 5 分钟 K 线爬虫 |
| `services/review_service.py` | 服务 | 分时复盘分析引擎 |
| `bin/review_runner.py` | 脚本 | 分析编排+钉钉推送 |

### Files to Modify

| File | Description |
|------|-------------|
| `config/inputs.conf` | 新增两条定时任务 |
