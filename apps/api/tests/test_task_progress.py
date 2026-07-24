import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock


class TestTaskProgress:
    def test_get_progress_returns_pending_when_not_found(self):
        with patch("database.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.__getitem__.return_value.find_one.return_value = None
            mock_get_db.return_value = mock_db

            from services.task_progress import get_progress

            result = get_progress("nonexistent-id")
            assert result["status"] == "PENDING"
            assert result["current"] == 0
            assert result["total"] == 0

    def test_get_progress_returns_doc(self):
        with patch("database.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.__getitem__.return_value.find_one.return_value = {
                "_id": "task-1",
                "current": 50,
                "total": 100,
                "status": "RUNNING",
            }
            mock_get_db.return_value = mock_db

            from services.task_progress import get_progress

            result = get_progress("task-1")
            assert result["status"] == "RUNNING"
            assert result["current"] == 50
            assert result["total"] == 100

    def test_update_progress_writes_to_db(self):
        with patch("database.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            from services.task_progress import update_progress

            update_progress("task-1", current=10, total=100, status="RUNNING")
            mock_db.__getitem__.return_value.update_one.assert_called_once()
