"""
板块-股票映射数据导入脚本
从CSV文件读取板块-股票映射关系，导入MongoDB的sector_stocks集合
"""
import csv
import re
import sys
import os
from datetime import datetime
from pymongo import MongoClient, ASCENDING

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config import settings


def get_mongo_client():
    """获取MongoDB连接"""
    return MongoClient(f"mongodb://{settings.mongodb_host}:{settings.mongodb_port}/")


def import_sector_data(csv_path=None):
    """导入板块-股票映射数据"""
    if csv_path is None:
        csv_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', 'stock_industry.csv'
        )
    
    if not os.path.exists(csv_path):
        print(f"错误: CSV文件不存在: {csv_path}")
        return False
    
    client = get_mongo_client()
    db = client[settings.mongodb_db]
    collection = db.sector_stocks
    
    # 读取CSV并导入（幂等upsert: replace_one with sector_name+stock_code 作为复合key）
    count = 0
    insert_count = 0
    update_count = 0
    errors = 0
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                code = row.get('code', '').strip()
                code_name = row.get('code_name', '').strip()
                industry = row.get('industry', '').strip()
                
                if not code or not industry:
                    continue
                
                sector_code = ''
                sector_name = industry
                m = re.match(r'^([A-Z]\d+)(.+)$', industry)
                if m:
                    sector_code = m.group(1)
                    sector_name = m.group(2).strip()
                
                doc = {
                    'sector_name': sector_name,
                    'sector_code': sector_code,
                    'stock_code': code,
                    'stock_name': code_name,
                    'imported_at': datetime.now()
                }
                
                filter_key = {'sector_name': sector_name, 'stock_code': code}
                existing = collection.find_one(filter_key)
                if existing:
                    collection.replace_one({'_id': existing['_id']}, doc)
                    update_count += 1
                else:
                    collection.insert_one(doc)
                    insert_count += 1
                
                count += 1
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"导入行失败: {row} - {e}")
    
    # 创建索引
    collection.create_index([("sector_name", ASCENDING)])
    collection.create_index([("stock_code", ASCENDING)])
    collection.create_index([("sector_name", ASCENDING), ("stock_code", ASCENDING)], unique=True)
    
    print(f"\n导入完成:")
    print(f"  总计处理: {count} 条")
    print(f"  新增: {insert_count} 条")
    print(f"  更新: {update_count} 条")
    print(f"  失败: {errors} 条")
    
    # 验证数据
    sectors = collection.distinct("sector_name")
    print(f"  板块数量: {len(sectors)}")
    print(f"  前5个板块: {sectors[:5]}")
    
    client.close()
    return True


if __name__ == "__main__":
    csv_file = sys.argv[1] if len(sys.argv) > 1 else None
    success = import_sector_data(csv_file)
    sys.exit(0 if success else 1)
