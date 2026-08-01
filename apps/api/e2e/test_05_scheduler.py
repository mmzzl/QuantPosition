import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock


class TestSchedulerE2E:

    def test_loads_real_intervals_from_conf(self):
        from scheduler.scheduler import IntervalTask, CronTask, tasks_load_from_inputs

        mock_inputs = MagicMock()
        mock_inputs.config = {
            "script://bin/test_spider.py": {"enable": "true", "interval": "5m"},
            "script://bin/test_report.py": {"enable": "true", "cron": "hour=9,minute=30"},
            "script://bin/disabled_job.py": {"enable": "false", "interval": "1h"},
        }
        tasks = tasks_load_from_inputs(mock_inputs)
        assert len(tasks) == 2
        interval_tasks = [t for t in tasks if isinstance(t, IntervalTask)]
        cron_tasks = [t for t in tasks if isinstance(t, CronTask)]
        assert len(interval_tasks) == 1
        assert len(cron_tasks) == 1
        assert interval_tasks[0].trigger.interval.seconds == 300
        hour_field = next((f for f in cron_tasks[0].trigger.fields if f.name == "hour"), None)
        minute_field = next((f for f in cron_tasks[0].trigger.fields if f.name == "minute"), None)
        assert hour_field is not None
        assert minute_field is not None

    def test_register_tasks_into_real_scheduler(self):
        from scheduler.scheduler import IntervalTask
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler()
        task = IntervalTask("bin/test_job.py", "30s")
        assert task.isok
        scheduler.add_job(
            lambda: None,
            trigger=task.trigger,
            id="test_job",
            name="test",
            replace_existing=True,
        )
        jobs = scheduler.get_jobs()
        assert len(jobs) == 1
        job = jobs[0]
        assert job.id == "test_job"
        assert job.trigger.interval.seconds == 30

    def test_scheduler_from_systems_conf(self):
        from scheduler.scheduler import tasks_load_from_inputs, IntervalTask, CronTask
        from unittest.mock import MagicMock

        mock_conf = MagicMock()
        mock_conf.config = {
            "script://bin/e2e.py": {
                "enable": "true",
                "interval": "10m",
                "description": "E2E test task"
            },
            "script://bin/weekly.py": {
                "enable": "true",
                "cron": "hour=9,minute=0,day_of_week=1",
                "description": "Weekly report"
            },
        }
        tasks = tasks_load_from_inputs(mock_conf)
        assert len(tasks) == 2
        assert any(t.script.endswith("e2e.py") for t in tasks)
        assert any(t.script.endswith("weekly.py") for t in tasks)
