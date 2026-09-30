from __future__ import annotations

import os
import sys
from pathlib import Path


def application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def data_directory() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "DualAgentStudio"
    else:
        base = application_root() / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base


def logs_directory() -> Path:
    directory = data_directory() / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def settings_path() -> Path:
    return data_directory() / "settings.json"


def history_path() -> Path:
    return data_directory() / "history.json"


def app_log_path() -> Path:
    return data_directory() / "app.log"

