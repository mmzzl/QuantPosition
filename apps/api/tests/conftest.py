import sys
import os
import pytest
from typing import Generator
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="session")
def test_client() -> Generator[TestClient, None, None]:
    from app.app_factory import create_app
    app = create_app(title="TestApp", version="0.1.0", description="Test", log_level="DEBUG")
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="session")
def test_settings():
    from config.config import Settings
    return Settings(
        mongodb_host="localhost",
        mongodb_port=27017,
        mongodb_db="test_db",
        mongodb_collection="test",
        spider_progress_file="test_progress.json",
        app_name="TestApp",
        app_version="1.0",
        app_description="Test",
        jwt_secret="test-secret-key-not-default-2026",
        jwt_algorithm="HS256",
        jwt_access_token_expire_minutes=30,
        redis_host="localhost",
        redis_port=6379,
    )


@pytest.fixture(scope="function")
def auth_headers(test_client: TestClient) -> dict[str, str]:
    return {"Authorization": "Bearer test_token"}
