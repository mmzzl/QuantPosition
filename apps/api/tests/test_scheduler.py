import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import MagicMock
from scheduler.scheduler import IntervalTask, CronTask, DateTask, tasks_load_from_inputs
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger


class TestIntervalTask:

    def test_parses_30s(self):
        task = IntervalTask("test.py", "30s")
        assert task.isok is True
        assert task.trigger.interval.seconds == 30
        assert isinstance(task.trigger, IntervalTrigger)

    def test_parses_5m(self):
        task = IntervalTask("test.py", "5m")
        assert task.isok is True
        assert task.trigger.interval.seconds == 300
        assert isinstance(task.trigger, IntervalTrigger)

    def test_parses_2h(self):
        task = IntervalTask("test.py", "2h")
        assert task.isok is True
        assert task.trigger.interval.seconds == 7200
        assert isinstance(task.trigger, IntervalTrigger)

    def test_parses_7d(self):
        task = IntervalTask("test.py", "7d")
        assert task.isok is True
        assert task.trigger.interval.days == 7
        assert isinstance(task.trigger, IntervalTrigger)

    def test_parses_2w(self):
        task = IntervalTask("test.py", "2w")
        assert task.isok is True
        assert task.trigger.interval.days == 14
        assert isinstance(task.trigger, IntervalTrigger)

    def test_invalid_format(self):
        task = IntervalTask("test.py", "invalid")
        assert task.isok is False

    def test_invalid_unit(self):
        task = IntervalTask("test.py", "5x")
        assert task.isok is False

    def test_jitter_is_10(self):
        task = IntervalTask("test.py", "30s")
        assert task.trigger.jitter == 10
        task2 = IntervalTask("test.py", "5m")
        assert task2.trigger.jitter == 10
        task3 = IntervalTask("test.py", "7d")
        assert task3.trigger.jitter == 10


class TestCronTask:

    def test_parses_hour_minute(self):
        task = CronTask("test.py", "hour=9,minute=20")
        assert task.isok is True
        assert isinstance(task.trigger, CronTrigger)

    def test_parses_with_day_of_week(self):
        task = CronTask("test.py", "hour=15,minute=10,day_of_week=3")
        assert task.isok is True
        assert isinstance(task.trigger, CronTrigger)

    def test_empty_cron(self):
        task = CronTask("test.py", "")
        assert task.isok is False


class TestDateTask:

    def test_parses_datetime_string(self):
        task = DateTask("test.py", "2026-07-22 15:00:00")
        assert task.isok is True
        assert isinstance(task.trigger, DateTrigger)


class TestTaskLoading:

    def test_loads_interval_task(self):
        mock_inputs = MagicMock()
        mock_inputs.config = {
            "script://bin/test.py": {"enable": "true", "interval": "30s"}
        }
        tasks = tasks_load_from_inputs(mock_inputs)
        assert len(tasks) == 1
        assert isinstance(tasks[0], IntervalTask)

    def test_loads_cron_task(self):
        mock_inputs = MagicMock()
        mock_inputs.config = {
            "script://bin/test.py": {"enable": "true", "cron": "hour=9,minute=20"}
        }
        tasks = tasks_load_from_inputs(mock_inputs)
        assert len(tasks) == 1
        assert isinstance(tasks[0], CronTask)

    def test_skips_disabled_task(self):
        mock_inputs = MagicMock()
        mock_inputs.config = {
            "script://bin/test.py": {"enable": "false", "interval": "30s"}
        }
        tasks = tasks_load_from_inputs(mock_inputs)
        assert len(tasks) == 0

    def test_creates_task_on_missing_enable(self):
        mock_inputs = MagicMock()
        mock_inputs.config = {
            "script://bin/test.py": {"interval": "30s"}
        }
        tasks = tasks_load_from_inputs(mock_inputs)
        assert len(tasks) == 1
        assert isinstance(tasks[0], IntervalTask)


from unittest.mock import patch, MagicMock


class TestSchedulerManager:

    def test_scheduler_start_and_shutdown(self):
        from scheduler.scheduler import SchedulerManager

        mgr = SchedulerManager()
        mock_scheduler = MagicMock()
        mgr._scheduler = mock_scheduler

        mock_scheduler.running = False
        mgr.start()
        mock_scheduler.start.assert_called_once()

        mock_scheduler.running = True
        mgr.shutdown()
        mock_scheduler.shutdown.assert_called_once()

    def test_add_task_to_scheduler(self):
        from scheduler.scheduler import IntervalTask, SchedulerManager

        task = IntervalTask("bin/test.py", "30s")
        assert task.isok

        mgr = SchedulerManager()
        mock_scheduler = MagicMock()
        mgr._scheduler = mock_scheduler

        mgr.add_task(task)
        mock_scheduler.add_job.assert_called_once()
        args, kwargs = mock_scheduler.add_job.call_args
        assert "trigger" in kwargs
        assert kwargs["trigger"].interval.seconds == 30


class TestScriptSingle:

    def test_lock_acquired_when_no_existing_lock(self):
        with patch("systems.single.flock_exclusive", return_value=(MagicMock(), None)):
            from systems.single import ScriptSingle
            ss = ScriptSingle("/tmp/test.pid")
            assert ss.is_running() is False

    def test_lock_fails_when_process_running(self):
        with patch("systems.single.flock_exclusive", return_value=(None, 'locked')):
            from systems.single import ScriptSingle
            ss = ScriptSingle("/tmp/test.pid")
            assert ss.is_running() is True


class TestCeleryRegistration:

    def test_celery_app_imports_task_modules(self):
        from celery_config import _TASK_MODULES, celery_app
        assert len(_TASK_MODULES) == 7
        for m in ("selection_tasks", "news_selection_tasks", "heatmap_selection_tasks",
                  "kline_tasks", "indicator_tasks", "backtest_tasks", "rule_explore_tasks"):
            assert m in _TASK_MODULES
        assert celery_app.conf.task_serializer == "json"

    def test_celery_broker_is_redis(self):
        from celery_config import celery_app
        assert "redis" in celery_app.conf.broker_url

    def test_celery_task_created(self):
        from celery_config import celery_app
        from tasks.kline_tasks import update_kline_data
        assert update_kline_data.name == "tasks.kline.update"

    def test_all_task_names_match_contract(self):
        from tasks.selection_tasks import run_dual_ma_selection
        from tasks.news_selection_tasks import run_news_selection
        from tasks.heatmap_selection_tasks import run_heatmap_selection
        from tasks.kline_tasks import update_kline_data
        from tasks.indicator_tasks import update_indicators, backfill_indicators
        from tasks.backtest_tasks import run_simple_backtest
        from tasks.rule_explore_tasks import run_rule_exploration, run_rule_validation

        assert run_dual_ma_selection.name == "tasks.selection.run_dual_ma_selection"
        assert run_news_selection.name == "tasks.news_selection.run_news_selection"
        assert run_heatmap_selection.name == "tasks.heatmap_selection.run_heatmap_selection"
        assert update_kline_data.name == "tasks.kline.update"
        assert update_indicators.name == "tasks.indicators.update"
        assert backfill_indicators.name == "tasks.indicators.backfill"
        assert run_simple_backtest.name == "tasks.backtest.run_simple_backtest"
        assert run_rule_exploration.name == "tasks.rule_explore.run_rule_exploration"
        assert run_rule_validation.name == "tasks.rule_explore.run_rule_validation"
