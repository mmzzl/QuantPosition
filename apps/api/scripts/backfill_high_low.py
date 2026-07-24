"""
将 stock_indicators 中缺失的 high/low 字段从 stock_kline 补充
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime
from database import get_db
from pymongo import UpdateOne

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def main():
    db = get_db()

    missing = db.stock_indicators.count_documents({"high": {"$exists": False}})
    if missing == 0:
        logging.info("所有 stock_indicators 记录已有 high 字段，无需回填")
        return

    logging.info(f"发现 {missing} 条记录缺少 high/low 字段")

    batch_size = 2000
    updated = 0

    for doc in db.stock_indicators.find({"high": {"$exists": False}}, {"code": 1, "date": 1}).batch_size(batch_size):
        code = doc["code"]
        date_str = doc["date"]

        kline = db.stock_kline.find_one(
            {"code": code, "date": {"$regex": f"^{date_str}"}},
            {"high": 1, "low": 1}
        )

        if kline and "high" in kline and "low" in kline:
            db.stock_indicators.update_one(
                {"code": code, "date": date_str},
                {"$set": {
                    "high": float(kline["high"]),
                    "low": float(kline["low"]),
                    "updated_at": datetime.now(),
                }}
            )
            updated += 1
            if updated % 10000 == 0:
                logging.info(f"已回填 {updated}/{missing} 条")

    remaining = db.stock_indicators.count_documents({"high": {"$exists": False}})
    logging.info(f"回填完成, 更新 {updated} 条, 剩余 {remaining} 条（无匹配 K 线）")


if __name__ == "__main__":
    main()