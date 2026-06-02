import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db
db = get_db()
total = db.trading_rules.count_documents({})
enabled = db.trading_rules.count_documents({"enabled": True})
print(f"total={total}, enabled={enabled}")
for r in db.trading_rules.find().sort("rule_id", 1):
    print(f"  id={r['rule_id']} type={r['type']} name={r['name']} weight={r['weight']}")
