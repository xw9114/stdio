from __future__ import annotations

import json
import logging
from pathlib import Path

from app.models.settings import AppSettings
from app.utils.paths import settings_path

LOGGER = logging.getLogger(__name__)


class SettingsService:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings_path()

    def load(self) -> AppSettings:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("settings root must be an object")
            return AppSettings.from_dict(payload)
        except FileNotFoundError:
            return AppSettings()
        except (OSError, ValueError, json.JSONDecodeError) as error:
            LOGGER.warning("Could not load settings: %s", error)
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        self._atomic_write(settings.to_dict())

    def _atomic_write(self, payload: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

