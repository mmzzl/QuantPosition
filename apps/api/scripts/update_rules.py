import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db

db = get_db()

# 调低放量阈值: 1.3 -> 1.1
db.trading_rules.update_one(
    {"name": "放量突破"},
    {"$set": {"condition": "vol > ma5_vol * 1.1", "updated_at": __import__("datetime").datetime.now()}}
)

# 增加一条简单的买入规则: ma5 > ma10 就够了
last = db.trading_rules.find_one(sort=[("rule_id", -1)])
if last:
    new_id = last["rule_id"] + 1
    from datetime import datetime
    db.trading_rules.insert_one({
        "rule_id": new_id,
        "name": "均线多头",
        "type": "buy",
        "priority": 1,
        "weight": 2.0,
        "condition": "ma5 > ma10",
        "enabled": True,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    })
    print(f"added rule_id={new_id}")
else:
    print("no rules found")

print("done")
for r in db.trading_rules.find().sort("rule_id", 1):
    print(f"  {r['rule_id']} [{r['type']}] {r['name']} cond={r['condition']}")
