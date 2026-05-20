from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27017/')
db = client['eastmoney_news']

users = list(db.users.find())
for u in users:
    print(f"User: {u.get('username')}, ID: {u['_id']}")
    txns = list(db.transactions.find({"user_id": str(u['_id'])}))
    print(f"  Transactions: {len(txns)}")
    for t in txns[:3]:
        print(f"    - {t.get('type')}: {t.get('code')}")
