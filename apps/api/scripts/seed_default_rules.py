import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime
from database import get_db

db = get_db()
if db.trading_rules.count_documents({"enabled": True}) > 0:
    print("已有启用规则，跳过")
    sys.exit(0)

rules = [
    {"name": "短期趋势向上", "type": "buy", "priority": 1, "weight": 3.0,
     "condition": "price > ma5 and ma5 > ma10"},
    {"name": "放量突破", "type": "buy", "priority": 2, "weight": 2.0,
     "condition": "vol > ma5_vol * 1.3"},
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
    {"name": "止损-7%", "type": "risk", "priority": 1, "weight": 0,
     "condition": "has_pos and price < cost * 0.93"},
]

last = db.trading_rules.find_one(sort=[("rule_id", -1)])
next_id = (last["rule_id"] + 1) if last else 1

for r in rules:
    r["rule_id"] = next_id
    r["enabled"] = True
    r["created_at"] = datetime.now()
    r["updated_at"] = datetime.now()
    next_id += 1

db.trading_rules.insert_many(rules)
print(f"已创建 {len(rules)} 条默认规则:")
for r in rules:
    print(f"  [{r['type']}] {r['name']} (weight={r['weight']})")
