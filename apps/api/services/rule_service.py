from datetime import datetime
from typing import Dict, Any, List, Optional
from database import get_db
from bson import ObjectId


class RuleService:

    COLLECTION = "trading_rules"

    @staticmethod
    def list_rules(page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        db = get_db()
        total = db[RuleService.COLLECTION].count_documents({})
        results = list(db[RuleService.COLLECTION].find()
                       .sort("rule_id", 1)
                       .skip((page - 1) * page_size).limit(page_size))
        rules = []
        for r in results:
            r["_id"] = str(r["_id"])
            rules.append(r)
        return {"rules": rules, "total": total, "page": page, "page_size": page_size}

    @staticmethod
    def get_rule(rule_id: int) -> Optional[Dict]:
        db = get_db()
        r = db[RuleService.COLLECTION].find_one({"rule_id": rule_id})
        if r:
            r["_id"] = str(r["_id"])
        return r

    @staticmethod
    def _next_id():
        """原子自增 rule_id"""
        db = get_db()
        counter = db.rule_id_counter.find_one_and_update(
            {"_id": "rule_id"},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=True
        )
        return counter["seq"]

    @staticmethod
    def create_rule(data: Dict[str, Any]) -> Dict:
        db = get_db()
        new_id = RuleService._next_id()

        doc = {
            "rule_id": new_id,
            "name": data.get("name", ""),
            "type": data.get("type", "buy"),
            "priority": data.get("priority", 3),
            "weight": data.get("weight", 0.0),
            "condition": data.get("condition", ""),
            "enabled": data.get("enabled", True),
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        db[RuleService.COLLECTION].insert_one(doc)
        doc["_id"] = str(doc["_id"])
        return doc

    @staticmethod
    def update_rule(rule_id: int, data: Dict[str, Any]) -> bool:
        db = get_db()
        update = {k: v for k, v in data.items()
                  if k in ("name", "type", "priority", "weight", "condition", "enabled")}
        if not update:
            return False
        update["updated_at"] = datetime.now()
        result = db[RuleService.COLLECTION].update_one(
            {"rule_id": rule_id}, {"$set": update})
        return result.modified_count > 0

    @staticmethod
    def delete_rule(rule_id: int) -> bool:
        db = get_db()
        result = db[RuleService.COLLECTION].delete_one({"rule_id": rule_id})
        return result.deleted_count > 0

    @staticmethod
    def batch_delete(rule_ids: List[int]) -> int:
        db = get_db()
        result = db[RuleService.COLLECTION].delete_many({"rule_id": {"$in": rule_ids}})
        return result.deleted_count
