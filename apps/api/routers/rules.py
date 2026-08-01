from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel
from bson import ObjectId
from datetime import datetime, timedelta
from app.core.auth import AuthenticatedUser, get_current_user
from database import get_db
from services.rule_service import RuleService


class ExploreRequest(BaseModel):
    phases: List[str] = ["template", "llm", "genetic"]


router = APIRouter(prefix="/rules", tags=["交易规则"])

STALE_THRESHOLD_MINUTES = 5


def _reset_stale_progress(progress: dict, db) -> dict:
    """检测并重置卡死的任务进度"""
    if progress and progress.get("status") == "running":
        updated_at = progress.get("updated_at")
        if updated_at and isinstance(updated_at, datetime):
            if datetime.now() - updated_at > timedelta(minutes=STALE_THRESHOLD_MINUTES):
                db.rule_explore_progress.update_one(
                    {"_id": "current"},
                    {"$set": {
                        "status": "error", "phase": "stale",
                        "phase_label": "任务已失效（Celery 重启或崩溃）",
                        "error_msg": "上次任务未正常结束，已自动重置",
                        "updated_at": datetime.now(),
                    }}
                )
                progress["status"] = "error"
                progress["phase_label"] = "任务已失效，可重新开始"
    return progress

FORBIDDEN_NAMES = {
    "import", "exec", "eval", "os", "sys", "subprocess",
    "__import__", "__builtins__", "__class__", "__subclasses__",
    "getattr", "setattr", "delattr", "globals", "locals", "vars",
    "compile", "breakpoint", "exit", "quit",
}

TEST_CTX = {
    "price": 25.5, "vol": 100000, "ma5": 25.0, "ma10": 24.5,
    "ma20": 24.0, "ma60": 23.5,
    "ma5_vol": 80000, "last_close": 25.3, "high": 27.0, "low": 23.0,
    "open": 25.4,
    "rsi": 55, "atr": 1.2, "adx": 30, "amplitude": 0.035,
    "has_pos": True, "cost": 26.0,
    "buy_date": 739500, "today": 739520,
}


def _validate_condition(condition: str):
    if not condition or not condition.strip():
        return "条件不能为空"

    import ast
    try:
        tree = ast.parse(condition, mode="eval")
    except SyntaxError as e:
        return f"语法错误: {e.msg} (第{e.lineno}行第{e.offset}列)"

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            return f"不允许使用: {node.id}"
        if isinstance(node, ast.Attribute):
            return f"不允许属性访问: .{node.attr}"
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return "不允许 import"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_NAMES:
            return f"不允许调用: {node.func.id}()"

    try:
        result = eval(condition, {"__builtins__": {}}, TEST_CTX)
    except Exception as e:
        return f"执行错误: {e}"

    if not isinstance(result, (bool, int, float)):
        return f"条件必须返回 True/False，当前返回: {type(result).__name__}"

    return None


def validate_condition(condition: str):
    err = _validate_condition(condition)
    if err:
        raise HTTPException(status_code=400, detail=err)


class RuleCreate(BaseModel):
    name: str
    type: str  # buy / sell / risk
    priority: int = 3
    weight: float = 0.0
    condition: str = ""
    enabled: bool = True


class RuleUpdate(BaseModel):
    name: str = None
    type: str = None
    priority: int = None
    weight: float = None
    condition: str = None
    enabled: bool = None


class BatchDelete(BaseModel):
    rule_ids: List[int]


@router.get("")
async def list_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    return RuleService.list_rules(page, page_size)


@router.post("")
async def create_rule(
    data: RuleCreate,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    if not data.condition or not data.condition.strip():
        raise HTTPException(status_code=400, detail="条件不能为空")
    validate_condition(data.condition)
    return RuleService.create_rule(data.model_dump())


class ConditionValidate(BaseModel):
    condition: str


@router.post("/validate")
async def validate_condition_endpoint(
    data: ConditionValidate,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    err = _validate_condition(data.condition)
    if err:
        return {"valid": False, "message": err}
    try:
        result = eval(data.condition, {"__builtins__": {}}, TEST_CTX)
    except Exception as e:
        return {"valid": False, "message": str(e)}
    return {"valid": True, "message": "条件合法", "result": result}


# === 规则探索相关端点（必须在 /{rule_id} 之前）===

@router.get("/explore/status")
async def get_explore_status(
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    db = get_db()
    progress = db.rule_explore_progress.find_one({"_id": "current"})
    if not progress:
        return {"status": "idle", "phase": "none"}
    progress = _reset_stale_progress(progress, db)
    progress.pop("_id", None)
    return progress


from tasks.rule_explore_tasks import run_rule_exploration
from tasks.rule_explore_tasks import run_rule_optimization

@router.post("/explore")
async def start_explore(
    data: ExploreRequest,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    db = get_db()
    progress = db.rule_explore_progress.find_one({"_id": "current"})
    progress = _reset_stale_progress(progress, db) if progress else progress
    if progress and progress.get("status") == "running":
        raise HTTPException(status_code=409, detail="已有探索任务在运行中，请等待完成")

    settings = db.system_settings.find_one({"_id": "global"}) or {}
    if "llm" in data.phases and not settings.get("llm_api_key"):
        raise HTTPException(status_code=400, detail="LLM 阶段需要先配置 LLM API Key")

    task = run_rule_exploration.delay(data.phases)
    return {"task_id": task.id, "message": "探索任务已启动"}


from tasks.rule_explore_tasks import run_rule_validation

class ValidateRequest(BaseModel):
    scope: str = "all"
    limit: int = 500
    backtest_days: int = 360

@router.post("/validate-candidates")
async def start_validate(
    data: ValidateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    task = run_rule_validation.delay(data.scope, data.limit, data.backtest_days)
    return {"task_id": task.id, "message": "验证任务已启动"}


@router.post("/apply-candidates")
async def apply_candidates_endpoint(
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    from services.rule_explorer import apply_candidates
    result = apply_candidates()
    return {"message": result}


@router.get("/candidates")
async def list_candidates(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    validated: Optional[bool] = None,
    source: Optional[str] = None,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    db = get_db()
    query = {}
    if validated is not None:
        query["validated"] = validated
    if source:
        query["source"] = source

    total = db.rule_candidates.count_documents(query)
    items = list(db.rule_candidates.find(query)
                 .sort("composite_score", -1)
                 .skip((page - 1) * page_size)
                 .limit(page_size))
    for item in items:
        item["_id"] = str(item["_id"])
    return {"candidates": items, "total": total, "page": page, "page_size": page_size}


@router.delete("/candidates/{candidate_id}")
async def delete_candidate(
    candidate_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    db = get_db()
    result = db.rule_candidates.delete_one({"_id": ObjectId(candidate_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="候选规则不存在")
    return {"message": "已删除"}


class ClearRequest(BaseModel):
    scope: str = "all"

@router.post("/candidates/{candidate_id}/apply")
async def apply_single_candidate(
    candidate_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """用指定候选规则替换当前规则"""
    from services.rule_explorer import apply_candidate_by_id
    result = apply_candidate_by_id(candidate_id)
    return {"message": result}


@router.get("/optimized-candidates")
async def list_optimized_candidates(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    validated: Optional[bool] = None,
    parent_source: Optional[str] = None,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    db = get_db()
    query = {}
    if validated is not None:
        query["validated"] = validated
    if parent_source:
        query["parent_source"] = parent_source

    total = db.rule_candidates_optimized.count_documents(query)
    items = list(db.rule_candidates_optimized.find(query)
                 .sort("created_at", -1)
                 .skip((page - 1) * page_size)
                 .limit(page_size))
    for item in items:
        item["_id"] = str(item["_id"])
    return {"candidates": items, "total": total, "page": page, "page_size": page_size}


class OptimizeRequest(BaseModel):
    scope: str = "all"
    limit: int = 500


@router.post("/optimized-candidates/validate")
async def start_optimized_validate(
    data: ValidateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """启动优化后候选规则验证（复用候选验证引擎，落盘到 rule_candidates_optimized）"""
    db = get_db()
    progress = db.rule_explore_progress.find_one({"_id": "current"})
    progress = _reset_stale_progress(progress, db) if progress else progress
    if progress and progress.get("status") == "running":
        raise HTTPException(status_code=409, detail="已有任务在运行中，请等待完成")

    task = run_rule_validation.delay(data.scope, data.limit, data.backtest_days, target="optimized")
    return {"task_id": task.id, "message": "优化后规则验证任务已启动"}


@router.get("/optimized-candidates/backtest")
async def get_optimized_candidate_backtest(
    id: str = Query(..., description="优化后候选规则 _id"),
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    db = get_db()
    try:
        cand = db.rule_candidates_optimized.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=404, detail="规则不存在")
    if not cand:
        raise HTTPException(status_code=404, detail="规则不存在")
    result = cand.get("backtest_result") or {}
    trades = result.get("trades", [])
    return {
        "trades": trades,
        "sharpe": round(result.get("sharpe", 0), 2),
        "portfolio_return": round(result.get("portfolio_return", 0), 2),
        "win_rate": round(result.get("win_rate", 0), 1),
        "total_trades": len(trades),
    }


@router.post("/optimize-candidates")
async def start_optimize(
    data: OptimizeRequest,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """启动 LLM 逐条优化：读取已有候选规则 → LLM优化 → 写入优化后候选表"""
    db = get_db()
    progress = db.rule_explore_progress.find_one({"_id": "current"})
    progress = _reset_stale_progress(progress, db) if progress else progress
    if progress and progress.get("status") == "running":
        raise HTTPException(status_code=409, detail="已有任务在运行中，请等待完成")

    settings = db.system_settings.find_one({"_id": "global"}) or {}
    if not settings.get("llm_api_key"):
        raise HTTPException(status_code=400, detail="LLM 优化需要先配置 LLM API Key")

    task = run_rule_optimization.delay(data.scope, data.limit)
    return {"task_id": task.id, "message": "LLM优化任务已启动"}


@router.delete("/optimized-candidates/{candidate_id}")
async def delete_optimized_candidate(
    candidate_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    db = get_db()
    result = db.rule_candidates_optimized.delete_one({"_id": ObjectId(candidate_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="优化后规则不存在")
    return {"message": "已删除"}


@router.post("/optimized-candidates/{candidate_id}/apply")
async def apply_optimized_candidate(
    candidate_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """用指定的 LLM 优化后规则替换当前规则"""
    db = get_db()
    candidate = db.rule_candidates_optimized.find_one({"_id": ObjectId(candidate_id)})
    if not candidate:
        raise HTTPException(status_code=404, detail="优化后规则不存在")

    from services.rule_explorer import _replace_rules_with_candidate
    result = _replace_rules_with_candidate(candidate)
    return {"message": result}


@router.delete("/optimized-candidates")
async def clear_optimized_candidates(
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    db = get_db()
    result = db.rule_candidates_optimized.delete_many({})
    return {"message": f"已清空 {result.deleted_count} 条优化后候选规则"}


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


@router.get("/candidates/backtest")
async def get_candidate_backtest(
    id: str = Query(..., description="候选规则 _id"),
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    db = get_db()
    try:
        cand = db.rule_candidates.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=404, detail="规则不存在")
    if not cand:
        raise HTTPException(status_code=404, detail="规则不存在")
    result = cand.get("backtest_result") or {}
    trades = result.get("trades", [])
    return {
        "trades": trades,
        "sharpe": round(result.get("sharpe", 0), 2),
        "portfolio_return": round(result.get("portfolio_return", 0), 2),
        "win_rate": round(result.get("win_rate", 0), 1),
        "total_trades": len(trades),
    }


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
    db = get_db()
    result = db.rule_blacklist.delete_one({"_id": ObjectId(blacklist_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="黑名单记录不存在")
    return {"message": "已从黑名单移除"}


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


# === 原有规则 CRUD 端点 ===

@router.get("/{rule_id}")
async def get_rule(
    rule_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    r = RuleService.get_rule(rule_id)
    if not r:
        raise HTTPException(status_code=404, detail="规则不存在")
    return r


@router.put("/{rule_id}")
async def update_rule(
    rule_id: int,
    data: RuleUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    update_data = data.model_dump(exclude_none=True)
    if "condition" in update_data and update_data["condition"]:
        validate_condition(update_data["condition"])
    ok = RuleService.update_rule(rule_id, update_data)
    if not ok:
        raise HTTPException(status_code=404, detail="规则不存在或无变化")
    return {"message": "更新成功"}


@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    ok = RuleService.delete_rule(rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="规则不存在")
    return {"message": "删除成功"}


@router.post("/batch-delete")
async def batch_delete(
    data: BatchDelete,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    if not data.rule_ids:
        raise HTTPException(status_code=400, detail="rule_ids 列表不能为空")
    count = RuleService.batch_delete(data.rule_ids)
    return {"message": f"已删除 {count} 条规则"}
