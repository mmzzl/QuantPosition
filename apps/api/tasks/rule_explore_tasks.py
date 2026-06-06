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

    progress = db.rule_explore_progress.find_one({"_id": "current"})
    if progress and progress.get("status") == "running":
        return {"status": "skipped", "reason": "已有任务在运行"}

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
        template_count = generate_template_rules()

        try:
            llm_count = generate_llm_rules()
        except ValueError as e:
            logging.warning(f"[EXPLORE] LLM 跳过: {e}")
            llm_count = 0

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


@celery_app.task(bind=True, name="rule_validation")
def run_rule_validation(self, scope: str = "all", limit: int = 500, backtest_days: int = 360):
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
        validate_candidates(scope, limit=limit, backtest_days=backtest_days)
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
