# -*- coding: utf-8 -*-
import hashlib
import hmac
import base64
import time
import logging
import json as _json
from typing import Dict, Optional
from urllib.parse import quote

import requests

from database import get_db

logger = logging.getLogger(__name__)

MAX_PAYLOAD_BYTES = 19000
TRUNCATION_SUFFIX = "\n\n...(内容过长已截断)"


def get_webhook_config() -> dict:
    db = get_db()
    settings = db.system_settings.find_one({"_id": "global"}) or {}
    return {
        "dingtalk_webhook": settings.get("dingtalk_webhook", ""),
        "dingtalk_secret": settings.get("dingtalk_secret", ""),
    }


def send_dingtalk_message(title: str, content: str) -> bool:
    try:
        config = get_webhook_config()
        webhook = config["dingtalk_webhook"]
        secret = config["dingtalk_secret"]

        if not webhook:
            logger.warning("钉钉 webhook 未配置")
            return False

        logger.info(f"钉钉 webhook URL: {webhook[:60]}... (长度: {len(webhook)})")

        timestamp = str(round(time.time() * 1000))
        if secret:
            sign_str = f"{timestamp}\n{secret}"
            sign = base64.b64encode(
                hmac.new(secret.encode("utf-8"), sign_str.encode("utf-8"), hashlib.sha256).digest()
            ).decode("utf-8")
            webhook += f"&timestamp={timestamp}&sign={quote(sign)}"

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": f"## {title}\n\n{content}"
            }
        }
        body_size = len(_json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        logger.info(f"钉钉推送 payload 大小: {body_size} bytes")
        if body_size > MAX_PAYLOAD_BYTES:
            logger.warning(f"payload 过大 ({body_size} bytes)，截断内容")
            payload["markdown"]["text"] = payload["markdown"]["text"][:18000] + TRUNCATION_SUFFIX

        resp = requests.post(webhook, json=payload, timeout=5)
        result = resp.json()
        logger.info(f"钉钉推送结果: {result}")
        return result.get("errcode") == 0
    except Exception as e:
        logger.error(f"钉钉推送失败: {e}")
        return False


def send_alert(rule_id: str, code: str, message: str) -> bool:
    title = f"规则告警: {rule_id}"
    content = f"**股票代码**: {code}\n\n**告警详情**: {message}"
    return send_dingtalk_message(title, content)