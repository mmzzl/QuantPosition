from pydantic_settings import BaseSettings
from typing import Optional  # 必须加这个
import os
import yaml
from systems.sys import home

class Settings(BaseSettings):
    """应用配置类"""
    # 正确写法：可选字符串，不传就是 None，不报错
    news_api_url: Optional[str] = None
    news_api_key: Optional[str] = None
    database_url: Optional[str] = None

    # MongoDB 配置
    mongodb_host: str
    mongodb_port: int
    mongodb_db: str
    mongodb_collection: str
    app_name: str
    app_version: str
    app_description: str
    # 爬虫配置
    spider_progress_file: str
    # JWT 配置
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    
    # Redis 配置
    redis_host: str = "localhost"
    redis_port: int = 6379

    # 交易费率
    commission_rate: float = 0.0003
    min_commission: float = 5.0
    transfer_rate: float = 0.00001
    stamp_duty_rate: float = 0.001

    class Config:
        extra = "allow"

def load_config(config_file='config.yaml'):
    """加载配置文件，支持 CONFIG_FILE 环境变量覆盖"""
    config_file = os.environ.get("CONFIG_FILE", config_file)
    config_path = os.path.join(home(), 'apps', 'api', 'config', config_file)
    print("加载配置文件:", config_path)
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    jwt_config = config.get('jwt', {})
    return Settings(
        mongodb_host=config['mongodb']['host'],
        mongodb_port=config['mongodb']['port'],
        mongodb_db=config['mongodb']['database'],
        mongodb_collection=config['mongodb']['collection'],
        spider_progress_file=config['spider']['progress_file'],
        app_name=config['app']['name'],
        app_version=config['app']['version'],
        app_description=config['app']['description'],
        jwt_secret=jwt_config.get('secret', 'your-secret-key-change-in-production'),
        jwt_algorithm=jwt_config.get('algorithm', 'HS256'),
        jwt_access_token_expire_minutes=jwt_config.get('access_token_expire_minutes', 30),
        redis_host=config.get('redis', {}).get('host', 'localhost'),
        redis_port=config.get('redis', {}).get('port', 6379),
        commission_rate=config.get('trade', {}).get('commission_rate', 0.0003),
        min_commission=config.get('trade', {}).get('min_commission', 5.0),
        transfer_rate=config.get('trade', {}).get('transfer_rate', 0.00001),
        stamp_duty_rate=config.get('trade', {}).get('stamp_duty_rate', 0.001)
    )

settings = load_config()