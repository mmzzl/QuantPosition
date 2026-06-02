import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db

db = get_db()
db.rule_explore_progress.update_one(
    {"_id": "current"},
    {"$set": {"status": "idle", "phase": "none", "phase_label": ""}}
)
print("ok")
