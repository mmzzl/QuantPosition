import ast
import re
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from database import get_db

# ============================================================
# 常量定义
# ============================================================

VARIABLES = [
    "price", "vol", "ma5", "ma10", "ma20", "ma60", "ma5_vol",
    "last_close", "high", "low", "open",
    "has_pos", "cost", "buy_date", "today",
    "rsi", "atr", "adx", "amplitude"
]

ALLOWED_VARS = set(VARIABLES) | {"and", "or", "not", "True", "False", "abs"}

OPERATORS = [">", "<", ">=", "<="]

COEFFICIENTS = [0.8, 0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15, 1.2, 1.3, 1.5, 1.8, 2.0]

PRICE_PAIRS = [
    ("price", "ma5"), ("price", "ma10"), ("price", "ma20"), ("price", "ma60"),
    ("price", "last_close"), ("price", "high"), ("price", "low"), ("price", "open"),
    ("ma5", "ma10"), ("ma5", "ma20"), ("ma10", "ma20"), ("ma20", "ma60"),
    ("price", "cost"),
]
VOL_PAIRS = [("vol", "ma5_vol")]
HOLD_PAIRS = [("today", "buy_date")]
TECH_PAIRS = [
    ("rsi", "70"), ("rsi", "30"), ("adx", "25"), ("adx", "20"),
    ("amplitude", "0.03"), ("amplitude", "0.05"),
]
ALL_PAIRS = PRICE_PAIRS + VOL_PAIRS + HOLD_PAIRS + TECH_PAIRS


# ============================================================
# 基础工具函数
# ============================================================

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
    """规范化条件字符串"""
    s = condition_str.strip()
    s = re.sub(r'\s+', '', s)
    s = re.sub(r'>=', '≥', s)
    s = re.sub(r'<=', '≤', s)
    s = re.sub(r'!=', '≠', s)
    return s.lower()


def is_blacklisted(key: str) -> bool:
    db = get_db()
    return db.rule_blacklist.find_one({"key": key}) is not None


def is_duplicate(key: str) -> bool:
    db = get_db()
    return db.rule_candidates.find_one({"key": key}) is not None


def _generate_single_condition() -> str:
    """随机生成一条单条件表达式"""
    left, right = random.choice(ALL_PAIRS)
    op = random.choice(OPERATORS)
    coeff = random.choice(COEFFICIENTS)
    return f"{left} {op} {right} * {coeff}"


def _generate_double_condition() -> str:
    """随机生成一条双条件表达式"""
    pairs = random.sample(ALL_PAIRS, 2)
    (l1, r1), (l2, r2) = pairs
    op1, op2 = random.choice(OPERATORS), random.choice(OPERATORS)
    c1, c2 = random.choice(COEFFICIENTS), random.choice(COEFFICIENTS)
    connector = random.choice(["and", "or"])
    return f"{l1} {op1} {r1} * {c1} {connector} {l2} {op2} {r2} * {c2}"


BOUNDED_VARS = {
    "rsi": (0, 100),
    "adx": (0, 100),
    "amplitude": (0, 1),
}

def _impossible_comparison(condition: str) -> bool:
    """检测不可能成立的条件：如 rsi > 140 或 adx > 80 * 1.5 永远为 False"""
    for var, (lo, hi) in BOUNDED_VARS.items():
        for op_sym, is_gt in ((">", True), ("<", False)):
            for op in (op_sym, op_sym + "="):
                pat = re.compile(rf'\b{var}\s*{op}\s*([\d.]+(?:\s*\*\s*[\d.]+)?)')
                for m in pat.finditer(condition):
                    val_str = m.group(1)
                    if "*" in val_str:
                        a, b = val_str.split("*")
                        val = float(a.strip()) * float(b.strip())
                    else:
                        val = float(val_str)
                    if is_gt and val > hi:
                        return True
                    if not is_gt and val < lo:
                        return True
    return False


def _is_trivial_condition(condition: str) -> bool:
    """检测无意义的条件：自引用、恒真、无价格/量/技术指标"""
    try:
        tree = ast.parse(condition, mode="eval")
        vars_found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                vars_found.add(node.id)
            # 自引用比较：ma5 > ma5
            if isinstance(node, ast.Compare):
                left_var = node.left.id if isinstance(node.left, ast.Name) else None
                for c in node.comparators:
                    right_var = c.id if isinstance(c, ast.Name) else None
                    if left_var and right_var and left_var == right_var:
                        return True
        # 只有 has_pos/today/buy_date，没有价格量指标 → 无方向性
        price_tech = {"price", "ma5", "ma10", "ma20", "ma60", "last_close", "high", "low", "open", "rsi", "adx", "amplitude", "vol", "ma5_vol"}
        if vars_found and not vars_found & price_tech:
            return True
    except Exception:
        pass
    return False


def _validate_condition(condition: str) -> bool:
    """校验单条条件是否合法"""
    ok, _ = validate_variables(condition)
    if not ok:
        return False
    if _impossible_comparison(condition):
        return False
    if _is_trivial_condition(condition):
        return False
    try:
        ast.parse(condition, mode="eval")
        return True
    except SyntaxError:
        return False


def try_insert_candidate(rule_set: dict) -> bool:
    """尝试插入一条完整规则集（买+卖+风控），返回是否成功"""
    buy = rule_set.get("buy_condition", "")
    sell = rule_set.get("sell_condition", "")
    risk = rule_set.get("risk_condition", "")

    if not buy or not sell or not risk:
        return False

    # 校验每条条件
    for cond in [buy, sell, risk]:
        if not _validate_condition(cond):
            return False

    # 买入=卖出 → 无意义(同时触发)
    if normalize_condition(buy) == normalize_condition(sell):
        return False

    # 风控不涉及 cost/atr/price → 无止损逻辑
    risk_vars = set()
    try:
        for node in ast.walk(ast.parse(risk, mode="eval")):
            if isinstance(node, ast.Name):
                risk_vars.add(node.id)
    except Exception:
        pass
    if not risk_vars & {"cost", "price", "atr", "last_close", "low"}:
        return False

    # 生成唯一 key（三条条件排序后拼接）
    parts = sorted([normalize_condition(c) for c in [buy, sell, risk]])
    key = "|".join(parts)

    if is_blacklisted(key):
        return False
    if is_duplicate(key):
        return False

    db = get_db()
    doc = {
        "source": rule_set.get("source", "unknown"),
        "generation": rule_set.get("generation", 0),
        "name": rule_set.get("name", ""),
        "buy_condition": buy,
        "sell_condition": sell,
        "risk_condition": risk,
        "key": key,
        "priority": rule_set.get("priority", 3),
        "weight": rule_set.get("weight", 0.35),
        "sharpe": None,
        "win_rate": None,
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
                    trades: int, backtest_days: int = 360) -> float:
    """综合评分：夏普40% + 年化收益40% + 胜率20% (负夏普/负收益不再被忽略)"""
    if trades < 5:
        return -999

    annualized_return = total_return / backtest_days * 365

    # Sharpe -3~3 → 0~100 (负数拉低分数)
    sharpe_clamped = min(max(sharpe, -3), 3)
    sharpe_norm = (sharpe_clamped + 3) / 6 * 100

    # 年化收益 -20%~+50% → 0~100（缩窄量程，提高收益区分度）
    ret_clamped = min(max(annualized_return, -20), 50)
    return_norm = (ret_clamped + 20) / 70 * 100

    win_norm = min(max(win_rate, 0), 100)

    score = sharpe_norm * 0.4 + return_norm * 0.4 + win_norm * 0.2
    if trades > 500:
        score *= 0.8
    elif trades < 10:
        score *= 0.6
    return round(score, 2)



def update_progress(phase: str, phase_label: str, **kwargs):
    db = get_db()
    update = {"phase": phase, "phase_label": phase_label, "updated_at": datetime.now()}
    update.update(kwargs)
    db.rule_explore_progress.update_one({"_id": "current"}, {"$set": update}, upsert=True)


# ============================================================
# Phase 1: 模板网格搜索 — 生成完整规则集
# ============================================================

def generate_template_rules() -> int:
    """生成完整规则集（买+卖+风控合一条）"""
    count = 0
    update_progress("template", "模板网格搜索", template_done=0, template_total=0)

    # 先生成大量单条件和双条件
    conditions = []
    for _ in range(3000):
        if random.random() < 0.6:
            conditions.append(_generate_double_condition())
        else:
            conditions.append(_generate_single_condition())

    # 去重
    conditions = list(set(conditions))
    random.shuffle(conditions)

    total = len(conditions)
    update_progress("template", "模板网格搜索", template_total=total)

    # 用这些条件组装完整规则集（买+卖+风控）
    for i, buy_cond in enumerate(conditions):
        sell_cond = random.choice(conditions)
        risk_cond = random.choice(conditions)

        rule_set = {
            "source": "template",
            "name": f"模板_{i:04d}",
            "buy_condition": buy_cond,
            "sell_condition": sell_cond,
            "risk_condition": risk_cond,
            "priority": 3,
            "weight": 0.35,
        }
        if try_insert_candidate(rule_set):
            count += 1

        if (i + 1) % 200 == 0:
            update_progress("template", "模板网格搜索", template_done=i + 1)

    update_progress("template", "模板网格搜索", template_done=total, candidates_count=count)
    logging.info(f"[EXPLORE] 模板搜索完成，生成 {count} 条规则集")
    return count


# ============================================================
# Phase 2: LLM 批量生成
# ============================================================

LLM_SYSTEM_PROMPT = """你是一个A股量化交易规则专家。你的任务是生成高夏普、高胜率的交易规则。

## 可用变量
price(最新价), vol(成交量)
ma5(5日均线), ma10(10日均线), ma20(20日均线), ma60(60日均线)
ma5_vol(5日均量)
last_close(昨收), high(20日最高), low(20日最低), open(开盘价)
has_pos(是否持仓), cost(持仓成本), buy_date(买入日期), today(今天)
rsi(RSI相对强弱0~100), atr(ATR真实波动幅度), adx(ADX趋势强度), amplitude(当日振幅)

运算符: > < >= <= and or not  函数: abs()

## 评分标准（你的目标）
夏普比率 ×40% + 年化收益 ×40% + 胜率 ×20%
- 夏普 >1.5 = 优秀, >0.5 = 及格, <0 = 亏损
- 年化 >30% = 优秀, >10% = 及格
- 胜率 >60% = 优秀, >45% = 及格
- 交易次数必须 >=10 次（否则直接 -999 分）

## 高夏普规则的特征（优先使用这些模式）
1. 趋势跟踪（最容易出高夏普）:
   - adx > 25（趋势确认）+ ma5 > ma20（方向）+ rsi < 70（避免追高）
2. 均线多头排列:
   - price > ma5 > ma10 > ma20（上升通道完整）
3. 量价配合:
   - price > ma5 and vol > ma5_vol * 1.2（价涨量增，可靠性高）
4. RSI + 趋势过滤（胜率高）:
   - rsi between 45~65 + ma5 > ma20（不超买的多头行情）
5. 动态止损（保护收益）:
   - has_pos and price < cost - 1.5 * atr（ATR动态止损比固定百分比更准）

## 必须避免的模式（会直接给低分）
✗ 单一变量条件: has_pos, price > 5（太简单，没有选择力）
✗ 不可能比较: price < 0, amplitude < 0
✗ 过窄范围: rsi > 55 and rsi < 58（几乎不会触发）
✗ 价格和均线反着比: price < ma5 and ma5 > ma10（方向矛盾）
✗ 只用一句话: 买入和卖出条件不要完全相同

## 策略类型要求
每条规则集必须包含买入、卖出、风控三个条件，三者形成一个完整逻辑。
尽量多样化，覆盖以下类型（每批至少包含3-4种）：
- 趋势跟踪（中长线持有）
- 动量突破（短线爆发）
- 回调低吸（RSI超卖反弹）
- 量价背离（预警反转）

## 输出格式
返回 JSON 数组，每个元素: {"name": "中文名称", "buy_condition": "...", "sell_condition": "...", "risk_condition": "..."}

只返回 JSON 数组，不要其他文字。"""


def call_llm_batch(rule_sets: List[dict], batch_size: int, settings: dict) -> List[dict]:
    """调用 LLM 生成一批完整规则集（带 429 退避重试）"""
    import time
    from openai import OpenAI, RateLimitError, APIError

    api_url = settings.get("llm_api_url", "").rstrip("/")
    api_key = settings.get("llm_api_key", "")
    model = settings.get("llm_model", "gpt-4o-mini")

    if not api_url or not api_key:
        raise ValueError("LLM 未配置")

    db = get_db()

    ref_text = ""
    if rule_sets:
        ref_rules = random.sample(rule_sets, min(random.randint(10, 15), len(rule_sets)))
        ref_text = "参考规则集：\n" + "\n".join([
            f"- 买入:{r['buy_condition']} | 卖出:{r['sell_condition']} | 风控:{r['risk_condition']}"
            for r in ref_rules
        ])

    top_text = ""
    top = list(db.rule_candidates.find(
        {"validated": True, "composite_score": {"$gt": 0}}
    ).sort("composite_score", -1).limit(10))
    if top:
        top_text = "\n当前最佳规则参考（高评分）:\n" + "\n".join([
            f"  [{r.get('composite_score',0)}分] 买入:{r['buy_condition']} | 卖出:{r['sell_condition']} | 风控:{r['risk_condition']}"
            for r in top
        ])

    if rule_sets:
        user_msg = f"""请基于以下规则集，生成 {batch_size} 条变异版本。

{ref_text}{top_text}

要求：
1. 每条规则集必须包含买入、卖出、风控三个条件
2. 买入条件要合理（能选出好股票），卖出条件要保收益
3. 风控条件必须用到 cost 或 atr（否则无效）
4. 避免太简单的条件（如 has_pos 单独作为条件）
5. 买入和卖出条件不能完全相同
6. 确保返回 {batch_size} 条不同的规则集

请返回 JSON 数组，每个元素包含：
- buy_condition: 买入条件
- sell_condition: 卖出条件
- risk_condition: 风控条件
- name: 规则名称（简短中文描述）

只返回 JSON 数组，不要其他文字。"""
    else:
        user_msg = f"""请根据系统提示词中的高夏普模式，从头生成 {batch_size} 条不同的完整规则集。

{top_text}

要求：
1. 每条规则集必须包含买入、卖出、风控三个条件
2. 买入条件要合理（能选出好股票），卖出条件要保收益
3. 风控条件必须用到 cost 或 atr（否则无效）
4. 避免太简单的条件（如 has_pos 单独作为条件）
5. 买入和卖出条件不能完全相同
6. 覆盖多种策略类型：趋势跟踪、动量突破、回调低吸、量价配合
7. 确保返回 {batch_size} 条不同的规则集

请返回 JSON 数组，每个元素包含：
- buy_condition: 买入条件
- sell_condition: 卖出条件
- risk_condition: 风控条件
- name: 规则名称（简短中文描述）

只返回 JSON 数组，不要其他文字。"""

    client = OpenAI(base_url=api_url, api_key=api_key)

    for attempt in range(6):
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": LLM_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.9,
                max_tokens=4000,
                stream=False,
            )
            content = completion.choices[0].message.content
            import json
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            return json.loads(content.strip())

        except RateLimitError:
            wait = (2 ** attempt) + random.uniform(0.5, 1.5)
            logging.warning(f"[LLM] 429 限流，等 {wait:.1f}s 后重试 (attempt {attempt+1}/6)")
            time.sleep(wait)

        except APIError as e:
            wait = (2 ** attempt) + random.uniform(0.5, 1.5)
            logging.warning(f"[LLM] API 错误: {e}，等 {wait:.1f}s 后重试")
            time.sleep(wait)

        except Exception as e:
            logging.error(f"[LLM] 未知错误: {e}")
            if attempt == 5:
                raise
            time.sleep(2)

    raise RuntimeError("LLM 调用重试 6 次仍然失败")


def generate_llm_rules(batch_size: int = 100, total_calls: int = 10) -> int:
    """Phase 2: LLM 批量生成完整规则集"""
    import time

    db = get_db()
    settings = db.system_settings.find_one({"_id": "global"}) or {}

    if not settings.get("llm_api_key"):
        raise ValueError("请先在系统设置中配置 LLM API Key")

    candidates = list(db.rule_candidates.aggregate([{"$sample": {"size": 200}}]))
    has_candidates = len(candidates) > 0

    batch_size = settings.get("llm_batch_size", batch_size)
    count = 0
    update_progress("llm", "LLM批量优化", llm_total=total_calls)

    for i in range(total_calls):
        ref_rules = random.sample(candidates, min(random.randint(10, 15), len(candidates))) if has_candidates else []

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

        # 批次间延迟，避免限流
        if i < total_calls - 1:
            time.sleep(2)

    update_progress("llm", "LLM批量优化",
                    llm_done=total_calls, candidates_count=count)
    logging.info(f"[EXPLORE] LLM 生成完成，新增 {count} 条规则集")
    return count


# ============================================================
# Phase 2.5: LLM 逐条优化已有规则（不凭空生成，改现有候选）
# ============================================================

OPTIMIZE_SYSTEM_PROMPT = """你是一个A股量化交易规则优化专家。你的任务是基于**已有的规则集**进行优化改进，而不是从零生成新规则。

## 可用变量
price(最新价), vol(成交量)
ma5(5日均线), ma10(10日均线), ma20(20日均线), ma60(60日均线)
ma5_vol(5日均量)
last_close(昨收), high(20日最高), low(20日最低), open(开盘价)
has_pos(是否持仓), cost(持仓成本), buy_date(买入日期), today(今天)
rsi(RSI相对强弱0~100), atr(ATR真实波动幅度), adx(ADX趋势强度), amplitude(当日振幅)

运算符: > < >= <= and or not  函数: abs()

## 优化要求
1. 保留原有策略思路（趋势/动量/回调等），只修正逻辑缺陷、增强有效性
2. 买入条件要有选择力，卖出条件要保收益，风控条件**必须**用到 cost 或 atr
3. 买入和卖出条件不能完全相同
4. 避免不可能比较（如 price < 0、rsi > 100）和过窄范围
5. 避免方向矛盾（如 price < ma5 and ma5 > ma10）
6. 保持条件简洁，不要无意义堆叠
7. 如果原规则已经很合理，可以只做小幅微调

## 输出格式
返回 JSON 对象（不要代码块、不要其他文字）：
{"name": "中文名称", "buy_condition": "...", "sell_condition": "...", "risk_condition": "...", "optimization_note": "优化说明（改了哪里、为什么）"}"""


def _call_llm_optimize(rule_set: dict, settings: dict) -> dict:
    """调用 LLM 优化单条规则集（带 429 退避重试）"""
    import time
    import json
    from openai import OpenAI, RateLimitError, APIError

    api_url = settings.get("llm_api_url", "").rstrip("/")
    api_key = settings.get("llm_api_key", "")
    model = settings.get("llm_model", "gpt-4o-mini")

    if not api_url or not api_key:
        raise ValueError("LLM 未配置")

    user_msg = (
        "请优化以下规则集：\n"
        f"- 名称: {rule_set.get('name', '')}\n"
        f"- 买入: {rule_set.get('buy_condition', '')}\n"
        f"- 卖出: {rule_set.get('sell_condition', '')}\n"
        f"- 风控: {rule_set.get('risk_condition', '')}\n\n"
        "请返回优化后的 JSON。"
    )

    client = OpenAI(base_url=api_url, api_key=api_key)

    for attempt in range(6):
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": OPTIMIZE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.7,
                max_tokens=2000,
                stream=False,
            )
            content = completion.choices[0].message.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            result = json.loads(content.strip())
            if not isinstance(result, dict):
                raise ValueError("LLM 返回不是 JSON 对象")
            return result
        except RateLimitError:
            wait = (2 ** attempt) + random.uniform(0.5, 1.5)
            logging.warning(f"[LLM_OPT] 429 限流，等 {wait:.1f}s 后重试 (attempt {attempt+1}/6)")
            time.sleep(wait)
        except APIError as e:
            wait = (2 ** attempt) + random.uniform(0.5, 1.5)
            logging.warning(f"[LLM_OPT] API 错误: {e}，等 {wait:.1f}s 后重试")
            time.sleep(wait)
        except Exception as e:
            logging.error(f"[LLM_OPT] 未知错误: {e}")
            if attempt == 5:
                raise
            time.sleep(2)

    raise RuntimeError("LLM 优化调用重试 6 次仍然失败")


def try_insert_optimized(rule_set: dict, parent: dict) -> bool:
    """把 LLM 优化后的规则写入 rule_candidates_optimized，返回是否成功"""
    buy = rule_set.get("buy_condition", "")
    sell = rule_set.get("sell_condition", "")
    risk = rule_set.get("risk_condition", "")

    if not buy or not sell or not risk:
        return False

    for cond in [buy, sell, risk]:
        if not _validate_condition(cond):
            return False

    if normalize_condition(buy) == normalize_condition(sell):
        return False

    parts = sorted([normalize_condition(c) for c in [buy, sell, risk]])
    key = "|".join(parts)

    db = get_db()
    if is_blacklisted(key):
        return False
    if db.rule_candidates_optimized.find_one({"key": key}):
        return False

    doc = {
        "source": "llm_evolve",
        "parent_key": parent.get("key", ""),
        "parent_source": parent.get("source", ""),
        "name": rule_set.get("name", parent.get("name", "优化后规则")),
        "buy_condition": buy,
        "sell_condition": sell,
        "risk_condition": risk,
        "optimization_note": rule_set.get("optimization_note", ""),
        "original_buy": parent.get("buy_condition", ""),
        "original_sell": parent.get("sell_condition", ""),
        "original_risk": parent.get("risk_condition", ""),
        "key": key,
        "priority": parent.get("priority", 3),
        "weight": parent.get("weight", 0.35),
        "sharpe": None,
        "win_rate": None,
        "total_return": None,
        "trades": None,
        "composite_score": None,
        "validated": False,
        "created_at": datetime.now(),
    }
    try:
        db.rule_candidates_optimized.insert_one(doc)
        return True
    except Exception as e:
        logging.error(f"写入优化后候选规则失败: {e}")
        return False


def optimize_candidates_with_llm(scope: str = "all", limit: int = 500) -> int:
    """逐条读取 rule_candidates 中的候选规则，交给 LLM 优化，写入 rule_candidates_optimized

    scope: all / unvalidated / validated
    limit: 本轮最多处理条数（已优化过的会跳过）
    """
    db = get_db()
    settings = db.system_settings.find_one({"_id": "global"}) or {}

    if not settings.get("llm_api_key"):
        raise ValueError("请先在系统设置中配置 LLM API Key")

    query = {}
    if scope == "validated":
        query["validated"] = True
    elif scope == "unvalidated":
        query["validated"] = {"$ne": True}

    # 已优化过的父规则 key（避免重复优化）
    optimized_parent_keys = set(
        d.get("parent_key", "") for d in db.rule_candidates_optimized.find({}, {"parent_key": 1})
    )

    candidates = list(db.rule_candidates.find(query))[:limit]
    logging.info(f"[LLM_OPT] 读取候选 {len(candidates)} 条（scope={scope}, limit={limit}），已优化 {len(optimized_parent_keys)} 条")

    update_progress("llm_evolve", "LLM逐条优化", llm_evolve_total=len(candidates))

    count = 0
    skipped = 0
    failed = 0
    for idx, cand in enumerate(candidates, 1):
        if cand.get("key", "") in optimized_parent_keys:
            skipped += 1
            continue
        try:
            optimized = _call_llm_optimize(cand, settings)
            if try_insert_optimized(optimized, cand):
                optimized_parent_keys.add(cand.get("key", ""))
                count += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            logging.warning(f"[LLM_OPT] 第 {idx} 条优化失败 ({cand.get('name','')}): {e}")

        if idx % 20 == 0 or idx == len(candidates):
            update_progress("llm_evolve", "LLM逐条优化",
                            llm_evolve_done=idx, llm_evolve_count=count)

    update_progress("llm_evolve", "LLM逐条优化",
                    llm_evolve_done=len(candidates), llm_evolve_count=count)
    logging.info(f"[LLM_OPT] 完成：新增 {count} 条，跳过已优化 {skipped} 条，失败 {failed} 条")
    return count


# ============================================================
# Phase 3: 遗传算法
# ============================================================

POPULATION_SIZE = 200
GENERATIONS = 20
MUTATION_RATE = 0.3


def _mutate_condition(condition: str) -> str:
    """变异一条条件"""
    choice = random.choice(["coeff", "var", "op"])

    if choice == "coeff":
        def repl(m):
            return str(random.choice(COEFFICIENTS))
        return re.sub(r'\* \d+\.\d+', repl, condition)

    elif choice == "var":
        words = [w for w in re.findall(r'[a-z_]\w*', condition) if w in ALLOWED_VARS]
        if not words:
            return condition
        old = random.choice(words)
        new = random.choice(VARIABLES)
        return condition.replace(old, new, 1)

    elif choice == "op":
        for op in [" > ", " < ", " >= ", " <= "]:
            if op in condition:
                return condition.replace(op, random.choice([" > ", " < ", " >= ", " <= "]), 1)
        return condition

    return condition


def generate_genetic_rules() -> int:
    """Phase 3: 遗传算法生成完整规则集"""
    db = get_db()

    initial = list(db.rule_candidates.aggregate([{"$sample": {"size": POPULATION_SIZE}}]))
    if len(initial) < 10:
        logging.warning("[GENETIC] 候选池不足，跳过遗传算法")
        return 0

    count = 0
    update_progress("genetic", "遗传算法进化", genetic_total=GENERATIONS)

    for gen in range(GENERATIONS):
        new_rule_sets = []

        if gen > 0 and gen % 5 == 0:
            initial = list(db.rule_candidates.aggregate([{"$sample": {"size": POPULATION_SIZE}}]))
            logging.info(f"[GENETIC] 刷新种群，当前候选池 {db.rule_candidates.count_documents({})} 条")

        for _ in range(POPULATION_SIZE):
            # 选择父代
            parent = random.choice(initial)

            # 变异
            buy = parent.get("buy_condition", "")
            sell = parent.get("sell_condition", "")
            risk = parent.get("risk_condition", "")

            if random.random() < MUTATION_RATE:
                buy = _mutate_condition(buy)
            if random.random() < MUTATION_RATE:
                sell = _mutate_condition(sell)
            if random.random() < MUTATION_RATE:
                risk = _mutate_condition(risk)

            # 交叉：随机替换一条条件
            if random.random() < 0.3:
                other = random.choice(initial)
                swap = random.choice(["buy", "sell", "risk"])
                if swap == "buy":
                    buy = other.get("buy_condition", buy)
                elif swap == "sell":
                    sell = other.get("sell_condition", sell)
                else:
                    risk = other.get("risk_condition", risk)

            rule_set = {
                "source": "genetic",
                "generation": gen,
                "name": f"遗传_第{gen}代",
                "buy_condition": buy,
                "sell_condition": sell,
                "risk_condition": risk,
                "priority": 3,
                "weight": 0.35,
            }
            if try_insert_candidate(rule_set):
                count += 1

        update_progress("genetic", "遗传算法进化", genetic_done=gen + 1)
        logging.info(f"[GENETIC] 第 {gen+1}/{GENERATIONS} 代完成")

    update_progress("genetic", "遗传算法进化", genetic_done=GENERATIONS)
    logging.info(f"[EXPLORE] 遗传算法完成，新增 {count} 条规则集")
    return count


# ============================================================
# 验证
# ============================================================

def _run_backtest_with_rules(rule_set: dict, stock_codes: List[str],
                             start_date: str, end_date: str, backtest_days: int) -> float:
    """用指定规则集跑回测，返回综合评分"""
    from services.backtest_engine import run_backtest

    # 跳过包含不可能条件的规则集
    for cond_key in ("buy_condition", "sell_condition", "risk_condition"):
        cond = rule_set.get(cond_key, "")
        if _impossible_comparison(cond):
            return -666, {"trades": 0, "portfolio_return": 0, "sharpe": 0, "win_rate": 0}

    rules = [
        {"rule_id": 1, "name": "风控", "type": "risk",
         "condition": rule_set.get("risk_condition", ""), "priority": 1, "weight": 1.0, "enabled": True},
        {"rule_id": 2, "name": "卖出", "type": "sell",
         "condition": rule_set.get("sell_condition", ""), "priority": 2, "weight": 0.5, "enabled": True},
        {"rule_id": 3, "name": "买入", "type": "buy",
         "condition": rule_set.get("buy_condition", ""), "priority": 3, "weight": 0.5, "enabled": True},
    ]

    result = run_backtest(
        codes=stock_codes, start_date=start_date, end_date=end_date,
        custom_rules=rules, max_positions=1
    )

    return composite_score(
        result.get("sharpe", 0), result.get("portfolio_return", 0),
        result.get("win_rate", 0), result.get("trades", 0), backtest_days
    ), result


def validate_candidates(scope="all", limit=500, backtest_days=360):
    """单阶段验证候选规则：单次回测，去除了多时段平均逻辑"""
    db = get_db()
    stock_codes = db.stock_kline.distinct("code", {"frequency": 9})
    blacklist_keys = set(d.get("key", "") for d in db.rule_blacklist.find({}, {"key": 1}))

    query = {"$or": [{"validated": {"$ne": True}}, {"validated": {"$exists": False}}]}
    if scope != "all":
        query["source"] = scope

    total = db.rule_candidates.count_documents(query)
    if total == 0:
        logging.info("[VALIDATE] 没有需要验证的候选规则")
        return

    p_end = datetime.now()
    p_start = p_end - timedelta(days=backtest_days)
    logging.info(f"[VALIDATE] 单次回测 {backtest_days} 天：{total} 条待验")

    processed = 0
    while True:
        batch = [c for c in db.rule_candidates.find(query).limit(limit)
                 if c.get("key", "") not in blacklist_keys]
        if not batch:
            break
        for cand in batch:
            try:
                score, result = _run_backtest_with_rules(
                    cand, stock_codes, p_start.strftime("%Y-%m-%d"),
                    p_end.strftime("%Y-%m-%d"), backtest_days
                )
                trades_list = result.get("trades_list", [])
                update = {"validated": score > 0, "composite_score": score,
                          "sharpe": round(result.get("sharpe", 0), 2),
                          "trades": result.get("trades", 0)}
                if score > 0:
                    update["portfolio_return"] = round(result.get("portfolio_return", 0), 2)
                    update["win_rate"] = round(result.get("win_rate", 0), 1)
                db.rule_candidates.update_one({"_id": cand["_id"]}, {"$set": update})
                if trades_list:
                    db.rule_candidates.update_one(
                        {"_id": cand["_id"]},
                        {"$set": {"backtest_result": {
                            "trades": trades_list,
                            "sharpe": round(result.get("sharpe", 0), 2),
                            "portfolio_return": round(result.get("portfolio_return", 0), 2),
                            "win_rate": round(result.get("win_rate", 0), 1),
                        }}}
                    )
                processed += 1
            except Exception as e:
                logging.error(f"[VALIDATE] 失败: {e}")
                db.rule_candidates.update_one(
                    {"_id": cand["_id"]},
                    {"$set": {"validated": True, "validated_error": str(e)}}
                )
        logging.info(f"[VALIDATE] 进度 {processed}/{total}")


# ============================================================
# 一键更新
# ============================================================

def apply_candidates() -> str:
    """用最优候选替换当前规则"""
    db = get_db()

    candidates = list(db.rule_candidates.find(
        {"validated": True, "composite_score": {"$gt": 0}}
    ).sort("composite_score", -1))

    if not candidates:
        return "没有通过验证的候选规则，请先运行验证"

    best = candidates[0]
    return _replace_rules_with_candidate(best)


def _replace_rules_with_candidate(candidate: dict) -> str:
    """用指定候选规则替换当前交易规则"""
    db = get_db()
    # 检查有没有不可能条件，警告但不阻止
    for cond_key, label in [("buy_condition", "买入"), ("sell_condition", "卖出"), ("risk_condition", "风控")]:
        if _impossible_comparison(candidate.get(cond_key, "")):
            logging.warning(f"[APPLY] {label}条件存在不可能的比较: {candidate.get(cond_key, '')}")

    # 备份当前规则
    current_rules = list(db.trading_rules.find({}))
    if current_rules:
        db.rule_backup.insert_one({
            "backup_at": datetime.now(),
            "source": "apply_single_candidate",
            "rules": [{k: v for k, v in r.items() if k != "_id"} for r in current_rules]
        })
        backups = list(db.rule_backup.find().sort("backup_at", -1))
        if len(backups) > 10:
            for old in backups[10:]:
                db.rule_backup.delete_one({"_id": old["_id"]})

    # 用候选规则替换
    db.trading_rules.delete_many({})
    for i, (rule_type, cond_key) in enumerate([
        ("risk", "risk_condition"),
        ("sell", "sell_condition"),
        ("buy", "buy_condition"),
    ]):
        db.trading_rules.insert_one({
            "rule_id": i + 1,
            "name": f"{candidate.get('name', '候选')}_{rule_type}",
            "type": rule_type,
            "condition": candidate.get(cond_key, ""),
            "priority": {"risk": 1, "sell": 2, "buy": 3}[rule_type],
            "weight": 0.5,
            "enabled": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        })

    return f"已更新，评分 {candidate.get('composite_score', 0)}"


def apply_candidate_by_id(candidate_id: str) -> str:
    """用指定ID的候选规则替换当前规则"""
    from bson import ObjectId
    db = get_db()
    candidate = db.rule_candidates.find_one({"_id": ObjectId(candidate_id)})
    if not candidate:
        return "候选规则不存在"
    return _replace_rules_with_candidate(candidate)
