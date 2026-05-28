# 规则探索系统设计文档

## 概述

自动探索交易规则的系统：通过模板网格搜索、LLM 优化、遗传算法三种方式大量生成候选规则，写入 MongoDB 存储，用户按需验证（回测评分），最终一键更新最优规则到生产环境。

## 核心原则

- **生成与验证分离**：生成是廉价的（拼字符串），验证是昂贵的（跑回测）
- **尽量多生成**：候选规则写入 MongoDB 存着，验证是后面的事
- **断点续跑**：进度持久化，中断后可从上次位置继续
- **黑名单过滤**：已验证且质量太差的规则记入黑名单，后续生成跳过

## 架构

```
前端 "规则探索" 按钮
    │
    ▼
POST /rules/explore  ──→  Celery Task: rule_exploration
    │                         │
    │                         ├─ Phase 1: 模板网格搜索（~3000-5000 条）
    │                         ├─ Phase 2: LLM 批量优化（~500-1000 条）
    │                         └─ Phase 3: 遗传算法进化（~4000+ 条）
    │                              │
    │                              ▼
    │                         全部写入 rule_candidates
    │                         进度写入 rule_explore_progress
    │                         烂规则写入 rule_blacklist
    │
前端 "验证规则" 按钮
    │
    ▼
POST /rules/validate-candidates  ──→  Celery Task: rule_validation
    │                                      │
    │                                      ▼
    │                                 读取 rule_candidates（未验证的）
    │                                 抽样 500 只股票回测
    │                                 组合评分（买入+卖出+风控 一起）
    │                                 更新评分 / 入黑名单
    │
前端 "一键更新规则" 按钮
    │
    ▼
POST /rules/apply-candidates  ──→  最优候选替换 trading_rules
```

## MongoDB 集合设计

### `rule_candidates` — 候选规则池

```json
{
  "_id": "auto",
  "source": "template | llm | genetic",
  "generation": 0,
  "type": "buy | sell | risk",
  "name": "模板生成_买入_001",
  "condition": "price > ma5 * 1.5 and vol > ma5_vol * 2",
  "condition_normalized": "price>ma5*1.5andvol>ma5_vol*2",
  "priority": 3,
  "weight": 0.35,
  "sharpe": null,
  "win_rate": null,
  "avg_return": null,
  "total_return": null,
  "trades": null,
  "composite_score": null,
  "validated": false,
  "created_at": "2026-05-26T10:00:00"
}
```

索引：`{validated: 1}`, `{source: 1}`, `{composite_score: -1}`, `{condition_normalized: 1}`

### `rule_explore_progress` — 探索进度（单条记录）

```json
{
  "_id": "current",
  "status": "running | paused | done | error",
  "phase": "template | llm | genetic | done",
  "phase_label": "LLM批量优化",
  "template_done": 3200,
  "template_total": 3200,
  "llm_done": 80,
  "llm_total": 200,
  "genetic_done": 0,
  "genetic_total": 4000,
  "candidates_count": 3280,
  "blacklist_count": 156,
  "best_sharpe": 1.85,
  "best_score": 72.5,
  "error_msg": "",
  "task_id": "celery-task-uuid",
  "updated_at": "2026-05-26T10:30:00"
}
```

### `rule_blacklist` — 规则黑名单

```json
{
  "_id": "auto",
  "condition": "price < ma5 * 0.8 and vol < ma5_vol * 0.5",
  "condition_normalized": "price<ma5*0.8 and vol<ma5_vol*0.5",
  "type": "buy",
  "sharpe": -1.2,
  "reason": "validated_poor",
  "created_at": "2026-05-26T10:00:00"
}
```

索引：`{condition_normalized: 1}`（用于快速查重）

### `rule_backup` — 规则备份（一键更新前自动备份）

```json
{
  "_id": "auto",
  "backup_at": "2026-05-26T10:00:00",
  "source": "apply_candidates",
  "rules": [
    {"rule_id": 1, "name": "...", "type": "buy", "condition": "...", ...},
    {"rule_id": 2, "name": "...", "type": "sell", "condition": "...", ...}
  ]
}
```

保留最近 10 次备份，超出的自动删除。

### `system_settings` — 新增 LLM 配置字段

```json
{
  "llm_api_url": "https://api.openai.com/v1",
  "llm_api_key": "sk-xxx",
  "llm_model": "gpt-4o-mini",
  "llm_batch_size": 15
}
```

## 模板设计

### 变量池

```python
VARIABLES = [
    "price", "vol", "ma5", "ma10", "ma5_vol",
    "last_close", "high", "low", "open",
    "has_pos", "cost", "buy_date", "today"
]
```

### 变量白名单校验

LLM 或遗传算法生成的规则可能包含非法变量，写入前必须校验：

```python
import ast

ALLOWED_VARS = set(VARIABLES) | {"and", "or", "not", "True", "False", "abs"}

def validate_variables(condition_str):
    """校验条件中只使用了允许的变量"""
    tree = ast.parse(condition_str, mode="eval")
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in ALLOWED_VARS:
            return False, f"非法变量: {node.id}"
        if isinstance(node, ast.Attribute):
            return False, f"不允许属性访问: .{node.attr}"
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return False, "不允许 import"
    return True, ""
```

### 条件规范化与去重

生成的规则写入前需规范化，避免重复：

```python
import re

def normalize_condition(condition_str):
    """规范化条件字符串：去空格、统一运算符"""
    s = condition_str.strip()
    s = re.sub(r'\s+', '', s)           # 去所有空格
    s = re.sub(r'>=', '≥', s)           # 统一运算符
    s = re.sub(r'<=', '≤', s)
    s = re.sub(r'!=', '≠', s)
    s = re.sub(r'\*1\.0(?!\d)', '', s)  # *1.0 简化
    return s.lower()                     # 统一小写
```

**写入流程**：
1. 生成条件字符串
2. `validate_variables()` 校验变量合法性
3. `ast.parse(condition, mode="eval")` 校验语法
4. `normalize_condition()` 规范化
5. 查 `rule_blacklist` 的 `condition_normalized`，命中则跳过
6. 查 `rule_candidates` 的 `condition_normalized`，已存在则跳过
7. 全部通过 → 写入 `rule_candidates`

### 运算符

```python
OPERATORS = [">", "<", ">=", "<="]
```

### 系数池

```python
COEFFICIENTS = [0.8, 0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15, 1.2, 1.3, 1.5, 1.8, 2.0]
```

### 模板结构

```python
# 单条件模板
SINGLE_TEMPLATES = [
    "{left} {op} {right}",
    "{left} {op} {right} * {coeff}",
]

# 双条件模板（and/or 连接）
DOUBLE_TEMPLATES = [
    "{left1} {op1} {right1} * {coeff1} and {left2} {op2} {right2} * {coeff2}",
    "{left1} {op1} {right1} or {left2} {op2} {right2} * {coeff2}",
]

# 三条件模板
TRIPLE_TEMPLATES = [
    "{left1} {op1} {right1} * {coeff1} and {left2} {op2} {right2} * {coeff2} and {left3} {op3} {right3} * {coeff3}",
]
```

### 变量对组合（有意义的配对）

```python
# 价格类比较
PRICE_PAIRS = [
    ("price", "ma5"), ("price", "ma10"), ("price", "last_close"),
    ("price", "high"), ("price", "low"), ("price", "open"),
    ("ma5", "ma10"), ("price", "cost"),
]

# 成交量类比较
VOL_PAIRS = [
    ("vol", "ma5_vol"),
]

# 持仓天数类
HOLD_PAIRS = [
    ("today", "buy_date"),
]
```

### 生成规模估算

```
价格对: 8 对 × 4 运算符 × 13 系数 = 416 单条件
量对:   1 对 × 4 运算符 × 13 系数 = 52 单条件
持仓:   1 对 × 4 运算符 × 13 系数 = 52 单条件

单条件买入: 520 条
单条件卖出: 520 条
单条件风控: 520 条

双条件组合: 520 × 520 × 2(and/or) ≈ 太多，需要截取 top 组合
→ 实际生成 3000-5000 条
```

## LLM 批量生成

### Prompt 模板

```
你是一个股票交易规则专家。以下是当前系统中的变量和运算符：

变量：price(最新价), vol(成交量), ma5(5日均线), ma10(10日均线),
      ma5_vol(5日均量), last_close(昨收), high(20日最高), low(20日最低),
      open(开盘价), has_pos(是否持仓), cost(持仓成本),
      buy_date(买入日期), today(今天)

运算符：>, <, >=, <=, and, or, not
函数：abs()

请基于以下 {n} 条规则，生成 {batch_size} 条变异版本。
要求：
1. 语法正确，可被 Python eval() 执行
2. 只使用上述变量，不使用其他变量
3. 不使用属性访问（如 .xxx）
4. 条件必须返回 True/False
5. 尽量多样化，覆盖不同策略思路

输入规则：
{rules}

请返回 JSON 数组，每个元素包含：
- condition: 条件表达式
- type: buy/sell/risk
- name: 规则名称（简短描述）
- priority: 1-3
- weight: 0.0-1.0
```

### LLM 调用策略

- 每次发送 10-20 条参考规则
- LLM 返回 15-20 条新规则
- 调用 50-100 次 = 750-2000 条新候选
- 失败重试 2 次，仍失败则跳过该批次
- 所有返回的规则先做语法检查（`ast.parse`），无效的丢弃

## 遗传算法

### 编码方式

规则条件字符串直接作为基因，不做二进制编码。

### 种群初始化

从 `rule_candidates` 中随机抽取 200 条作为初始种群。

### 选择机制

所有个体都写入 rule_candidates（不做淘汰），但**选择父代时**使用轮盘赌：

```python
def select_parent(population, scores):
    """轮盘赌选择：composite_score 越高被选中概率越大"""
    # 未验证的个体（score=None）给一个基础分
    adjusted = [s if s is not None else 10.0 for s in scores]
    total = sum(adjusted)
    if total == 0:
        return random.choice(population)
    pick = random.uniform(0, total)
    current = 0
    for i, score in enumerate(adjusted):
        current += score
        if current >= pick:
            return population[i]
    return population[-1]
```

### 交叉操作

```
父代A: "price > ma5 * 1.5 and vol > ma5_vol * 2"
父代B: "ma5 > ma10 * 1.1 and price > last_close * 1.05"

交叉点: 在 "and" 处切分

子代: "price > ma5 * 1.5 and price > last_close * 1.05"
```

### 变异操作

```
原始: "price > ma5 * 1.5 and vol > ma5_vol * 2"

变异1（替换系数）: "price > ma5 * 1.2 and vol > ma5_vol * 2"
变异2（替换变量）: "price > ma10 * 1.5 and vol > ma5_vol * 2"
变异3（替换运算符）: "price >= ma5 * 1.5 and vol > ma5_vol * 2"
变异4（添加条件）: "price > ma5 * 1.5 and vol > ma5_vol * 2 and ma5 > ma10"
```

### 参数

```python
POPULATION_SIZE = 200
GENERATIONS = 20
CROSSOVER_RATE = 0.7
MUTATION_RATE = 0.3
ELITE_SIZE = 20  # 每代保留 top-20 精英
```

### 生成规模

每代 200 个个体 × 20 代 = 4000 条新候选（全部写入 rule_candidates）

## 验证阶段

### 回测股票抽样

从全市场股票中抽样 500 只，覆盖各行业：

```python
def sample_stocks(all_codes, name_map, n=500):
    # 1. 剔除 ST/*ST 股票
    # 2. 优先选择：有足够K线数据（>60天）的股票
    # 3. 按行业分层抽样，每个行业至少取 2 只
    # 4. 最终选取 n 只
    pass  # 实现时复用 backtest_engine.py 中的 _load_klines 逻辑
```

### 组合回测

规则引擎的执行逻辑是：风控优先级最高 → 卖出 → 买入。所以验证时必须以"规则集"为单位回测。

**注意**：`backtest_with_rules()` 复用 `backtest_engine.py` 的 `run_backtest()` 函数，传入候选规则集合作为参数。

```
一组规则集 = [风控规则...] + [卖出规则...] + [买入规则...]

回测流程：
1. 从 rule_candidates 中选取待验证的规则
2. 按 type 分组，每组取 composite_score 最高的 top-N
3. 组装成规则集进行回测
4. 每个规则集包含：1条风控 + 1条卖出 + 1条买入
5. 用 backtest_engine 对 500 只股票跑回测
6. 计算综合评分，更新到各条候选规则上

注意：一条候选规则可能参与多个规则集的回测，
其评分取所有包含它的规则集中的最高分。
```

### 综合评分

```python
def composite_score(sharpe, total_return, win_rate, trades, backtest_days=180):
    """
    综合评分 = 夏普 * 40 + 年化收益归一化 * 40 + 胜率 * 20

    各指标归一化到 0-100 范围：
    - 夏普：0→0, 2→100（超过2按100算）
    - 年化收益：-50%→0, 100%→100（按回测天数年化）
    - 胜率：0%→0, 100%→100

    交易次数惩罚：
    - <10：不可信，直接 -999
    - >500：可能过拟合，打 0.8 折
    """
    if trades < 10:
        return -999

    # 年化收益：不同回测周期（90/180/365天）的收益统一到年
    annualized_return = total_return / backtest_days * 365

    # 归一化
    sharpe_norm = min(max(sharpe, 0), 2) / 2 * 100              # 0~2 → 0~100
    return_norm = min(max(annualized_return, -50), 100)          # -50~100 → 0~100
    win_norm = min(max(win_rate, 0), 100)                        # 0~100 → 0~100

    score = sharpe_norm * 0.4 + return_norm * 0.4 + win_norm * 0.2

    if trades > 500:
        score *= 0.8

    return round(score, 2)
```

### 黑名单入列条件

```python
def should_blacklist(sharpe, total_return, win_rate, trades):
    if trades == 0:
        return True, "无交易"
    if sharpe < -0.5:
        return True, "夏普过低"
    if win_rate < 30 and sharpe < 0:
        return True, "胜率和夏普双低"
    return False, ""
```

## 一键更新逻辑

```python
def apply_candidates():
    # 1. 读取已验证的候选，按 composite_score 降序
    candidates = db.rule_candidates.find({"validated": True}).sort("composite_score", -1)

    # 2. 按 type 分组取 top-1
    best = {}
    for c in candidates:
        if c["type"] not in best:
            best[c["type"]] = c
        if len(best) == 3:
            break

    if len(best) < 3:
        return "候选规则不完整，需要至少1条买入+1条卖出+1条风控"

    # 3. 备份当前规则
    current_rules = list(db.trading_rules.find({}))
    if current_rules:
        db.rule_backup.insert_one({
            "backup_at": datetime.now(),
            "source": "apply_candidates",
            "rules": [{k: v for k, v in r.items() if k != "_id"} for r in current_rules]
        })
        # 保留最近 10 次备份
        backups = list(db.rule_backup.find().sort("backup_at", -1))
        if len(backups) > 10:
            for old in backups[10:]:
                db.rule_backup.delete_one({"_id": old["_id"]})

    # 4. 计算当前规则的综合评分（如果有的话）
    if current_rules:
        current_score = backtest_with_rules(current_rules)
    else:
        current_score = -999  # 没有当前规则，直接用候选

    # 5. 计算候选规则的综合评分
    candidate_score = backtest_with_rules([best["buy"], best["sell"], best["risk"]])

    # 6. 比较
    if candidate_score > current_score:
        # 替换
        db.trading_rules.delete_many({})
        for rule_type, rule in best.items():
            rule.pop("_id", None)
            rule["rule_id"] = next_id()
            rule["enabled"] = True
            db.trading_rules.insert_one(rule)
        return f"已更新：候选评分 {candidate_score} > 当前评分 {current_score}"
    else:
        return f"未更新：候选评分 {candidate_score} <= 当前评分 {current_score}"
```

## 前端页面

### TradingRules.vue — 新增按钮

在现有页面顶部新增：
- `规则探索` 按钮 → 触发生成阶段
- `验证规则` 按钮 → 触发验证阶段
- `候选规则` 链接 → 跳转到候选规则页面

### 候选规则页面（RuleCandidates.vue）

```
┌─────────────────────────────────────────────────────────────┐
│ 候选规则池                                                  │
│                                                             │
│ 状态栏：已验证 320 / 8450 | 黑名单 156 条 | 当前最优夏普 2.1│
│                                                             │
│ [验证全部] [验证前500条] [一键更新规则] [查看黑名单] [清空]  │
│                                                             │
│ 筛选：[全部▾] [已验证▾] [来源▾] [类型▾]                    │
│                                                             │
│ ┌──────┬──────┬──────────────────────────┬──────┬──────┬───┐│
│ │ 来源 │ 类型 │ 条件                     │ 综合 │ 夏普 │操作││
│ ├──────┼──────┼──────────────────────────┼──────┼──────┼───┤│
│ │ 模板 │ 买入 │ price > ma5 * 1.5        │ 85.2 │ 2.1  │删除││
│ │ LLM  │ 卖出 │ price < ma10 * 0.9       │ 72.1 │ 1.8  │删除││
│ │ 遗传 │ 风控 │ cost > price * 1.1       │ -    │ -    │删除││
│ └──────┴──────┴──────────────────────────┴──────┴──────┴───┘│
│                                                             │
│ [分页]                                                      │
└─────────────────────────────────────────────────────────────┘
```

### Settings.vue — LLM 配置

新增分区：

```
─── LLM 配置（规则探索用）───
API 地址：    [https://api.openai.com/v1]
API Key：     [sk-xxx...]
模型名称：    [gpt-4o-mini]
每次生成条数：[15]  (10-20)
```

## API 端点

### `POST /rules/explore` — 启动规则探索

```json
// 请求：无参数（从 MongoDB 读取当前规则和 LLM 配置）
// 响应：
{"task_id": "celery-task-uuid", "message": "探索任务已启动"}

// 错误：
{"detail": "已有探索任务在运行中，请等待完成"}
{"detail": "请先在系统设置中配置 LLM"}
```

### `GET /rules/explore/status` — 查询探索状态

```json
// 响应：
{
  "status": "running",
  "phase": "llm",
  "phase_label": "LLM批量优化",
  "template_done": 3200,
  "template_total": 3200,
  "llm_done": 80,
  "llm_total": 200,
  "genetic_done": 0,
  "genetic_total": 4000,
  "candidates_count": 3280,
  "blacklist_count": 156,
  "best_score": 85.2
}
```

### `POST /rules/validate-candidates` — 启动验证

```json
// 请求：
{"scope": "all | template | llm | genetic", "limit": 500}
// 响应：
{"task_id": "celery-task-uuid", "message": "验证任务已启动"}
```

### `POST /rules/apply-candidates` — 一键更新

```json
// 响应：
{"message": "已更新：候选评分 85.2 > 当前评分 72.1"}
{"message": "未更新：候选评分 65.0 <= 当前评分 72.1"}
```

### `GET /rules/candidates` — 获取候选列表

```json
// 查询参数：?page=1&page_size=50&validated=true&source=template&type=buy
// 响应：
{
  "candidates": [...],
  "total": 8450,
  "page": 1,
  "page_size": 50
}
```

### `DELETE /rules/candidates/{id}` — 删除单条候选

### `DELETE /rules/candidates` — 清空候选

```json
// 请求：
{"scope": "all | validated | unvalidated"}
```

### `GET /rules/blacklist` — 获取黑名单

```json
// 查询参数：?page=1&page_size=50
// 响应：
{
  "blacklist": [...],
  "total": 156
}
```

### `DELETE /rules/blacklist/{id}` — 从黑名单移除

### `GET /rules/backup` — 获取规则备份列表

```json
// 响应：
{
  "backups": [
    {"_id": "...", "backup_at": "2026-05-26T10:00:00", "rules_count": 5},
    ...
  ]
}
```

### `POST /rules/backup/{id}/restore` — 从备份恢复规则

```json
// 响应：
{"message": "已恢复 5 条规则", "rules": [...]}
```

## 异常处理

| 阶段 | 异常 | 处理 |
|------|------|------|
| 模板搜索 | 规则语法错误 | 跳过，记录日志 |
| LLM 调用 | API Key 未配置 | 终止任务，返回错误 |
| LLM 调用 | API 调用失败 | 重试 2 次，跳过该批次 |
| LLM 调用 | 返回无效规则 | 语法检查失败的丢弃 |
| LLM 调用 | 余额不足 | 终止任务，返回错误 |
| 遗传算法 | 种群退化 | 提前终止，用当前最优 |
| 验证回测 | 数据不足 | 跳过该股票 |
| 验证回测 | 无交易 | 评分 -999 |
| MongoDB | 写入失败 | 重试 3 次 |
| 并发 | 重复触发 | 拒绝，提示任务进行中 |

## 资源保护

- **断点续跑**：进度写入 MongoDB，中断后重启从上次位置继续
- **并发控制**：同一时间只允许一个探索任务运行
- **LLM 调用上限**：100 次/次探索
- **候选上限**：无硬限制（MongoDB 存储）
- **黑名单自动清理**：超过 30 天的黑名单记录自动清除（可选）

## 边界情况处理

| 情况 | 处理方式 |
|------|---------|
| `trading_rules` 为空（用户没配规则） | 一键更新时直接用候选最优规则，跳过比较 |
| 用户有手动写的自定义规则 | 一键更新前备份当前规则到 `rule_backup` 集合 |
| 候选规则中有重复条件 | 写入前用 `condition_normalized` 去重，保留分数更高的 |
| 验证任务中断 | 进度持久化到 `rule_explore_progress`，重启后从未验证的继续 |
| LLM 返回的规则包含非法变量 | `validate_variables()` 校验，无效的丢弃 |
| 遗传算法交叉后产生无效语法 | `ast.parse()` 校验，无效的丢弃，重新交叉 |
| 一键更新时候选评分 = 当前评分 | 视为"未更优"，不替换 |
| 黑名单中被误标记的规则 | 前端黑名单页面支持手动移除 |

## 新增文件清单

| 文件 | 作用 |
|------|------|
| `apps/api/services/rule_explorer.py` | 探索引擎核心：模板生成、LLM 调用、遗传算法、评分、去重、黑名单过滤 |
| `apps/api/tasks/rule_explore_tasks.py` | Celery 任务定义（探索 + 验证） |
| `apps/api/routers/rules.py` | 新增 9 个端点（explore/validate/apply/candidates/blacklist/backup） |
| `apps/api/routers/settings.py` | 新增 LLM 配置字段 |
| `apps/web/src/views/admin/Settings.vue` | 新增 LLM 配置区域 |
| `apps/web/src/views/TradingRules.vue` | 新增按钮 |
| `apps/web/src/views/RuleCandidates.vue` | 候选规则页面（新增） |
| `apps/web/src/api/rules.js` | 新增 API 调用 |
