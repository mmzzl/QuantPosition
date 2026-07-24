"""
添加板块热力图相关索引
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config import settings
from pymongo import MongoClient, ASCENDING, DESCENDING

def add_indexes():
    client = MongoClient(f"mongodb://{settings.mongodb_host}:{settings.mongodb_port}/")
    db = client[settings.mongodb_db]
    
    # stock_kline 集合索引（与 service 中使用的集合名一致）
    kline = db.stock_kline
    kline.create_index([("code", ASCENDING), ("date", DESCENDING)])
    kline.create_index([("code", ASCENDING), ("frequency", ASCENDING), ("date", DESCENDING)])
    kline.create_index([("date", DESCENDING)])
    print("stock_kline 索引已创建")
    
    # sector_stocks 集合索引已在导入脚本中创建
    print("sector_stocks 索引已存在")
    
    client.close()
    print("索引创建完成")

if __name__ == "__main__":
    add_indexes()
