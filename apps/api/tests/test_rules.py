import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.rules import router, RuleCreate, RuleUpdate, BatchDelete, ConditionValidate
from app.core.auth import get_current_user

app = FastAPI()
app.include_router(router)
app.dependency_overrides[get_current_user] = lambda: MagicMock(user_id="507f1f77bcf86cd799439011", username="admin")
client = TestClient(app)

MOCK_USER_ID = "507f1f77bcf86cd799439011"


def make_rule(rule_id, name="测试规则", rtype="buy", priority=3, weight=0.5, condition="price > ma5", enabled=True):
    return {
        "_id": f"mock_{rule_id}",
        "rule_id": rule_id,
        "name": name,
        "type": rtype,
        "priority": priority,
        "weight": weight,
        "condition": condition,
        "enabled": enabled,
    }


def make_mock_db_with_rules(rules_list=None):
    mock_db = MagicMock()
    mock_db.trading_rules = MagicMock()
    mock_db.trading_rules.find.return_value = MagicMock()
    mock_db.trading_rules.find.return_value.sort.return_value = MagicMock()
    mock_db.trading_rules.find.return_value.sort.return_value.skip.return_value = MagicMock()
    mock_db.trading_rules.find.return_value.sort.return_value.skip.return_value.limit.return_value = rules_list or []
    mock_db.trading_rules.count_documents.return_value = len(rules_list or [])
    mock_db.trading_rules.find_one.return_value = None
    mock_db.trading_rules.insert_one.return_value = MagicMock(inserted_id="new_id")
    mock_db.trading_rules.update_one.return_value = MagicMock(modified_count=1)
    mock_db.trading_rules.delete_one.return_value = MagicMock(deleted_count=1)
    mock_db.trading_rules.delete_many.return_value = MagicMock(deleted_count=2)
    mock_db.rule_id_counter = MagicMock()
    mock_db.rule_id_counter.find_one_and_update.return_value = {"seq": 1}
    mock_db.rule_explore_progress = MagicMock()
    mock_db.rule_explore_progress.find_one.return_value = None
    mock_db.rule_candidates = MagicMock()
    mock_db.rule_candidates.count_documents.return_value = 0
    mock_db.rule_candidates.find.return_value = MagicMock()
    mock_db.rule_candidates.find.return_value.sort.return_value = MagicMock()
    mock_db.rule_candidates.find.return_value.sort.return_value.skip.return_value = MagicMock()
    mock_db.rule_candidates.find.return_value.sort.return_value.skip.return_value.limit.return_value = []
    mock_db.rule_blacklist = MagicMock()
    mock_db.rule_blacklist.count_documents.return_value = 0
    mock_db.rule_blacklist.find.return_value = MagicMock()
    mock_db.rule_blacklist.find.return_value.sort.return_value = MagicMock()
    mock_db.rule_blacklist.find.return_value.sort.return_value.skip.return_value = MagicMock()
    mock_db.rule_blacklist.find.return_value.sort.return_value.skip.return_value.limit.return_value = []
    mock_db.rule_backup = MagicMock()
    mock_db.rule_backup.find.return_value = MagicMock()
    mock_db.rule_backup.find.return_value.sort.return_value = MagicMock()
    mock_db.rule_backup.find.return_value.sort.return_value.limit.return_value = []
    mock_db.rule_backup.find_one.return_value = None
    mock_db.system_settings = MagicMock()
    mock_db.system_settings.find_one.return_value = {}
    return mock_db


class TestRuleCRUD:

    def test_create_rule_success(self):
        mock_db = make_mock_db_with_rules()
        mock_db.__getitem__.return_value = mock_db.trading_rules
        mock_db.trading_rules.find_one.return_value = None
        mock_db.rule_id_counter.find_one_and_update.return_value = {"seq": 99}

        def _mock_insert(doc):
            doc["_id"] = "mock_inserted_id"
            return MagicMock(inserted_id="mock_inserted_id")
        mock_db.trading_rules.insert_one.side_effect = _mock_insert

        with patch("routers.rules.get_db", return_value=mock_db), \
             patch("services.rule_service.get_db", return_value=mock_db):
            response = client.post("/rules", json={
                "name": "测试买入规则",
                "type": "buy",
                "priority": 3,
                "weight": 0.5,
                "condition": "price > ma5 and vol > ma5_vol",
                "enabled": True,
            })

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "测试买入规则"
        assert data["type"] == "buy"
        assert data["condition"] == "price > ma5 and vol > ma5_vol"
        assert data["rule_id"] == 99

    def test_create_rule_empty_condition_returns_400(self):
        mock_db = make_mock_db_with_rules()

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.post("/rules", json={
                "name": "坏规则",
                "type": "buy",
                "condition": "",
            })

        assert response.status_code == 400

    def test_create_rule_invalid_condition_returns_400(self):
        mock_db = make_mock_db_with_rules()

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.post("/rules", json={
                "name": "坏规则",
                "type": "buy",
                "condition": "import os",
            })

        assert response.status_code == 400

    def test_list_rules_returns_paginated(self):
        rules = [
            make_rule(1, "规则A", "buy", 3, 0.5, "price > ma5"),
            make_rule(2, "规则B", "sell", 2, 0.5, "price < ma10"),
        ]
        mock_db = make_mock_db_with_rules(rules)
        mock_db.__getitem__.return_value = mock_db.trading_rules
        mock_db.trading_rules.count_documents.return_value = 2

        with patch("routers.rules.get_db", return_value=mock_db), \
             patch("services.rule_service.get_db", return_value=mock_db):
            response = client.get("/rules?page=1&page_size=50")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["rules"]) == 2
        assert data["rules"][0]["name"] == "规则A"

    def test_get_rule_by_id_success(self):
        rule = make_rule(1, "找到我", "risk", 1, 1.0, "price < cost - 2*atr")
        mock_db = make_mock_db_with_rules()
        mock_db.__getitem__.return_value = mock_db.trading_rules
        mock_db.trading_rules.find_one.return_value = rule

        with patch("routers.rules.get_db", return_value=mock_db), \
             patch("services.rule_service.get_db", return_value=mock_db):
            response = client.get("/rules/1")

        assert response.status_code == 200
        data = response.json()
        assert data["rule_id"] == 1
        assert data["name"] == "找到我"

    def test_get_rule_not_found_returns_404(self):
        mock_db = make_mock_db_with_rules()
        mock_db.__getitem__.return_value = mock_db.trading_rules
        mock_db.trading_rules.find_one.return_value = None

        with patch("routers.rules.get_db", return_value=mock_db), \
             patch("services.rule_service.get_db", return_value=mock_db):
            response = client.get("/rules/99999")

        assert response.status_code == 404

    def test_update_rule_success(self):
        mock_db = make_mock_db_with_rules()
        mock_db.__getitem__.return_value = mock_db.trading_rules
        mock_db.trading_rules.find_one.return_value = make_rule(1, "旧名")
        mock_db.trading_rules.update_one.return_value = MagicMock(modified_count=1)

        with patch("routers.rules.get_db", return_value=mock_db), \
             patch("services.rule_service.get_db", return_value=mock_db):
            response = client.put("/rules/1", json={
                "name": "新名字",
                "weight": 0.8,
            })

        assert response.status_code == 200
        assert response.json()["message"] == "更新成功"

    def test_update_rule_not_found_returns_404(self):
        mock_db = make_mock_db_with_rules()
        mock_db.__getitem__.return_value = mock_db.trading_rules
        mock_db.trading_rules.update_one.return_value = MagicMock(modified_count=0)

        with patch("routers.rules.get_db", return_value=mock_db), \
             patch("services.rule_service.get_db", return_value=mock_db):
            response = client.put("/rules/99999", json={"name": "新名字"})

        assert response.status_code == 404

    def test_update_rule_invalid_condition_returns_400(self):
        mock_db = make_mock_db_with_rules()

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.put("/rules/1", json={"condition": "__import__('os')"})

        assert response.status_code == 400

    def test_delete_rule_success(self):
        mock_db = make_mock_db_with_rules()
        mock_db.__getitem__.return_value = mock_db.trading_rules
        mock_db.trading_rules.delete_one.return_value = MagicMock(deleted_count=1)

        with patch("routers.rules.get_db", return_value=mock_db), \
             patch("services.rule_service.get_db", return_value=mock_db):
            response = client.delete("/rules/1")

        assert response.status_code == 200
        assert response.json()["message"] == "删除成功"

    def test_delete_rule_not_found_returns_404(self):
        mock_db = make_mock_db_with_rules()
        mock_db.__getitem__.return_value = mock_db.trading_rules
        mock_db.trading_rules.delete_one.return_value = MagicMock(deleted_count=0)

        with patch("routers.rules.get_db", return_value=mock_db), \
             patch("services.rule_service.get_db", return_value=mock_db):
            response = client.delete("/rules/99999")

        assert response.status_code == 404

    def test_batch_delete_success(self):
        mock_db = make_mock_db_with_rules()
        mock_db.__getitem__.return_value = mock_db.trading_rules
        mock_db.trading_rules.delete_many.return_value = MagicMock(deleted_count=3)

        with patch("routers.rules.get_db", return_value=mock_db), \
             patch("services.rule_service.get_db", return_value=mock_db):
            response = client.post("/rules/batch-delete", json={"rule_ids": [1, 2, 3]})

        assert response.status_code == 200
        assert "已删除 3" in response.json()["message"]

    def test_batch_delete_empty_returns_400(self):
        mock_db = make_mock_db_with_rules()

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.post("/rules/batch-delete", json={"rule_ids": []})

        assert response.status_code == 400
        assert "不能为空" in response.text


class TestValidateCondition:

    def test_validate_valid_condition(self):
        mock_db = make_mock_db_with_rules()

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.post("/rules/validate", json={
                "condition": "price > ma5 and vol > ma5_vol"
            })

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert "message" in data
        assert data["result"] is not None
        assert data["message"] == "条件合法"

    def test_validate_invalid_condition(self):
        mock_db = make_mock_db_with_rules()

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.post("/rules/validate", json={
                "condition": "os.system('rm -rf /')"
            })

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "message" in data

    def test_validate_syntax_error(self):
        mock_db = make_mock_db_with_rules()

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.post("/rules/validate", json={
                "condition": "price > > ma5"
            })

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "message" in data

    def test_validate_forbidden_name(self):
        mock_db = make_mock_db_with_rules()

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.post("/rules/validate", json={
                "condition": "eval('1+1')"
            })

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False


class TestExploreAndCandidates:

    def test_get_explore_status_idle(self):
        mock_db = make_mock_db_with_rules()
        mock_db.rule_explore_progress.find_one.return_value = None

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.get("/rules/explore/status")

        assert response.status_code == 200
        assert response.json()["status"] == "idle"

    def test_start_explore_without_llm_key(self):
        mock_db = make_mock_db_with_rules()
        mock_db.rule_explore_progress.find_one.return_value = None

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.post("/rules/explore", json={
                "phases": ["template", "llm", "genetic"]
            })

        assert response.status_code == 400
        assert "LLM" in response.text

    def test_list_candidates_empty(self):
        mock_db = make_mock_db_with_rules()
        mock_db.rule_candidates.find.return_value.sort.return_value.skip.return_value.limit.return_value = []
        mock_db.rule_candidates.count_documents.return_value = 0

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.get("/rules/candidates")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["candidates"] == []

    def test_delete_nonexistent_candidate_returns_404(self):
        mock_db = make_mock_db_with_rules()
        mock_db.rule_candidates.delete_one.return_value = MagicMock(deleted_count=0)

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.delete("/rules/candidates/507f1f77bcf86cd799439099")

        assert response.status_code == 404

    def test_candidate_backtest_query_param_returns_trades(self):
        mock_db = make_mock_db_with_rules()
        cand = {
            "_id": "507f1f77bcf86cd799439011",
            "key": "ma10≤ma20*2.0orprice≥high*1.8|ma5<ma20*2.0|p",
            "backtest_result": {
                "trades": [{"code": "000001", "pnl_pct": 5.2}],
                "sharpe": 1.96,
                "portfolio_return": -3.4,
                "win_rate": 60.0,
            },
        }
        mock_db.rule_candidates.find_one.return_value = cand

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.get(
                "/rules/candidates/backtest",
                params={"id": "507f1f77bcf86cd799439011"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["trades"]) == 1
        assert data["sharpe"] == 1.96
        mock_db.rule_candidates.find_one.assert_called_once()

    def test_candidate_backtest_not_found_returns_404(self):
        mock_db = make_mock_db_with_rules()
        mock_db.rule_candidates.find_one.return_value = None

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.get(
                "/rules/candidates/backtest",
                params={"id": "507f1f77bcf86cd799439099"},
            )

        assert response.status_code == 404
        assert "规则不存在" in response.text

    def test_candidate_backtest_invalid_id_returns_404(self):
        mock_db = make_mock_db_with_rules()

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.get(
                "/rules/candidates/backtest",
                params={"id": "not-an-objectid"},
            )

        assert response.status_code == 404
        assert "规则不存在" in response.text


class TestBlacklist:

    def test_list_blacklist_empty(self):
        mock_db = make_mock_db_with_rules()

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.get("/rules/blacklist")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    def test_delete_nonexistent_blacklist_returns_404(self):
        mock_db = make_mock_db_with_rules()
        mock_db.rule_blacklist.delete_one.return_value = MagicMock(deleted_count=0)

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.delete("/rules/blacklist/507f1f77bcf86cd799439099")

        assert response.status_code == 404


class TestOptimizedCandidates:
    def test_list_optimized_candidates_empty(self):
        mock_db = make_mock_db_with_rules()
        mock_db.rule_candidates_optimized = MagicMock()
        mock_db.rule_candidates_optimized.find.return_value.sort.return_value.skip.return_value.limit.return_value = []
        mock_db.rule_candidates_optimized.count_documents.return_value = 0

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.get("/rules/optimized-candidates")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["candidates"] == []

    def test_start_optimize_without_llm_key(self):
        mock_db = make_mock_db_with_rules()
        mock_db.rule_explore_progress.find_one.return_value = None
        mock_db.system_settings.find_one.return_value = {}

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.post("/rules/optimize-candidates", json={"scope": "all", "limit": 100})

        assert response.status_code == 400
        assert "LLM" in response.text

    def test_start_optimize_with_llm_key(self):
        mock_db = make_mock_db_with_rules()
        mock_db.rule_explore_progress.find_one.return_value = None
        mock_db.system_settings.find_one.return_value = {"llm_api_key": "sk-test"}

        from tasks.rule_explore_tasks import run_rule_optimization
        fake_task = MagicMock()
        fake_task.delay.return_value = MagicMock(id="task-123")
        with patch("routers.rules.run_rule_optimization", fake_task), \
             patch("routers.rules.get_db", return_value=mock_db):
            response = client.post("/rules/optimize-candidates", json={"scope": "all", "limit": 100})

        assert response.status_code == 200
        assert response.json()["task_id"] == "task-123"

    def test_delete_optimized_candidate_404(self):
        mock_db = make_mock_db_with_rules()
        mock_db.rule_candidates_optimized = MagicMock()
        mock_db.rule_candidates_optimized.delete_one.return_value = MagicMock(deleted_count=0)

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.delete("/rules/optimized-candidates/507f1f77bcf86cd799439099")

        assert response.status_code == 404

    def test_apply_optimized_candidate_404(self):
        mock_db = make_mock_db_with_rules()
        mock_db.rule_candidates_optimized = MagicMock()
        mock_db.rule_candidates_optimized.find_one.return_value = None

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.post("/rules/optimized-candidates/507f1f77bcf86cd799439099/apply")

        assert response.status_code == 404

    def test_clear_optimized_candidates(self):
        mock_db = make_mock_db_with_rules()
        mock_db.rule_candidates_optimized = MagicMock()
        mock_db.rule_candidates_optimized.delete_many.return_value = MagicMock(deleted_count=3)

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.delete("/rules/optimized-candidates")

        assert response.status_code == 200
        assert "3" in response.json()["message"]

    def test_list_optimized_candidates_filters(self):
        mock_db = make_mock_db_with_rules()
        mock_db.rule_candidates_optimized = MagicMock()
        mock_db.rule_candidates_optimized.find.return_value.sort.return_value.skip.return_value.limit.return_value = []
        mock_db.rule_candidates_optimized.count_documents.return_value = 2

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.get(
                "/rules/optimized-candidates",
                params={"validated": "true", "parent_source": "template"},
            )

        assert response.status_code == 200
        assert response.json()["total"] == 2
        call_args = mock_db.rule_candidates_optimized.count_documents.call_args
        assert call_args[0][0] == {"validated": True, "parent_source": "template"}

    def test_start_optimized_validate_starts_task(self):
        mock_db = make_mock_db_with_rules()
        mock_db.rule_explore_progress.find_one.return_value = None

        from tasks.rule_explore_tasks import run_rule_validation
        fake_task = MagicMock()
        fake_task.delay.return_value = MagicMock(id="task-opt-validate")
        with patch("routers.rules.run_rule_validation", fake_task), \
             patch("routers.rules.get_db", return_value=mock_db):
            response = client.post(
                "/rules/optimized-candidates/validate",
                json={"scope": "all", "limit": 100, "backtest_days": 180},
            )

        assert response.status_code == 200
        assert response.json()["task_id"] == "task-opt-validate"
        args, kwargs = fake_task.delay.call_args
        assert args[0] == "all"
        assert args[2] == 180
        assert kwargs["target"] == "optimized"

    def test_start_optimized_validate_conflict_when_running(self):
        mock_db = make_mock_db_with_rules()
        mock_db.rule_explore_progress.find_one.return_value = {"status": "running", "updated_at": None}

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.post("/rules/optimized-candidates/validate", json={})

        assert response.status_code == 409

    def test_optimized_candidate_backtest_returns_trades(self):
        mock_db = make_mock_db_with_rules()
        cand = {
            "_id": "507f1f77bcf86cd799439011",
            "key": "opt-key-1",
            "backtest_result": {
                "trades": [{"code": "600519", "pnl_pct": 8.8}],
                "sharpe": 2.11,
                "portfolio_return": 15.2,
                "win_rate": 66.7,
            },
        }
        mock_db.rule_candidates_optimized = MagicMock()
        mock_db.rule_candidates_optimized.find_one.return_value = cand

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.get(
                "/rules/optimized-candidates/backtest",
                params={"id": "507f1f77bcf86cd799439011"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["trades"]) == 1
        assert data["sharpe"] == 2.11
        assert data["portfolio_return"] == 15.2
        mock_db.rule_candidates_optimized.find_one.assert_called_once()

    def test_optimized_candidate_backtest_not_found_returns_404(self):
        mock_db = make_mock_db_with_rules()
        mock_db.rule_candidates_optimized = MagicMock()
        mock_db.rule_candidates_optimized.find_one.return_value = None

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.get(
                "/rules/optimized-candidates/backtest",
                params={"id": "507f1f77bcf86cd799439099"},
            )

        assert response.status_code == 404
        assert "规则不存在" in response.text


class TestOptimizeServiceFunctions:
    def test_try_insert_optimized_writes_doc(self):
        from services.rule_explorer import try_insert_optimized

        mock_db = make_mock_db_with_rules()
        mock_db.rule_candidates_optimized = MagicMock()
        mock_db.rule_candidates_optimized.find_one.return_value = None
        mock_db.rule_blacklist.find_one.return_value = None
        inserted = MagicMock()
        mock_db.rule_candidates_optimized.insert_one.return_value = inserted

        parent = {
            "key": "parent-key-1", "source": "template", "name": "模板_0001",
            "buy_condition": "price > ma20", "sell_condition": "price < ma10",
            "risk_condition": "price < cost * 0.9", "priority": 3, "weight": 0.35,
        }
        optimized = {
            "name": "优化版", "buy_condition": "price > ma20 and vol > ma5_vol",
            "sell_condition": "price < ma10", "risk_condition": "price < cost * 0.92",
            "optimization_note": "加强量价",
        }

        with patch("services.rule_explorer.get_db", return_value=mock_db):
            ok = try_insert_optimized(optimized, parent)

        assert ok is True
        inserted_doc = mock_db.rule_candidates_optimized.insert_one.call_args[0][0]
        assert inserted_doc["source"] == "llm_evolve"
        assert inserted_doc["parent_key"] == "parent-key-1"
        assert inserted_doc["optimization_note"] == "加强量价"

    def test_try_insert_optimized_invalid_conditions(self):
        from services.rule_explorer import try_insert_optimized

        mock_db = make_mock_db_with_rules()
        mock_db.rule_candidates_optimized = MagicMock()
        mock_db.rule_candidates_optimized.find_one.return_value = None
        mock_db.rule_blacklist.find_one.return_value = None

        parent = {
            "key": "p1", "source": "template", "name": "t",
            "buy_condition": "price > ma20", "sell_condition": "price < ma10",
            "risk_condition": "price < cost * 0.9",
        }
        optimized = {
            "name": "bad", "buy_condition": "price > ma20",
            "sell_condition": "import os", "risk_condition": "price < cost * 0.9",
        }

        with patch("services.rule_explorer.get_db", return_value=mock_db):
            ok = try_insert_optimized(optimized, parent)

        assert ok is False
        mock_db.rule_candidates_optimized.insert_one.assert_not_called()

    def test_optimize_candidates_with_llm_requires_key(self):
        from services.rule_explorer import optimize_candidates_with_llm

        mock_db = make_mock_db_with_rules()
        mock_db.system_settings.find_one.return_value = {}

        with patch("services.rule_explorer.get_db", return_value=mock_db), pytest.raises(ValueError):
            optimize_candidates_with_llm()

    def test_optimize_candidates_skips_existing(self):
        from services.rule_explorer import optimize_candidates_with_llm

        mock_db = make_mock_db_with_rules()
        mock_db.system_settings.find_one.return_value = {"llm_api_key": "sk-test"}
        mock_db.rule_candidates_optimized = MagicMock()
        mock_db.rule_candidates_optimized.find.return_value = [
            {"parent_key": "parent-key-1"},
        ]
        cand = {
            "key": "parent-key-1", "name": "模板_0001", "source": "template",
            "buy_condition": "price > ma20", "sell_condition": "price < ma10",
            "risk_condition": "price < cost * 0.9", "priority": 3, "weight": 0.35,
        }
        mock_db.rule_candidates.find.return_value = [cand]

        with patch("services.rule_explorer.get_db", return_value=mock_db), \
             patch("services.rule_explorer._call_llm_optimize") as mock_llm:
            mock_llm.return_value = {"buy_condition": "price > ma20"}
            count = optimize_candidates_with_llm(limit=500)

        assert count == 0
        mock_llm.assert_not_called()


class TestBackupAndRestore:
    def test_list_backups_empty(self):
        mock_db = make_mock_db_with_rules()

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.get("/rules/backup")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["backups"], list)

    def test_restore_nonexistent_backup_returns_404(self):
        mock_db = make_mock_db_with_rules()
        mock_db.rule_backup.find_one.return_value = None

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.post("/rules/backup/507f1f77bcf86cd799439099/restore")

        assert response.status_code == 404

    def test_restore_backup_success(self):
        mock_db = make_mock_db_with_rules()
        mock_db.rule_backup.find_one.return_value = {
            "_id": MagicMock(),
            "rules": [
                {"rule_id": 1, "name": "恢复规则A", "type": "buy", "condition": "price > ma5", "priority": 3, "weight": 0.5, "enabled": True},
            ]
        }
        mock_db.trading_rules.count_documents.return_value = 0

        with patch("routers.rules.get_db", return_value=mock_db):
            response = client.post("/rules/backup/507f1f77bcf86cd799439099/restore")

        assert response.status_code == 200
        assert "已恢复" in response.json()["message"]