from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.constants import DEFAULT_ORCHESTRATOR_PATH


@dataclass(slots=True)
class AppSettings:
    orchestrator_path: str = DEFAULT_ORCHESTRATOR_PATH
    project_path: str = ""
    default_brain: str = "claude"
    default_executor: str = "codex"
    default_max_retries: int = 3
    auto_scroll_logs: bool = True
    check_environment_on_start: bool = True
    auto_detect_roles: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AppSettings":
        defaults = cls()
        return cls(
            orchestrator_path=_string(value.get("orchestrator_path"), defaults.orchestrator_path),
            project_path=_string(value.get("project_path"), defaults.project_path),
            default_brain=_string(value.get("default_brain"), defaults.default_brain),
            default_executor=_string(value.get("default_executor"), defaults.default_executor),
            default_max_retries=_bounded_int(
                value.get("default_max_retries"), defaults.default_max_retries, 0, 20
            ),
            auto_scroll_logs=_boolean(value.get("auto_scroll_logs"), defaults.auto_scroll_logs),
            check_environment_on_start=_boolean(
                value.get("check_environment_on_start"), defaults.check_environment_on_start
            ),
            auto_detect_roles=_boolean(value.get("auto_detect_roles"), defaults.auto_detect_roles),
        )


def _string(value: object, default: str) -> str:
    return value if isinstance(value, str) else default


def _boolean(value: object, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _bounded_int(value: object, default: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return min(maximum, max(minimum, value))

