import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.error import setup_error_handlers
from app.middleware import TraceIDMiddleware
from app.logging_config import setup_logging

logger = logging.getLogger(__name__)


def create_app(
    title: str = "Sunny Sailor API",
    version: str = "1.0.0",
    description: str = "",
    log_level: str = "INFO",
    cors_origins: list[str] | None = None,
) -> FastAPI:
    setup_logging(level=log_level)

    app = FastAPI(title=title, version=version, description=description)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(TraceIDMiddleware)

    setup_error_handlers(app)

    logger.info("Application created", extra={"title": title, "version": version})

    return app
