from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27017/')
db = client['eastmoney_news']

print("=== Holdings ===")
holdings = list(db.holdings.find())
for h in holdings:
    print(f"  {h.get('code')} - {h.get('name')} - user_id: {h.get('user_id')}")

print("\n=== Transactions ===")
txns = list(db.transactions.find())
print(f"Total: {len(txns)}")
for t in txns:
    print(f"  {t.get('type')} - {t.get('code')} - user_id: {t.get('user_id')}")
