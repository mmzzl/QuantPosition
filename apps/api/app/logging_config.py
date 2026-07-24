import logging
import logging.handlers
import json
import os
import sys
from datetime import datetime
from pythonjsonlogger import jsonlogger


_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")


class TraceIDFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, "trace_id"):
            record.trace_id = ""
        return True


def ensure_log_dir():
    os.makedirs(_LOG_DIR, exist_ok=True)


def setup_logging(level: str = "INFO", log_dir: str | None = None) -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)
    target_dir = log_dir or _LOG_DIR
    os.makedirs(target_dir, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    json_formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(trace_id)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=os.path.join(target_dir, "app.log"),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(json_formatter)
    file_handler.addFilter(TraceIDFilter())

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(json_formatter)
    console_handler.addFilter(TraceIDFilter())

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
