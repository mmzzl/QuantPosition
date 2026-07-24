import sys
import os
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import copy
import yaml
import pytest
from config.config import load_config, Settings


DEFAULT_CONFIG = {
    "mongodb": {"host": "127.0.0.1", "port": 27017, "database": "test_db", "collection": "test"},
    "spider": {"progress_file": "test_progress.json"},
    "app": {"name": "TestApp", "version": "1.0", "description": "Test"},
    "jwt": {"secret": "test-secret-key-not-default-2026", "algorithm": "HS256", "access_token_expire_minutes": 30},
    "trade": {
        "commission_rate": 0.0003, "min_commission": 5.0,
        "transfer_rate": 0.00001, "stamp_duty_rate": 0.001,
    },
}


def _write_config(data, path):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)


class TestLoadConfig:

    def test_loads_full_config(self):
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False, encoding="utf-8") as f:
            yaml.dump(DEFAULT_CONFIG, f)
            config_path = f.name
        try:
            os.environ["CONFIG_FILE"] = config_path
            settings = load_config(config_path)
            assert isinstance(settings, Settings)
            assert settings.mongodb_host == "127.0.0.1"
            assert settings.mongodb_port == 27017
            assert settings.app_name == "TestApp"
            assert settings.jwt_secret == "test-secret-key-not-default-2026"
            assert settings.commission_rate == 0.0003
        finally:
            os.unlink(config_path)
            os.environ.pop("CONFIG_FILE", None)

    def test_rejects_default_jwt_secret(self):
        config = copy.deepcopy(DEFAULT_CONFIG)
        config["jwt"]["secret"] = "your-secret-key-change-in-production"
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False, encoding="utf-8") as f:
            yaml.dump(config, f)
            config_path = f.name
        try:
            with pytest.raises(ValueError, match="JWT secret"):
                load_config(config_path)
        finally:
            os.unlink(config_path)

    def test_rejects_empty_jwt_secret(self):
        config = copy.deepcopy(DEFAULT_CONFIG)
        config["jwt"]["secret"] = ""
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False, encoding="utf-8") as f:
            yaml.dump(config, f)
            config_path = f.name
        try:
            with pytest.raises(ValueError, match="JWT secret"):
                load_config(config_path)
        finally:
            os.unlink(config_path)

    def test_missing_file_raises_error(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path/config.yaml")

    def test_supports_env_var_override(self):
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False, encoding="utf-8") as f:
            yaml.dump(DEFAULT_CONFIG, f)
            config_path = f.name
        try:
            os.environ["CONFIG_FILE"] = config_path
            s = load_config()
            assert s.app_name == "TestApp"
        finally:
            os.unlink(config_path)
            os.environ.pop("CONFIG_FILE", None)


class TestSettingsModel:

    def test_extra_fields_forbidden(self):
        with pytest.raises(Exception):
            Settings(
                mongodb_host="localhost", mongodb_port=27017, mongodb_db="db", mongodb_collection="c",
                spider_progress_file="p.json",
                app_name="x", app_version="1", app_description="d",
                jwt_secret="s", unknown_field="should_fail"
            )
