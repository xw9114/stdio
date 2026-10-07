from __future__ import annotations

import json
import logging
from pathlib import Path

from app.constants import MAX_HISTORY_ITEMS
from app.models.task import AgentTask
from app.utils.paths import history_path

LOGGER = logging.getLogger(__name__)


class HistoryService:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or history_path()

    def load(self) -> list[AgentTask]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                raise ValueError("history root must be an array")
            return [AgentTask.from_dict(item) for item in payload if isinstance(item, dict)]
        except FileNotFoundError:
            return []
        except (OSError, ValueError, json.JSONDecodeError) as error:
            LOGGER.warning("Could not load history: %s", error)
            self._keep_unreadable_copy()
            return []

    def _keep_unreadable_copy(self) -> None:
        # The next save rewrites the file from what load() returned, so an
        # unreadable history would otherwise be replaced and lost for good.
        backup = self.path.with_suffix(f"{self.path.suffix}.corrupt")
        try:
            if self.path.is_file() and not backup.exists():
                backup.write_bytes(self.path.read_bytes())
                LOGGER.warning("Kept the unreadable history as %s", backup)
        except OSError as error:
            LOGGER.warning("Could not keep the unreadable history: %s", error)

    def add(self, task: AgentTask) -> list[AgentTask]:
        history = [item for item in self.load() if item.id != task.id]
        history.insert(0, task)
        history = history[:MAX_HISTORY_ITEMS]
        self._save(history)
        return history

    def update(self, task: AgentTask) -> list[AgentTask]:
        """Replaces a stored entry where it is, without moving it to the top."""
        history = [task if item.id == task.id else item for item in self.load()]
        self._save(history)
        return history

    def _save(self, history: list[AgentTask]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps([task.to_dict() for task in history], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

