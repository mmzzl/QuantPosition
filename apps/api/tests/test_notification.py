import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock
import requests

from services.notification_service import send_dingtalk_message, send_alert, get_webhook_config


class TestGetWebhookConfig:

    def test_returns_empty_defaults(self):
        mock_db = MagicMock()
        mock_db.system_settings.find_one.return_value = None
        with patch("services.notification_service.get_db", return_value=mock_db):
            config = get_webhook_config()
        assert config["dingtalk_webhook"] == ""
        assert config["dingtalk_secret"] == ""

    def test_returns_configured_values(self):
        mock_db = MagicMock()
        mock_db.system_settings.find_one.return_value = {
            "_id": "global",
            "dingtalk_webhook": "https://oapi.dingtalk.com/robot/send?access_token=abc",
            "dingtalk_secret": "SEC123",
        }
        with patch("services.notification_service.get_db", return_value=mock_db):
            config = get_webhook_config()
        assert config["dingtalk_webhook"] == "https://oapi.dingtalk.com/robot/send?access_token=abc"
        assert config["dingtalk_secret"] == "SEC123"


class TestSendDingtalkMessage:

    def test_returns_false_when_webhook_empty(self):
        mock_db = MagicMock()
        mock_db.system_settings.find_one.return_value = {
            "_id": "global",
            "dingtalk_webhook": "",
            "dingtalk_secret": "",
        }
        with patch("services.notification_service.get_db", return_value=mock_db):
            result = send_dingtalk_message("test", "content")
        assert result is False

    def test_returns_true_on_success(self):
        mock_db = MagicMock()
        mock_db.system_settings.find_one.return_value = {
            "_id": "global",
            "dingtalk_webhook": "https://oapi.dingtalk.com/robot/send",
            "dingtalk_secret": "",
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errcode": 0}
        with patch("services.notification_service.get_db", return_value=mock_db):
            with patch("services.notification_service.requests.post", return_value=mock_resp):
                result = send_dingtalk_message("test", "content")
        assert result is True

    def test_returns_false_on_dingtalk_error(self):
        mock_db = MagicMock()
        mock_db.system_settings.find_one.return_value = {
            "_id": "global",
            "dingtalk_webhook": "https://oapi.dingtalk.com/robot/send",
            "dingtalk_secret": "",
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errcode": 1}
        with patch("services.notification_service.get_db", return_value=mock_db):
            with patch("services.notification_service.requests.post", return_value=mock_resp):
                result = send_dingtalk_message("test", "content")
        assert result is False

    def test_returns_false_on_timeout(self):
        mock_db = MagicMock()
        mock_db.system_settings.find_one.return_value = {
            "_id": "global",
            "dingtalk_webhook": "https://oapi.dingtalk.com/robot/send",
            "dingtalk_secret": "",
        }
        with patch("services.notification_service.get_db", return_value=mock_db):
            with patch("services.notification_service.requests.post", side_effect=requests.exceptions.Timeout):
                result = send_dingtalk_message("test", "content")
        assert result is False

    def test_signs_payload_with_hmac_sha256(self):
        mock_db = MagicMock()
        mock_db.system_settings.find_one.return_value = {
            "_id": "global",
            "dingtalk_webhook": "https://oapi.dingtalk.com/robot/send",
            "dingtalk_secret": "mysecret",
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errcode": 0}
        with patch("services.notification_service.get_db", return_value=mock_db):
            with patch("services.notification_service.requests.post", return_value=mock_resp) as mock_post:
                with patch("services.notification_service.time.time", return_value=1712345678.0):
                    send_dingtalk_message("test", "content")
        url = mock_post.call_args[0][0]
        assert "timestamp=" in url
        assert "sign=" in url

    def test_truncates_long_content(self):
        mock_db = MagicMock()
        mock_db.system_settings.find_one.return_value = {
            "_id": "global",
            "dingtalk_webhook": "https://oapi.dingtalk.com/robot/send",
            "dingtalk_secret": "",
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errcode": 0}
        with patch("services.notification_service.get_db", return_value=mock_db):
            with patch("services.notification_service.requests.post", return_value=mock_resp) as mock_post:
                send_dingtalk_message("test", "x" * 20000)
        payload = mock_post.call_args[1]["json"]
        text = payload["markdown"]["text"]
        assert text.endswith("...(内容过长已截断)")

    def test_returns_false_on_requests_exception(self):
        mock_db = MagicMock()
        mock_db.system_settings.find_one.return_value = {
            "_id": "global",
            "dingtalk_webhook": "https://oapi.dingtalk.com/robot/send",
            "dingtalk_secret": "",
        }
        with patch("services.notification_service.get_db", return_value=mock_db):
            with patch("services.notification_service.requests.post", side_effect=Exception("boom")):
                result = send_dingtalk_message("test", "content")
        assert result is False


class TestSendAlert:

    def test_sends_alert_with_rule_id_and_code(self):
        mock_db = MagicMock()
        mock_db.system_settings.find_one.return_value = {
            "_id": "global",
            "dingtalk_webhook": "https://oapi.dingtalk.com/robot/send",
            "dingtalk_secret": "",
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errcode": 0}
        with patch("services.notification_service.get_db", return_value=mock_db):
            with patch("services.notification_service.requests.post", return_value=mock_resp) as mock_post:
                result = send_alert("RULE001", "000001", "股票触发卖出信号")
        assert result is True
        payload = mock_post.call_args[1]["json"]
        assert payload["msgtype"] == "markdown"
        assert "RULE001" in payload["markdown"]["title"]
        assert "000001" in payload["markdown"]["text"]
        assert "卖出信号" in payload["markdown"]["text"]

    def test_send_alert_returns_false_when_webhook_not_configured(self):
        mock_db = MagicMock()
        mock_db.system_settings.find_one.return_value = {
            "_id": "global",
            "dingtalk_webhook": "",
            "dingtalk_secret": "",
        }
        with patch("services.notification_service.get_db", return_value=mock_db):
            result = send_alert("RULE001", "000001", "test message")
        assert result is False