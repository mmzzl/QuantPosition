import os
import yaml
from config.config import Settings


def load_config(config_file: str = "config.yaml") -> Settings:
    config_file = os.environ.get("CONFIG_FILE", config_file)
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_file)

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    jwt_config = config.get("jwt", {})
    jwt_secret = jwt_config.get("secret")
    if not jwt_secret or jwt_secret == "your-secret-key-change-in-production":
        raise ValueError("JWT secret 未配置，请在 config.yaml 中设置 jwt.secret")

    return Settings(
        mongodb_host=config["mongodb"]["host"],
        mongodb_port=config["mongodb"]["port"],
        mongodb_db=config["mongodb"]["database"],
        mongodb_collection=config["mongodb"]["collection"],
        spider_progress_file=config["spider"]["progress_file"],
        app_name=config["app"]["name"],
        app_version=config["app"]["version"],
        app_description=config["app"]["description"],
        jwt_secret=jwt_secret,
        jwt_algorithm=jwt_config.get("algorithm", "HS256"),
        jwt_access_token_expire_minutes=jwt_config.get("access_token_expire_minutes", 30),
        redis_host=config.get("redis", {}).get("host", "localhost"),
        redis_port=config.get("redis", {}).get("port", 6379),
        commission_rate=config.get("trade", {}).get("commission_rate", 0.0003),
        min_commission=config.get("trade", {}).get("min_commission", 5.0),
        transfer_rate=config.get("trade", {}).get("transfer_rate", 0.00001),
        stamp_duty_rate=config.get("trade", {}).get("stamp_duty_rate", 0.001),
    )


settings = load_config()
