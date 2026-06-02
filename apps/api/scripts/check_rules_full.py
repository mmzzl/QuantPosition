import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db
db = get_db()
print(f"total={db.trading_rules.count_documents({})}, enabled={db.trading_rules.count_documents({'enabled': True})}")
for r in db.trading_rules.find().sort("rule_id", 1):
    print(f"\nrule_id={r['rule_id']}")
    print(f"  name={r['name']}")
    print(f"  type={r['type']}")
    print(f"  weight={r['weight']}")
    print(f"  priority={r['priority']}")
    print(f"  condition={r['condition']}")
    print(f"  enabled={r['enabled']}")
