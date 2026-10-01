from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.constants import normalize_run_mode


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class AgentTask:
    description: str
    project_path: str
    brain: str
    executor: str
    max_retries: int
    id: str = field(default_factory=lambda: uuid4().hex)
    status: str = "idle"
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    log_path: str | None = None
    result_summary: str = ""
    status_json: dict[str, Any] | None = None
    # A RUN_MODES key (auto / reviewed / planned / single), kept in history
    # so the workflows can be compared on real tasks.
    mode: str = "auto"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AgentTask":
        return cls(
            id=str(value.get("id") or uuid4().hex),
            description=str(value.get("description") or value.get("task") or ""),
            project_path=str(value.get("project_path") or value.get("project") or ""),
            brain=str(value.get("brain") or "claude"),
            executor=str(value.get("executor") or "codex"),
            max_retries=_integer(value.get("max_retries", value.get("maxRetries")), 3),
            status=str(value.get("status") or "unknown"),
            started_at=_optional_string(value.get("started_at", value.get("startedAt"))),
            finished_at=_optional_string(value.get("finished_at", value.get("finishedAt"))),
            exit_code=_optional_integer(value.get("exit_code", value.get("exitCode"))),
            log_path=_optional_string(value.get("log_path", value.get("logPath"))),
            result_summary=str(value.get("result_summary") or ""),
            status_json=value.get("status_json") if isinstance(value.get("status_json"), dict) else None,
            # Entries from before modes existed ran the two-agent plan flow.
            mode=normalize_run_mode(value.get("mode", "dual")),
        )


def _integer(value: object, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _optional_integer(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None

