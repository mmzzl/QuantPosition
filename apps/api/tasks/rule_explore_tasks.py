import logging
from celery_config import celery_app
from database import get_db
from datetime import datetime


@celery_app.task(bind=True, name="tasks.rule_explore.run_rule_exploration")
def run_rule_exploration(self, phases: list = None):
    """规则探索主任务：模板搜索 → LLM生成 → 遗传算法"""
    from services.rule_explorer import (
        generate_template_rules, generate_llm_rules, generate_genetic_rules,
        update_progress
    )

    if phases is None:
        phases = ["template", "llm", "genetic"]

    db = get_db()

    progress = db.rule_explore_progress.find_one({"_id": "current"})
    if progress and progress.get("status") == "running":
        return {"status": "skipped", "reason": "已有任务在运行"}

    db.rule_explore_progress.update_one(
        {"_id": "current"},
        {"$set": {
            "status": "running",
            "phase": phases[0] if phases else "done",
            "phase_label": f"规则探索 ({', '.join(phases)})",
            "task_id": self.request.id,
            "error_msg": "",
            "updated_at": datetime.now(),
        }},
        upsert=True
    )

    template_count = llm_count = genetic_count = 0

    try:
        # 如果选了 genetic 但候选池为空，自动先跑 template 播种
        if "genetic" in phases and "template" not in phases:
            if db.rule_candidates.count_documents({}) == 0:
                logging.info("[EXPLORE] 候选池为空，自动执行 template 播种")
                generate_template_rules()

        if "template" in phases:
            template_count = generate_template_rules()

        if "llm" in phases:
            try:
                llm_count = generate_llm_rules()
            except ValueError as e:
                logging.warning(f"[EXPLORE] LLM 跳过: {e}")
                llm_count = 0

        if "genetic" in phases:
            genetic_count = generate_genetic_rules()

        total = db.rule_candidates.count_documents({})
        update_progress("done", "探索完成", candidates_count=total, status="done")

        return {
            "status": "done",
            "template": template_count,
            "llm": llm_count,
            "genetic": genetic_count,
            "total_candidates": total,
        }

    except Exception as e:
        logging.error(f"[EXPLORE] 任务失败: {e}")
        update_progress("error", f"探索失败: {str(e)}", status="error", error_msg=str(e))
        return {"status": "error", "error": str(e)}


@celery_app.task(bind=True, name="tasks.rule_explore.run_rule_validation")
def run_rule_validation(self, scope: str = "all", limit: int = 500, backtest_days: int = 360, max_stocks: int = 500):
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
        validate_candidates(scope, limit=limit, backtest_days=backtest_days, max_stocks=max_stocks)
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
