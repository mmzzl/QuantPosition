# 规则探索系统实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建自动规则探索系统，通过模板搜索、LLM优化、遗传算法生成大量候选规则，用户按需验证后一键更新最优规则。

**Architecture:** 生成与验证分离。生成阶段（模板→LLM→遗传算法）将候选规则写入MongoDB `rule_candidates`集合。验证阶段抽样500只股票做组合回测评分。一键更新时备份当前规则后替换为最优候选。

**Tech Stack:** Python 3.12 + FastAPI + MongoDB (pymongo) + Celery + Vue 3 + Element Plus + requests (LLM调用)

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `apps/api/services/rule_explorer.py` | 探索引擎核心：常量定义、校验函数、模板生成、LLM调用、遗传算法、评分、黑名单 |
| `apps/api/tasks/rule_explore_tasks.py` | Celery异步任务：探索任务、验证任务 |
| `apps/api/routers/rules.py` | 新增9个API端点 |
| `apps/api/routers/settings.py` | 新增LLM配置字段 |
| `apps/web/src/api/rules.js` | 新增前端API调用 |
| `apps/web/src/views/admin/Settings.vue` | 新增LLM配置区域 |
| `apps/web/src/views/TradingRules.vue` | 新增3个按钮 |
| `apps/web/src/views/RuleCandidates.vue` | 候选规则页面（新建） |

---

## Task 1: MongoDB 集合初始化

**Files:**
- Modify: `apps/api/database.py` (添加索引创建)

- [ ] **Step 1: 在 database.py 中添加集合索引初始化**

在 `database.py` 的 `get_db()` 函数或启动时添加索引：

```python
def ensure_indexes():
    db = get_db()
    # rule_candidates 索引
    db.rule_candidates.create_index("validated")
    db.rule_candidates.create_index("source")
    db.rule_candidates.create_index("composite_score")
    db.rule_candidates.create_index("condition_normalized")
    # rule_blacklist 索引
    db.rule_blacklist.create_index("condition_normalized")
    # rule_backup 无需额外索引，按 backup_at 排序即可
```

- [ ] **Step 2: 在 main.py 启动时调用 ensure_indexes()**

```python
from database import ensure_indexes

@app.on_event("startup")
async def startup():
    ensure_indexes()
```

- [ ] **Step 3: 验证索引创建成功**

运行应用，检查 MongoDB 中 `rule_candidates`、`rule_blacklist` 集合的索引。

---

## Task 2: 后端 - rule_explorer.py 基础函数

**Files:**
- Create: `apps/api/services/rule_explorer.py`

- [ ] **Step 1: 创建文件，定义常量和基础函数**

```python
import ast
import re
import random
import logging
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from database import get_db

# 变量池
VARIABLES = [
    "price", "vol", "ma5", "ma10", "ma5_vol",
    "last_close", "high", "low", "open",
    "has_pos", "cost", "buy_date", "today"
]

ALLOWED_VARS = set(VARIABLES) | {"and", "or", "not", "True", "False", "abs"}

# 运算符
OPERATORS = [">", "<", ">=", "<="]

# 系数池
COEFFICIENTS = [0.8, 0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15, 1.2, 1.3, 1.5, 1.8, 2.0]

# 变量对
PRICE_PAIRS = [
    ("price", "ma5"), ("price", "ma10"), ("price", "last_close"),
    ("price", "high"), ("price", "low"), ("price", "open"),
    ("ma5", "ma10"), ("price", "cost"),
]
VOL_PAIRS = [("vol", "ma5_vol")]
HOLD_PAIRS = [("today", "buy_date")]

ALL_PAIRS = PRICE_PAIRS + VOL_PAIRS + HOLD_PAIRS


def validate_variables(condition_str: str) -> Tuple[bool, str]:
    """校验条件中只使用了允许的变量"""
    try:
        tree = ast.parse(condition_str, mode="eval")
    except SyntaxError as e:
        return False, f"语法错误: {e.msg}"
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in ALLOWED_VARS:
            return False, f"非法变量: {node.id}"
        if isinstance(node, ast.Attribute):
            return False, f"不允许属性访问: .{node.attr}"
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return False, "不允许 import"
    return True, ""


def normalize_condition(condition_str: str) -> str:
    """规范化条件字符串：去空格、统一运算符"""
    s = condition_str.strip()
    s = re.sub(r'\s+', '', s)
    s = re.sub(r'>=', '≥', s)
    s = re.sub(r'<=', '≤', s)
    s = re.sub(r'!=', '≠', s)
    s = re.sub(r'\*1\.0(?!\d)', '', s)
    return s.lower()


def is_blacklisted(condition_normalized: str) -> bool:
    """检查条件是否在黑名单中"""
    db = get_db()
    return db.rule_blacklist.find_one({"condition_normalized": condition_normalized}) is not None


def is_duplicate(condition_normalized: str) -> bool:
    """检查条件是否已在候选池中"""
    db = get_db()
    return db.rule_candidates.find_one({"condition_normalized": condition_normalized}) is not None


def try_insert_candidate(rule: dict) -> bool:
    """尝试插入候选规则，返回是否成功（通过校验和去重）"""
    condition = rule.get("condition", "")
    if not condition:
        return False

    ok, err = validate_variables(condition)
    if not ok:
        logging.debug(f"变量校验失败: {err}, condition={condition}")
        return False

    try:
        ast.parse(condition, mode="eval")
    except SyntaxError as e:
        logging.debug(f"语法校验失败: {e}, condition={condition}")
        return False

    normalized = normalize_condition(condition)
    if is_blacklisted(normalized):
        return False
    if is_duplicate(normalized):
        return False

    db = get_db()
    doc = {
        "source": rule.get("source", "unknown"),
        "generation": rule.get("generation", 0),
        "type": rule.get("type", "buy"),
        "name": rule.get("name", ""),
        "condition": condition,
        "condition_normalized": normalized,
        "priority": rule.get("priority", 3),
        "weight": rule.get("weight", 0.35),
        "sharpe": None,
        "win_rate": None,
        "avg_return": None,
        "total_return": None,
        "trades": None,
        "composite_score": None,
        "validated": False,
        "created_at": datetime.now(),
    }
    try:
        db.rule_candidates.insert_one(doc)
        return True
    except Exception as e:
        logging.error(f"写入候选规则失败: {e}")
        return False


def composite_score(sharpe: float, total_return: float, win_rate: float,
                    trades: int, backtest_days: int = 180) -> float:
    """综合评分：夏普40% + 年化收益40% + 胜率20%"""
    if trades < 10:
        return -999

    annualized_return = total_return / backtest_days * 365
    sharpe_norm = min(max(sharpe, 0), 2) / 2 * 100
    return_norm = min(max(annualized_return, -50), 100)
    win_norm = min(max(win_rate, 0), 100)

    score = sharpe_norm * 0.4 + return_norm * 0.4 + win_norm * 0.2
    if trades > 500:
        score *= 0.8
    return round(score, 2)


def should_blacklist(sharpe: float, total_return: float, win_rate: float,
                     trades: int) -> Tuple[bool, str]:
    """判断是否应该加入黑名单"""
    if trades == 0:
        return True, "无交易"
    if sharpe < -0.5:
        return True, "夏普过低"
    if win_rate < 30 and sharpe < 0:
        return True, "胜率和夏普双低"
    return False, ""


def update_progress(phase: str, phase_label: str, **kwargs):
    """更新探索进度到 MongoDB"""
    db = get_db()
    update = {
        "phase": phase,
        "phase_label": phase_label,
        "updated_at": datetime.now(),
    }
    update.update(kwargs)
    db.rule_explore_progress.update_one(
        {"_id": "current"},
        {"$set": update},
        upsert=True
    )
```

- [ ] **Step 2: 验证基础函数**

在Python交互环境中测试：
```python
from services.rule_explorer import validate_variables, normalize_condition
print(validate_variables("price > ma5 * 1.5"))  # (True, '')
print(validate_variables("price > xxx * 1.5"))  # (False, '非法变量: xxx')
print(normalize_condition("price > ma5 * 1.5"))  # "price>ma5*1.5"
```

---

## Task 3: 后端 - 模板搜索生成

**Files:**
- Modify: `apps/api/services/rule_explorer.py`

- [ ] **Step 1: 添加模板搜索函数**

```python
def generate_template_rules() -> int:
    """Phase 1: 模板网格搜索，生成候选规则写入 MongoDB，返回生成数量"""
    from itertools import product

    count = 0
    update_progress("template", "模板网格搜索", template_done=0, template_total=0)

    # 单条件模板
    single_conditions = []
    for left, right in ALL_PAIRS:
        for op in OPERATORS:
            for coeff in COEFFICIENTS:
                single_conditions.append(f"{left} {op} {right} * {coeff}")
            single_conditions.append(f"{left} {op} {right}")

    # 双条件模板（and 连接）
    double_conditions = []
    pairs_list = list(ALL_PAIRS)
    for i, (l1, r1) in enumerate(pairs_list):
        for j, (l2, r2) in enumerate(pairs_list):
            if i >= j:
                continue
            for op1 in OPERATORS:
                for op2 in OPERATORS:
                    for c1 in random.sample(COEFFICIENTS, min(3, len(COEFFICIENTS))):
                        for c2 in random.sample(COEFFICIENTS, min(3, len(COEFFICIENTS))):
                            double_conditions.append(
                                f"{l1} {op1} {r1} * {c1} and {l2} {op2} {r2} * {c2}"
                            )

    all_conditions = single_conditions + double_conditions
    random.shuffle(all_conditions)

    total = len(all_conditions)
    update_progress("template", "模板网格搜索", template_total=total)

    types = ["buy", "sell", "risk"]
    for i, cond in enumerate(all_conditions):
        for rule_type in types:
            rule = {
                "source": "template",
                "type": rule_type,
                "name": f"模板_{rule_type}_{i:04d}",
                "condition": cond,
                "priority": {"risk": 1, "sell": 2, "buy": 3}[rule_type],
                "weight": 0.35,
            }
            if try_insert_candidate(rule):
                count += 1

        if (i + 1) % 100 == 0:
            update_progress("template", "模板网格搜索", template_done=i + 1)

    update_progress("template", "模板网格搜索",
                    template_done=total, candidates_count=count)
    logging.info(f"[EXPLORE] 模板搜索完成，生成 {count} 条候选")
    return count
```

- [ ] **Step 2: 测试模板生成**

```python
from services.rule_explorer import generate_template_rules
# 注意：需要 MongoDB 连接
count = generate_template_rules()
print(f"生成 {count} 条")
```

---

## Task 4: 后端 - LLM 批量生成

**Files:**
- Modify: `apps/api/services/rule_explorer.py`

- [ ] **Step 1: 添加 LLM 调用函数**

```python
LLM_SYSTEM_PROMPT = """你是一个股票交易规则专家。以下是系统中的变量和运算符：

变量：price(最新价), vol(成交量), ma5(5日均线), ma10(10日均线),
      ma5_vol(5日均量), last_close(昨收), high(20日最高), low(20日最低),
      open(开盘价), has_pos(是否持仓), cost(持仓成本),
      buy_date(买入日期), today(今天)

运算符：>, <, >=, <=, and, or, not
函数：abs()

要求：
1. 语法正确，可被 Python eval() 执行
2. 只使用上述变量，不使用其他变量
3. 不使用属性访问（如 .xxx）
4. 条件必须返回 True/False
5. 尽量多样化，覆盖不同策略思路（趋势、均值回归、量价配合等）
"""


def call_llm_batch(rules: List[dict], batch_size: int, settings: dict) -> List[dict]:
    """调用 LLM 生成一批规则"""
    api_url = settings.get("llm_api_url", "").rstrip("/")
    api_key = settings.get("llm_api_key", "")
    model = settings.get("llm_model", "gpt-4o-mini")

    if not api_url or not api_key:
        raise ValueError("LLM 未配置")

    rules_text = "\n".join([
        f"- [{r['type']}] {r['condition']}" for r in rules[:20]
    ])

    user_msg = f"""请基于以下 {len(rules)} 条规则，生成 {batch_size} 条变异版本。

输入规则：
{rules_text}

请返回 JSON 数组，每个元素包含：
- condition: 条件表达式
- type: buy/sell/risk
- name: 规则名称（简短中文描述）
- priority: 1-3（1=风控最高, 2=卖出, 3=买入）
- weight: 0.0-1.0

只返回 JSON 数组，不要其他文字。"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": LLM_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.9,
        "max_tokens": 4000,
    }

    for attempt in range(3):
        try:
            resp = requests.post(f"{api_url}/chat/completions",
                                 json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            # 提取 JSON 数组
            import json
            # 尝试从 markdown code block 中提取
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            content = content.strip()
            return json.loads(content)
        except Exception as e:
            logging.warning(f"[LLM] 调用失败 (attempt {attempt+1}): {e}")
            if attempt == 2:
                raise
    return []


def generate_llm_rules(batch_size: int = 15, total_calls: int = 50) -> int:
    """Phase 2: LLM 批量生成候选规则"""
    db = get_db()
    settings = db.system_settings.find_one({"_id": "global"}) or {}

    if not settings.get("llm_api_key"):
        raise ValueError("请先在系统设置中配置 LLM API Key")

    # 从候选池中随机抽取参考规则
    candidates = list(db.rule_candidates.aggregate([{"$sample": {"size": 500}}]))
    if not candidates:
        logging.warning("[EXPLORE] 候选池为空，跳过 LLM 生成")
        return 0

    count = 0
    update_progress("llm", "LLM批量优化", llm_total=total_calls)

    for i in range(total_calls):
        # 随机选择 10-20 条参考规则
        ref_rules = random.sample(candidates, min(random.randint(10, 20), len(candidates)))

        try:
            new_rules = call_llm_batch(ref_rules, batch_size, settings)
        except Exception as e:
            logging.error(f"[LLM] 批次 {i+1} 失败: {e}")
            update_progress("llm", "LLM批量优化", llm_done=i + 1)
            continue

        for rule in new_rules:
            rule["source"] = "llm"
            if try_insert_candidate(rule):
                count += 1

        update_progress("llm", "LLM批量优化", llm_done=i + 1)
        logging.info(f"[LLM] 批次 {i+1}/{total_calls} 完成，本批新增 {len(new_rules)} 条")

    update_progress("llm", "LLM批量优化",
                    llm_done=total_calls, candidates_count=count)
    logging.info(f"[EXPLORE] LLM 生成完成，新增 {count} 条候选")
    return count
```

- [ ] **Step 2: 测试 LLM 调用**

在系统设置中配置好 LLM API Key 后，调用测试：
```python
from services.rule_explorer import call_llm_batch
settings = {"llm_api_url": "https://api.openai.com/v1", "llm_api_key": "sk-xxx", "llm_model": "gpt-4o-mini"}
result = call_llm_batch([{"type": "buy", "condition": "price > ma5 * 1.5"}], 5, settings)
print(result)
```

---

## Task 5: 后端 - 遗传算法

**Files:**
- Modify: `apps/api/services/rule_explorer.py`

- [ ] **Step 1: 添加遗传算法函数**

```python
POPULATION_SIZE = 200
GENERATIONS = 20
CROSSOVER_RATE = 0.7
MUTATION_RATE = 0.3
ELITE_SIZE = 20


def _crossover(parent_a: str, parent_b: str) -> Optional[str]:
    """交叉：在 and/or 处切分，拼接子条件"""
    def split_conditions(cond):
        parts = re.split(r'\b(and|or)\b', cond)
        return [p.strip() for p in parts if p.strip() and p not in ("and", "or")]

    parts_a = split_conditions(parent_a)
    parts_b = split_conditions(parent_b)

    if len(parts_a) < 1 or len(parts_b) < 1:
        return None

    # 随机选择切分点
    cut_a = random.randint(1, len(parts_a))
    cut_b = random.randint(0, len(parts_b) - 1)

    new_parts = parts_a[:cut_a] + parts_b[cut_b:]
    result = " and ".join(new_parts)
    return result


def _mutate(condition: str) -> Optional[str]:
    """变异：随机替换系数、变量或运算符"""
    mutations = ["coeff", "var", "op", "add"]
    choice = random.choice(mutations)

    if choice == "coeff":
        # 替换系数
        def replace_coeff(match):
            return str(random.choice(COEFFICIENTS))
        result = re.sub(r'\* \d+\.\d+', replace_coeff, condition)
        return result

    elif choice == "var":
        # 替换变量
        words = re.findall(r'[a-z_]\w*', condition)
        if not words:
            return None
        old_var = random.choice(words)
        if old_var not in ALLOWED_VARS:
            return None
        new_var = random.choice(VARIABLES)
        return condition.replace(old_var, new_var, 1)

    elif choice == "op":
        # 替换运算符
        for op in [" > ", " < ", " >= ", " <= "]:
            if op in condition:
                new_op = random.choice([" > ", " < ", " >= ", " <= "])
                return condition.replace(op, new_op, 1)
        return None

    elif choice == "add":
        # 添加新条件
        pair = random.choice(ALL_PAIRS)
        op = random.choice(OPERATORS)
        coeff = random.choice(COEFFICIENTS)
        connector = random.choice(["and", "or"])
        new_cond = f"{pair[0]} {op} {pair[1]} * {coeff}"
        return f"{condition} {connector} {new_cond}"

    return None


def generate_genetic_rules() -> int:
    """Phase 3: 遗传算法生成候选规则"""
    db = get_db()

    # 从候选池中随机抽取初始种群
    initial = list(db.rule_candidates.aggregate([{"$sample": {"size": POPULATION_SIZE}}]))
    if len(initial) < 10:
        logging.warning("[GENETIC] 候选池不足，跳过遗传算法")
        return 0

    population = [r["condition"] for r in initial]
    count = 0
    update_progress("genetic", "遗传算法进化", genetic_total=GENERATIONS)

    for gen in range(GENERATIONS):
        new_individuals = []

        # 精英保留
        scored = [(r.get("composite_score") or 0, r) for r in initial]
        scored.sort(key=lambda x: x[0], reverse=True)
        elites = [s[1]["condition"] for s in scored[:ELITE_SIZE]]
        new_individuals.extend(elites)

        # 交叉和变异
        while len(new_individuals) < POPULATION_SIZE:
            if random.random() < CROSSOVER_RATE and len(population) >= 2:
                a, b = random.sample(population, 2)
                child = _crossover(a, b)
                if child:
                    new_individuals.append(child)

            if random.random() < MUTATION_RATE:
                parent = random.choice(population)
                child = _mutate(parent)
                if child:
                    new_individuals.append(child)

        population = new_individuals[:POPULATION_SIZE]

        # 写入候选池
        for cond in population:
            rule = {
                "source": "genetic",
                "generation": gen,
                "type": random.choice(["buy", "sell", "risk"]),
                "name": f"遗传_第{gen}代",
                "condition": cond,
                "priority": 3,
                "weight": 0.35,
            }
            if try_insert_candidate(rule):
                count += 1

        update_progress("genetic", "遗传算法进化", genetic_done=gen + 1)
        logging.info(f"[GENETIC] 第 {gen+1}/{GENERATIONS} 代完成")

    update_progress("genetic", "遗传算法进化", genetic_done=GENERATIONS)
    logging.info(f"[EXPLORE] 遗传算法完成，新增 {count} 条候选")
    return count
```

---

## Task 6: 后端 - 验证与一键更新

**Files:**
- Modify: `apps/api/services/rule_explorer.py`

- [ ] **Step 1: 添加验证函数**

```python
def sample_stocks(n: int = 500) -> List[str]:
    """抽样 n 只股票用于回测"""
    db = get_db()
    all_codes = db.stock_kline.distinct("code", {"frequency": 9})

    # 获取股票名称，剔除 ST
    name_map = {}
    for s in db.sector_stocks.find({}, {"stock_code": 1, "stock_name": 1}):
        name_map[s["stock_code"].split(".")[-1]] = s.get("stock_name", "")

    filtered = [c for c in all_codes if not name_map.get(c, "").startswith(("ST", "*ST"))]

    # 随机抽样
    if len(filtered) <= n:
        return filtered
    return random.sample(filtered, n)


def validate_candidates(scope: str = "all", limit: int = 500, backtest_days: int = 180):
    """验证候选规则：组合回测评分"""
    from services.backtest_engine import run_backtest

    db = get_db()

    # 构建查询
    query = {"validated": False}
    if scope != "all":
        query["source"] = scope

    candidates = list(db.rule_candidates.find(query).limit(limit * 3))
    if not candidates:
        logging.info("[VALIDATE] 没有需要验证的候选规则")
        return

    # 抽样股票
    stock_codes = sample_stocks(500)

    # 按 type 分组
    by_type = {"buy": [], "sell": [], "risk": []}
    for c in candidates:
        t = c.get("type", "buy")
        if t in by_type:
            by_type[t].append(c)

    # 组装规则集（笛卡尔积，取前 limit 个组合）
    import itertools
    combos = list(itertools.product(
        by_type["buy"][:20],
        by_type["sell"][:20],
        by_type["risk"][:20]
    ))
    random.shuffle(combos)
    combos = combos[:limit]

    logging.info(f"[VALIDATE] 开始验证 {len(combos)} 个规则集，抽样 {len(stock_codes)} 只股票")

    best_scores = {}  # candidate_id -> best_score

    for i, (buy_rule, sell_rule, risk_rule) in enumerate(combos):
        rule_set = [buy_rule, sell_rule, risk_rule]

        try:
            result = run_backtest(
                codes=stock_codes,
                start_date=(datetime.now() - pd.Timedelta(days=backtest_days)).strftime("%Y-%m-%d"),
                end_date=datetime.now().strftime("%Y-%m-%d"),
            )

            score = composite_score(
                result.get("sharpe", 0),
                result.get("total_return", 0),
                result.get("win_rate", 0),
                result.get("trades", 0),
                backtest_days
            )

            # 更新每条候选规则的最优分数
            for rule in rule_set:
                rid = rule["_id"]
                if rid not in best_scores or score > best_scores[rid]:
                    best_scores[rid] = score

        except Exception as e:
            logging.error(f"[VALIDATE] 回测失败: {e}")
            continue

        if (i + 1) % 50 == 0:
            logging.info(f"[VALIDATE] 进度 {i+1}/{len(combos)}")

    # 批量更新候选规则的评分
    for rid, score in best_scores.items():
        db.rule_candidates.update_one(
            {"_id": rid},
            {"$set": {"validated": True, "composite_score": score}}
        )

    # 处理黑名单
    for c in candidates:
        if c.get("composite_score") is not None:
            is_bl, reason = should_blacklist(
                c.get("sharpe", 0), c.get("total_return", 0),
                c.get("win_rate", 0), c.get("trades", 0)
            )
            if is_bl:
                normalized = c.get("condition_normalized", normalize_condition(c["condition"]))
                db.rule_blacklist.update_one(
                    {"condition_normalized": normalized},
                    {"$set": {
                        "condition": c["condition"],
                        "condition_normalized": normalized,
                        "type": c["type"],
                        "sharpe": c.get("sharpe", 0),
                        "reason": reason,
                        "created_at": datetime.now(),
                    }},
                    upsert=True
                )

    logging.info(f"[VALIDATE] 验证完成，更新 {len(best_scores)} 条候选评分")
```

- [ ] **Step 2: 添加一键更新函数**

```python
def apply_candidates() -> str:
    """一键更新：用最优候选替换当前规则"""
    db = get_db()

    # 读取已验证的候选，按 composite_score 降序
    candidates = list(db.rule_candidates.find(
        {"validated": True, "composite_score": {"$gt": 0}}
    ).sort("composite_score", -1))

    # 按 type 分组取 top-1
    best = {}
    for c in candidates:
        t = c.get("type")
        if t and t not in best:
            best[t] = c
        if len(best) == 3:
            break

    if len(best) < 3:
        return "候选规则不完整，需要至少1条买入+1条卖出+1条风控"

    # 备份当前规则
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

    # 替换规则
    db.trading_rules.delete_many({})
    for rule_type, rule in best.items():
        rule.pop("_id", None)
        rule["rule_id"] = db.trading_rules.count_documents({}) + 1
        rule["enabled"] = True
        rule["created_at"] = datetime.now()
        rule["updated_at"] = datetime.now()
        db.trading_rules.insert_one(rule)

    best_score = max(c.get("composite_score", 0) for c in best.values())
    return f"已更新 {len(best)} 条规则，最优评分 {best_score}"
```

---

## Task 7: 后端 - Settings.py 新增 LLM 配置

**Files:**
- Modify: `apps/api/routers/settings.py`

- [ ] **Step 1: 在 DEFAULTS 中添加 LLM 配置默认值**

```python
DEFAULTS = {
    # ... 现有字段 ...
    "llm_api_url": "https://api.openai.com/v1",
    "llm_api_key": "",
    "llm_model": "gpt-4o-mini",
    "llm_batch_size": 15,
}
```

- [ ] **Step 2: 在 SystemSettings model 中添加字段**

```python
class SystemSettings(BaseModel):
    # ... 现有字段 ...
    llm_api_url: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    llm_batch_size: Optional[int] = None
```

---

## Task 8: 后端 - Rules.py 新增 API 端点

**Files:**
- Modify: `apps/api/routers/rules.py`

- [ ] **Step 1: 新增探索状态查询端点**

```python
@router.get("/explore/status")
async def get_explore_status(
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    db = get_db()
    progress = db.rule_explore_progress.find_one({"_id": "current"})
    if not progress:
        return {"status": "idle", "phase": "none"}
    progress.pop("_id", None)
    return progress
```

- [ ] **Step 2: 新增启动探索端点**

```python
from tasks.rule_explore_tasks import run_rule_exploration

@router.post("/explore")
async def start_explore(
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    db = get_db()
    # 检查是否已有任务在运行
    progress = db.rule_explore_progress.find_one({"_id": "current"})
    if progress and progress.get("status") == "running":
        raise HTTPException(status_code=409, detail="已有探索任务在运行中，请等待完成")

    # 检查 LLM 配置
    settings = db.system_settings.find_one({"_id": "global"}) or {}
    if not settings.get("llm_api_key"):
        raise HTTPException(status_code=400, detail="请先在系统设置中配置 LLM API Key")

    task = run_rule_exploration.delay()
    return {"task_id": task.id, "message": "探索任务已启动"}
```

- [ ] **Step 3: 新增验证端点**

```python
from tasks.rule_explore_tasks import run_rule_validation

class ValidateRequest(BaseModel):
    scope: str = "all"
    limit: int = 500

@router.post("/validate-candidates")
async def start_validate(
    data: ValidateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    task = run_rule_validation.delay(data.scope, data.limit)
    return {"task_id": task.id, "message": "验证任务已启动"}
```

- [ ] **Step 4: 新增一键更新端点**

```python
@router.post("/apply-candidates")
async def apply_candidates_endpoint(
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    from services.rule_explorer import apply_candidates
    result = apply_candidates()
    return {"message": result}
```

- [ ] **Step 5: 新增候选列表端点**

```python
@router.get("/candidates")
async def list_candidates(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    validated: Optional[bool] = None,
    source: Optional[str] = None,
    type: Optional[str] = None,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    db = get_db()
    query = {}
    if validated is not None:
        query["validated"] = validated
    if source:
        query["source"] = source
    if type:
        query["type"] = type

    total = db.rule_candidates.count_documents(query)
    items = list(db.rule_candidates.find(query)
                 .sort("composite_score", -1)
                 .skip((page - 1) * page_size)
                 .limit(page_size))
    for item in items:
        item["_id"] = str(item["_id"])
    return {"candidates": items, "total": total, "page": page, "page_size": page_size}
```

- [ ] **Step 6: 新增删除候选和清空端点**

```python
@router.delete("/candidates/{candidate_id}")
async def delete_candidate(
    candidate_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    from bson import ObjectId
    db = get_db()
    result = db.rule_candidates.delete_one({"_id": ObjectId(candidate_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="候选规则不存在")
    return {"message": "已删除"}


class ClearRequest(BaseModel):
    scope: str = "all"

@router.delete("/candidates")
async def clear_candidates(
    data: ClearRequest,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    db = get_db()
    query = {}
    if data.scope == "validated":
        query["validated"] = True
    elif data.scope == "unvalidated":
        query["validated"] = False
    result = db.rule_candidates.delete_many(query)
    return {"message": f"已清空 {result.deleted_count} 条候选规则"}
```

- [ ] **Step 7: 新增黑名单端点**

```python
@router.get("/blacklist")
async def list_blacklist(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    db = get_db()
    total = db.rule_blacklist.count_documents({})
    items = list(db.rule_blacklist.find()
                 .sort("created_at", -1)
                 .skip((page - 1) * page_size)
                 .limit(page_size))
    for item in items:
        item["_id"] = str(item["_id"])
    return {"blacklist": items, "total": total, "page": page, "page_size": page_size}


@router.delete("/blacklist/{blacklist_id}")
async def delete_blacklist(
    blacklist_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    from bson import ObjectId
    db = get_db()
    result = db.rule_blacklist.delete_one({"_id": ObjectId(blacklist_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="黑名单记录不存在")
    return {"message": "已从黑名单移除"}
```

- [ ] **Step 8: 新增备份端点**

```python
@router.get("/backup")
async def list_backups(
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    db = get_db()
    items = list(db.rule_backup.find().sort("backup_at", -1).limit(20))
    for item in items:
        item["_id"] = str(item["_id"])
        item["rules_count"] = len(item.get("rules", []))
    return {"backups": items}


@router.post("/backup/{backup_id}/restore")
async def restore_backup(
    backup_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    from bson import ObjectId
    db = get_db()
    backup = db.rule_backup.find_one({"_id": ObjectId(backup_id)})
    if not backup:
        raise HTTPException(status_code=404, detail="备份不存在")

    rules = backup.get("rules", [])
    db.trading_rules.delete_many({})
    for rule in rules:
        rule.pop("_id", None)
        rule["rule_id"] = db.trading_rules.count_documents({}) + 1
        rule["enabled"] = True
        db.trading_rules.insert_one(rule)

    return {"message": f"已恢复 {len(rules)} 条规则"}
```

---

## Task 9: 后端 - Celery 任务定义

**Files:**
- Create: `apps/api/tasks/rule_explore_tasks.py`

- [ ] **Step 1: 创建 Celery 任务文件**

```python
import logging
from celery_config import celery_app
from database import get_db
from datetime import datetime


@celery_app.task(bind=True, name="rule_exploration")
def run_rule_exploration(self):
    """规则探索主任务：模板搜索 → LLM生成 → 遗传算法"""
    from services.rule_explorer import (
        generate_template_rules, generate_llm_rules, generate_genetic_rules,
        update_progress
    )

    db = get_db()

    # 检查是否已有任务在运行
    progress = db.rule_explore_progress.find_one({"_id": "current"})
    if progress and progress.get("status") == "running":
        return {"status": "skipped", "reason": "已有任务在运行"}

    # 初始化进度
    db.rule_explore_progress.update_one(
        {"_id": "current"},
        {"$set": {
            "status": "running",
            "phase": "template",
            "phase_label": "模板网格搜索",
            "task_id": self.request.id,
            "error_msg": "",
            "updated_at": datetime.now(),
        }},
        upsert=True
    )

    try:
        # Phase 1: 模板搜索
        template_count = generate_template_rules()

        # Phase 2: LLM 生成
        try:
            llm_count = generate_llm_rules()
        except ValueError as e:
            logging.warning(f"[EXPLORE] LLM 跳过: {e}")
            llm_count = 0

        # Phase 3: 遗传算法
        genetic_count = generate_genetic_rules()

        # 完成
        total = db.rule_candidates.count_documents({})
        update_progress("done", "探索完成",
                        candidates_count=total,
                        status="done")

        return {
            "status": "done",
            "template": template_count,
            "llm": llm_count,
            "genetic": genetic_count,
            "total_candidates": total,
        }

    except Exception as e:
        logging.error(f"[EXPLORE] 任务失败: {e}")
        update_progress("error", f"探索失败: {str(e)}",
                        status="error", error_msg=str(e))
        return {"status": "error", "error": str(e)}


@celery_app.task(bind=True, name="rule_validation")
def run_rule_validation(self, scope: str = "all", limit: int = 500):
    """验证候选规则任务"""
    from services.rule_explorer import validate_candidates

    db = get_db()
    db.rule_explore_progress.update_one(
        {"_id": "current"},
        {"$set": {
            "status": "running",
            "phase": "validation",
            "phase_label": "规则验证中",
            "task_id": self.request.id,
            "updated_at": datetime.now(),
        }},
        upsert=True
    )

    try:
        validate_candidates(scope, limit)
        db.rule_explore_progress.update_one(
            {"_id": "current"},
            {"$set": {"status": "done", "phase": "done", "phase_label": "验证完成"}}
        )
        return {"status": "done"}
    except Exception as e:
        logging.error(f"[VALIDATE] 任务失败: {e}")
        db.rule_explore_progress.update_one(
            {"_id": "current"},
            {"$set": {"status": "error", "error_msg": str(e)}}
        )
        return {"status": "error", "error": str(e)}
```

- [ ] **Step 2: 注册 Celery 任务**

确保 `celery_config.py` 中能发现这些任务，或在导入时自动注册。

---

## Task 10: 前端 - rules.js 新增 API 调用

**Files:**
- Modify: `apps/web/src/api/rules.js`

- [ ] **Step 1: 添加所有新 API 调用**

```javascript
export function validateCondition(condition) {
  return http.post('/rules/validate', { condition })
}

export function getExploreStatus() {
  return http.get('/rules/explore/status')
}

export function startExplore() {
  return http.post('/rules/explore')
}

export function startValidateCandidates(scope = 'all', limit = 500) {
  return http.post('/rules/validate-candidates', { scope, limit })
}

export function applyCandidates() {
  return http.post('/rules/apply-candidates')
}

export function getCandidates(params = {}) {
  return http.get('/rules/candidates', { params })
}

export function deleteCandidate(id) {
  return http.delete(`/rules/candidates/${id}`)
}

export function clearCandidates(scope = 'all') {
  return http.delete('/rules/candidates', { data: { scope } })
}

export function getBlacklist(params = {}) {
  return http.get('/rules/blacklist', { params })
}

export function deleteBlacklist(id) {
  return http.delete(`/rules/blacklist/${id}`)
}

export function getBackups() {
  return http.get('/rules/backup')
}

export function restoreBackup(id) {
  return http.post(`/rules/backup/${id}/restore`)
}
```

---

## Task 11: 前端 - Settings.vue 新增 LLM 配置

**Files:**
- Modify: `apps/web/src/views/admin/Settings.vue`

- [ ] **Step 1: 在 form 中添加 LLM 字段**

在 `form` ref 中添加：
```javascript
llm_api_url: 'https://api.openai.com/v1',
llm_api_key: '',
llm_model: 'gpt-4o-mini',
llm_batch_size: 15,
```

- [ ] **Step 2: 在模板中添加 LLM 配置区域**

在钉钉机器人配置区域后面添加：

```html
<!-- LLM 配置 -->
<el-divider content-position="left">LLM 配置（规则探索用）</el-divider>
<el-form-item label="API 地址">
  <el-input v-model="form.llm_api_url" placeholder="https://api.openai.com/v1" />
</el-form-item>
<el-form-item label="API Key">
  <el-input v-model="form.llm_api_key" type="password" show-password placeholder="sk-xxx" />
</el-form-item>
<el-form-item label="模型名称">
  <el-input v-model="form.llm_model" placeholder="gpt-4o-mini" />
</el-form-item>
<el-form-item label="每次生成条数">
  <el-input-number v-model="form.llm_batch_size" :min="5" :max="30" />
  <span class="hint">每次调用 LLM 生成的规则条数（5~30）</span>
</el-form-item>
```

---

## Task 12: 前端 - TradingRules.vue 新增按钮

**Files:**
- Modify: `apps/web/src/views/TradingRules.vue`

- [ ] **Step 1: 在页面顶部按钮区域添加新按钮**

```html
<el-button type="success" @click="goCandidates">候选规则</el-button>
<el-button type="warning" :loading="exploring" @click="handleExplore">规则探索</el-button>
```

- [ ] **Step 2: 添加对应的 script 逻辑**

```javascript
import { startExplore } from '@/api/rules'
import { useRouter } from 'vue-router'

const router = useRouter()
const exploring = ref(false)

function goCandidates() {
  router.push('/candidates')
}

async function handleExplore() {
  exploring.value = true
  try {
    const res = await startExplore()
    ElMessage.success(res.data.message)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '启动失败')
  } finally {
    exploring.value = false
  }
}
```

---

## Task 13: 前端 - RuleCandidates.vue 候选规则页面

**Files:**
- Create: `apps/web/src/views/RuleCandidates.vue`

- [ ] **Step 1: 创建候选规则页面**

```vue
<template>
  <div class="rule-candidates">
    <div class="page-header">
      <h2>候选规则池</h2>
      <div>
        <el-button @click="handleValidate" :loading="validating">验证规则</el-button>
        <el-button type="primary" @click="handleApply" :loading="applying">一键更新规则</el-button>
        <el-button @click="showBlacklist = true">查看黑名单</el-button>
        <el-button type="danger" @click="handleClear">清空候选</el-button>
      </div>
    </div>

    <!-- 状态栏 -->
    <el-card style="margin-bottom: 16px">
      <el-row :gutter="16">
        <el-col :span="6">
          <div class="stat-label">候选总数</div>
          <div class="stat-value">{{ stats.total }}</div>
        </el-col>
        <el-col :span="6">
          <div class="stat-label">已验证</div>
          <div class="stat-value">{{ stats.validated }}</div>
        </el-col>
        <el-col :span="6">
          <div class="stat-label">黑名单</div>
          <div class="stat-value">{{ stats.blacklist }}</div>
        </el-col>
        <el-col :span="6">
          <div class="stat-label">最优评分</div>
          <div class="stat-value">{{ stats.bestScore }}</div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 筛选 -->
    <el-row :gutter="12" style="margin-bottom: 16px">
      <el-col :span="6">
        <el-select v-model="filter.validated" clearable placeholder="验证状态" style="width:100%">
          <el-option label="已验证" :value="true" />
          <el-option label="未验证" :value="false" />
        </el-select>
      </el-col>
      <el-col :span="6">
        <el-select v-model="filter.source" clearable placeholder="来源" style="width:100%">
          <el-option label="模板" value="template" />
          <el-option label="LLM" value="llm" />
          <el-option label="遗传" value="genetic" />
        </el-select>
      </el-col>
      <el-col :span="6">
        <el-select v-model="filter.type" clearable placeholder="类型" style="width:100%">
          <el-option label="买入" value="buy" />
          <el-option label="卖出" value="sell" />
          <el-option label="风控" value="risk" />
        </el-select>
      </el-col>
      <el-col :span="6">
        <el-button @click="fetchCandidates">筛选</el-button>
      </el-col>
    </el-row>

    <!-- 候选列表 -->
    <el-table :data="candidates" v-loading="loading" stripe>
      <el-table-column prop="source" label="来源" width="70">
        <template #default="{ row }">
          <el-tag size="small" :type="sourceType(row.source)">{{ row.source }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="type" label="类型" width="60">
        <template #default="{ row }">
          <el-tag size="small" :type="typeTag(row.type)">{{ typeLabel(row.type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="condition" label="条件" min-width="300" show-overflow-tooltip />
      <el-table-column prop="composite_score" label="综合评分" width="90" sortable />
      <el-table-column prop="validated" label="状态" width="70">
        <template #default="{ row }">
          <el-tag :type="row.validated ? 'success' : 'info'" size="small">
            {{ row.validated ? '已验证' : '待验证' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80">
        <template #default="{ row }">
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[50, 100, 200]"
      layout="total, sizes, prev, pager, next"
      @size-change="fetchCandidates"
      @current-change="fetchCandidates"
      style="margin-top: 16px; justify-content: center"
    />

    <!-- 黑名单弹窗 -->
    <el-dialog v-model="showBlacklist" title="规则黑名单" width="800px">
      <el-table :data="blacklist" stripe>
        <el-table-column prop="type" label="类型" width="60">
          <template #default="{ row }">{{ typeLabel(row.type) }}</template>
        </el-table-column>
        <el-table-column prop="condition" label="条件" min-width="250" show-overflow-tooltip />
        <el-table-column prop="reason" label="原因" width="120" />
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button size="small" @click="handleRemoveBlacklist(row)">移除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getCandidates, deleteCandidate, clearCandidates,
  startValidateCandidates, applyCandidates,
  getBlacklist, deleteBlacklist
} from '@/api/rules'

const loading = ref(false)
const validating = ref(false)
const applying = ref(false)
const candidates = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const showBlacklist = ref(false)
const blacklist = ref([])
const filter = ref({ validated: null, source: null, type: null })
const stats = ref({ total: 0, validated: 0, blacklist: 0, bestScore: 0 })

function sourceType(s) { return { template: '', llm: 'success', genetic: 'warning' }[s] || 'info' }
function typeTag(t) { return { buy: 'danger', sell: 'warning', risk: '' }[t] || 'info' }
function typeLabel(t) { return { buy: '买入', sell: '卖出', risk: '风控' }[t] || t }

async function fetchCandidates() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (filter.value.validated !== null) params.validated = filter.value.validated
    if (filter.value.source) params.source = filter.value.source
    if (filter.value.type) params.type = filter.value.type
    const res = await getCandidates(params)
    candidates.value = res.data.candidates || []
    total.value = res.data.total || 0
  } catch { ElMessage.error('获取候选规则失败') }
  finally { loading.value = false }
}

async function fetchStats() {
  try {
    const [cands, bl] = await Promise.all([
      getCandidates({ page: 1, page_size: 1 }),
      getBlacklist({ page: 1, page_size: 1 }),
    ])
    stats.value.total = cands.data.total || 0
    const validatedRes = await getCandidates({ page: 1, page_size: 1, validated: true })
    stats.value.validated = validatedRes.data.total || 0
    stats.value.blacklist = bl.data.total || 0
    if (validatedRes.data.candidates?.[0]) {
      stats.value.bestScore = validatedRes.data.candidates[0].composite_score || 0
    }
  } catch {}
}

async function fetchBlacklist() {
  try {
    const res = await getBlacklist({ page: 1, page_size: 100 })
    blacklist.value = res.data.blacklist || []
  } catch {}
}

async function handleDelete(row) {
  try {
    await deleteCandidate(row._id)
    ElMessage.success('已删除')
    fetchCandidates()
    fetchStats()
  } catch { ElMessage.error('删除失败') }
}

async function handleClear() {
  try {
    await ElMessageBox.confirm('确定清空所有候选规则？', '提示')
    await clearCandidates('all')
    ElMessage.success('已清空')
    fetchCandidates()
    fetchStats()
  } catch {}
}

async function handleValidate() {
  validating.value = true
  try {
    await startValidateCandidates('all', 500)
    ElMessage.success('验证任务已启动')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '启动验证失败')
  } finally { validating.value = false }
}

async function handleApply() {
  try {
    await ElMessageBox.confirm('确定用最优候选替换当前规则？会自动备份。', '一键更新')
    applying.value = true
    const res = await applyCandidates()
    ElMessage.success(res.data.message)
    fetchCandidates()
    fetchStats()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '更新失败')
  } finally { applying.value = false }
}

async function handleRemoveBlacklist(row) {
  try {
    await deleteBlacklist(row._id)
    ElMessage.success('已移除')
    fetchBlacklist()
    fetchStats()
  } catch { ElMessage.error('移除失败') }
}

onMounted(() => {
  fetchCandidates()
  fetchStats()
  fetchBlacklist()
})
</script>

<style scoped>
.rule-candidates { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; }
.stat-label { font-size: 12px; color: #909399; }
.stat-value { font-size: 24px; font-weight: bold; margin-top: 4px; }
</style>
```

---

## Task 14: 前端 - 路由注册

**Files:**
- Modify: `apps/web/src/router/index.js` (或对应的路由文件)

- [ ] **Step 1: 添加候选规则页面路由**

```javascript
{
  path: '/candidates',
  name: 'RuleCandidates',
  component: () => import('@/views/RuleCandidates.vue'),
  meta: { title: '候选规则', requiresAuth: true }
}
```

---

## Task 15: 集成测试

- [ ] **Step 1: 启动应用，验证所有端点可访问**

```bash
# 检查后端启动无报错
# 检查前端页面可访问
```

- [ ] **Step 2: 测试规则探索流程**

1. 在系统设置中配置 LLM API Key
2. 点击"规则探索"按钮
3. 观察进度更新
4. 检查 `rule_candidates` 集合中有数据

- [ ] **Step 3: 测试验证流程**

1. 点击"验证规则"按钮
2. 观察候选规则的 `validated` 和 `composite_score` 更新

- [ ] **Step 4: 测试一键更新**

1. 点击"一键更新规则"
2. 检查 `trading_rules` 集合被更新
3. 检查 `rule_backup` 集合有备份

---

## 执行顺序

按以下顺序执行任务，每个任务完成后提交：

1. Task 1: MongoDB 索引初始化
2. Task 2: rule_explorer.py 基础函数
3. Task 3: 模板搜索生成
4. Task 4: LLM 批量生成
5. Task 5: 遗传算法
6. Task 6: 验证与一键更新
7. Task 7: Settings.py LLM 配置
8. Task 8: Rules.py API 端点
9. Task 9: Celery 任务定义
10. Task 10: 前端 rules.js API
11. Task 11: 前端 Settings.vue
12. Task 12: 前端 TradingRules.vue
13. Task 13: 前端 RuleCandidates.vue
14. Task 14: 路由注册
15. Task 15: 集成测试
