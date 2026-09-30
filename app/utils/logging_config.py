from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.utils.paths import app_log_path


def configure_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        return

    root.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        app_log_path(),
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root.addHandler(handler)
    logging.getLogger(__name__).info("Dual Agent Studio started")

