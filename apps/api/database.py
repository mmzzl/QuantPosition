from pymongo import MongoClient, ASCENDING, DESCENDING
from config.config import settings

_client = None
_db = None


def get_db():
    """连接到MongoDB数据库并返回数据库对象"""
    global _client, _db
    if _db is None:
        _client = MongoClient(f"mongodb://{settings.mongodb_host}:{settings.mongodb_port}/")
        _db = _client[settings.mongodb_db]
        _ensure_indexes(_db)
    return _db


def _ensure_indexes(db):
    """确保必要的索引存在"""
    # Role collection indexes
    db.roles.create_index([("name", ASCENDING)], unique=True)
    db.roles.create_index([("role_type", ASCENDING)])
    db.roles.create_index([("parent_roles", ASCENDING)])

    # Permission collection indexes
    db.permissions.create_index([("name", ASCENDING)], unique=True)
    db.permissions.create_index([("menu_path", ASCENDING)], sparse=True)

    # UserRole collection indexes
    db.user_roles.create_index([("user_id", ASCENDING), ("role_id", ASCENDING)], unique=True)
    db.user_roles.create_index([("role_id", ASCENDING)])

    # Sector stocks collection indexes
    db.sector_stocks.create_index([("sector_name", ASCENDING)])
    db.sector_stocks.create_index([("stock_code", ASCENDING)])
    db.sector_stocks.create_index([("sector_name", ASCENDING), ("stock_code", ASCENDING)], unique=True)

    # Stock kline collection indexes
    db.stock_kline.create_index([("code", ASCENDING), ("date", DESCENDING)])
    db.stock_kline.create_index([("date", DESCENDING)])

    # BK stocks collection indexes
    db.bk_stocks.create_index([("bk_code", ASCENDING)])
    db.bk_stocks.create_index([("stock_code", ASCENDING)])
    db.bk_stocks.create_index([("bk_code", ASCENDING), ("stock_code", ASCENDING)], unique=True)

    # News selection cache indexes
    db.news_selection_cache.create_index([("created_at", -1)])
    db.news_selection_cache.create_index([("expected_return", -1)])

    # Alert log indexes
    db.alert_log.create_index([("dedup_key", ASCENDING)], unique=True)
    db.alert_log.create_index([("created_at", -1)])

    # Paper positions indexes
    db.paper_positions.create_index([("code", ASCENDING)])
    db.paper_positions.create_index([("status", ASCENDING)])
    db.paper_positions.create_index([("created_at", -1)])


def query_sort_end(colletion, sort_end = ''):
    """查询数据库中最新的新闻的realSort作为sortEnd"""
    result = colletion.find_one({
        "realSort":sort_end
    }) 
    return True if result else False


def get_sort_end(colletion):
    """查询数据库中最新的新闻的realSort作为sortEnd"""
    result = colletion.find_one(sort=[("realSort", -1)]) 
    return result['realSort'] if result else ''