import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime
from database import get_db

db = get_db()

# 备份当前规则
current = list(db.trading_rules.find({}))
if current:
    db.rule_backup.insert_one({
        "backup_at": datetime.now(),
        "source": "reset_to_default",
        "rules": [{k: v for k, v in r.items() if k != "_id"} for r in current]
    })
    print(f"已备份 {len(current)} 条旧规则")

# 删除旧规则
db.trading_rules.delete_many({})

rules = [
    {"name": "短期趋势向上", "type": "buy", "priority": 1, "weight": 3.0,
     "condition": "price > ma5 and ma5 > ma10"},
    {"name": "放量突破", "type": "buy", "priority": 2, "weight": 2.0,
     "condition": "vol > ma5_vol * 1.1"},
    {"name": "RSI中性偏强", "type": "buy", "priority": 3, "weight": 1.5,
     "condition": "rsi > 45 and rsi < 70"},
    {"name": "振幅适中", "type": "buy", "priority": 4, "weight": 1.0,
     "condition": "amplitude < 0.08"},
    {"name": "非低价股", "type": "buy", "priority": 5, "weight": 1.0,
     "condition": "price > 5"},
    {"name": "短期趋势向下", "type": "sell", "priority": 1, "weight": 3.0,
     "condition": "price < ma5 and ma5 < ma10"},
    {"name": "RSI超买", "type": "sell", "priority": 2, "weight": 2.0,
     "condition": "rsi > 75"},
    {"name": "止损-7%", "type": "risk", "priority": 1, "weight": 0.0,
     "condition": "has_pos and price < cost * 0.93"},
]

for i, r in enumerate(rules, 1):
    r["rule_id"] = i
    r["enabled"] = True
    r["created_at"] = datetime.now()
    r["updated_at"] = datetime.now()

db.trading_rules.insert_many(rules)
print(f"已创建 {len(rules)} 条默认规则:")
for r in rules:
    sign = " +" if r["type"] == "buy" else (" -" if r["type"] == "sell" else " !")
    print(f"  [{r['type']}] {r['name']} (weight={r['weight']})")
