import logging
from datetime import datetime
from typing import Optional

import database as _db

logger = logging.getLogger(__name__)

COLLECTION = "backtest_progress"


def update_progress(
    task_id: str,
    current: int = 0,
    total: int = 0,
    status: str = "PENDING",
    detail: Optional[str] = None,
) -> None:
    doc = {
        "current": current,
        "total": total,
        "status": status,
        "updated_at": datetime.now(),
    }
    if detail is not None:
        doc["detail"] = detail
    try:
        db = _db.get_db()
        db[COLLECTION].update_one({"_id": task_id}, {"$set": doc}, upsert=True)
    except Exception as e:
        logger.error("Failed to update progress for task %s: %s", task_id, e)


def get_progress(task_id: str) -> dict:
    try:
        db = _db.get_db()
        doc = db[COLLECTION].find_one({"_id": task_id})
        if doc is None:
            return {"task_id": task_id, "current": 0, "total": 0, "status": "PENDING"}
        return {
            "task_id": task_id,
            "current": doc.get("current", 0),
            "total": doc.get("total", 0),
            "status": doc.get("status", "UNKNOWN"),
            "detail": doc.get("detail", ""),
            "updated_at": doc.get("updated_at"),
        }
    except Exception as e:
        logger.error("Failed to get progress for task %s: %s", task_id, e)
        return {"task_id": task_id, "current": 0, "total": 0, "status": "ERROR", "detail": str(e)}
