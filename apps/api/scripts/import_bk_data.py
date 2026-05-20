import csv
import re
import sys
import os
from datetime import datetime
from pymongo import MongoClient, ASCENDING

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import settings


def import_bk_data(csv_path=None):
    if csv_path is None:
        csv_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', 'all_stock_industry.csv'
        )

    if not os.path.exists(csv_path):
        print(f"CSV 文件不存在: {csv_path}")
        return False

    client = MongoClient(f"mongodb://{settings.mongodb_host}:{settings.mongodb_port}/")
    db = client[settings.mongodb_db]
    collection = db.bk_stocks

    collection.delete_many({})
    print("已清空 bk_stocks 集合")

    batch = []
    batch_size = 1000
    total = 0

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                bk_name = row.get('板块名称', '').strip()
                bk_code = row.get('板块代码', '').strip().upper()
                stock_code = row.get('代码', '').strip()
                stock_name = row.get('名称', '').strip()

                if not bk_code or not stock_code:
                    continue

                if not bk_code.startswith('BK'):
                    bk_code = f"BK{bk_code}"

                batch.append({
                    'bk_code': bk_code,
                    'bk_name': bk_name,
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'imported_at': datetime.now()
                })

                if len(batch) >= batch_size:
                    collection.insert_many(batch)
                    total += len(batch)
                    batch = []

            except Exception as e:
                pass

        if batch:
            collection.insert_many(batch)
            total += len(batch)

    collection.create_index([("bk_code", ASCENDING)])
    collection.create_index([("stock_code", ASCENDING)])
    collection.create_index([("bk_code", ASCENDING), ("stock_code", ASCENDING)], unique=True)

    bks = collection.distinct("bk_code")
    print(f"导入完成: {total} 条, {len(bks)} 个 BK 板块")
    print(f"前 10 个 BK: {sorted(bks)[:10]}")

    client.close()
    return True


if __name__ == "__main__":
    csv_file = sys.argv[1] if len(sys.argv) > 1 else None
    success = import_bk_data(csv_file)
    sys.exit(0 if success else 1)
