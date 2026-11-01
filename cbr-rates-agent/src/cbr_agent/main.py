"""Точка входа: запуск uvicorn-сервера."""

from __future__ import annotations

import logging

import uvicorn

from cbr_agent.api import create_app
from cbr_agent.config import get_settings
from cbr_agent.logging import setup_logging

logger = logging.getLogger(__name__)


def run() -> None:
    """Запускает uvicorn с настройками из .env."""
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("starting server on %s:%d", settings.app_host, settings.app_port)

    app = create_app(settings)
    uvicorn.run(
        app,
        host=settings.app_host,
        port=settings.app_port,
        log_config=None,  # используем наш логгер
        access_log=True,
    )


if __name__ == "__main__":
    run()
