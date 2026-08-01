import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import requests
from unittest.mock import patch, MagicMock


class TestNotificationE2E:

    def test_webhook_from_api_persists_and_notification_reads_it(self, api_url: str, auth_header: dict):
        from services.notification_service import send_dingtalk_message

        resp = requests.put(f"{api_url}/settings", json={
            "dingtalk_webhook": "https://oapi.dingtalk.com/robot/send?access_token=e2e-test",
            "dingtalk_secret": "",
        }, headers=auth_header, timeout=10)
        assert resp.status_code == 200

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errcode": 0}
        with patch("bin.rule_engine.requests.post", return_value=mock_resp):
            result = send_dingtalk_message("E2E Test", "Hello from E2E test")
        assert result is True

    def test_disabled_webhook_returns_false(self, api_url: str, auth_header: dict):
        from services.notification_service import send_dingtalk_message

        requests.put(f"{api_url}/settings", json={
            "dingtalk_webhook": "",
        }, headers=auth_header, timeout=10)

        result = send_dingtalk_message("E2E Test", "Should not send")
        assert result is False

    def test_secret_signing_from_db_settings(self, api_url: str, auth_header: dict):
        from services.notification_service import send_dingtalk_message

        requests.put(f"{api_url}/settings", json={
            "dingtalk_webhook": "https://oapi.dingtalk.com/robot/send?access_token=e2e-sign",
            "dingtalk_secret": "e2e-secret",
        }, headers=auth_header, timeout=10)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errcode": 0}
        with patch("bin.rule_engine.requests.post", return_value=mock_resp) as mock_post:
            with patch("bin.rule_engine.time.time", return_value=1712345678.0):
                result = send_dingtalk_message("E2E", "Test signing")
        assert result is True
        url = mock_post.call_args[0][0]
        assert "timestamp=1712345678" in url
        assert "sign=" in url
