from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.constants import BRAIN_OPTIONS, DEFAULT_ORCHESTRATOR_PATH, EXECUTOR_OPTIONS, normalize_run_mode

# A soft built-in gradient (see app/ui/wallpaper.py); "" turns it off.
DEFAULT_WALLPAPER = "preset:mist"


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
    confirm_plan: bool = True
    run_mode: str = "auto"
    # "" for none, "preset:<key>" for a built-in gradient, else an image path.
    wallpaper: str = DEFAULT_WALLPAPER
    # 0 (sharp) to 3 (strong) for images; presets are soft already.
    wallpaper_blur: int = 2
    # Percent of extra light veil over the wallpaper, on top of what the
    # image needs for legible text.
    wallpaper_veil: int = 20
    # A system notification when a task ends while Studio is not in front:
    # runs take minutes and the user switches away.
    notify_on_finish: bool = True
    # Windows sleeping mid-run stops the agents; held only while one runs.
    keep_awake: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AppSettings":
        defaults = cls()
        return cls(
            orchestrator_path=_string(value.get("orchestrator_path"), defaults.orchestrator_path),
            project_path=_string(value.get("project_path"), defaults.project_path),
            # An agent that is no longer offered (sub2api) falls back to the
            # default: the picker would otherwise silently show its first entry.
            default_brain=_choice(value.get("default_brain"), BRAIN_OPTIONS, defaults.default_brain),
            default_executor=_choice(value.get("default_executor"), EXECUTOR_OPTIONS, defaults.default_executor),
            default_max_retries=_bounded_int(
                value.get("default_max_retries"), defaults.default_max_retries, 0, 20
            ),
            auto_scroll_logs=_boolean(value.get("auto_scroll_logs"), defaults.auto_scroll_logs),
            check_environment_on_start=_boolean(
                value.get("check_environment_on_start"), defaults.check_environment_on_start
            ),
            auto_detect_roles=_boolean(value.get("auto_detect_roles"), defaults.auto_detect_roles),
            confirm_plan=_boolean(value.get("confirm_plan"), defaults.confirm_plan),
            # Settings saved before run modes stored only a single_agent flag.
            run_mode=normalize_run_mode(
                value.get("run_mode", "single" if value.get("single_agent") is True else "auto")
            ),
            wallpaper=_string(value.get("wallpaper"), defaults.wallpaper),
            wallpaper_blur=_bounded_int(value.get("wallpaper_blur"), defaults.wallpaper_blur, 0, 3),
            wallpaper_veil=_bounded_int(value.get("wallpaper_veil"), defaults.wallpaper_veil, 0, 90),
            notify_on_finish=_boolean(value.get("notify_on_finish"), defaults.notify_on_finish),
            keep_awake=_boolean(value.get("keep_awake"), defaults.keep_awake),
        )


def _string(value: object, default: str) -> str:
    return value if isinstance(value, str) else default


def _choice(value: object, options: tuple, default: str) -> str:
    return value if isinstance(value, str) and any(option.key == value for option in options) else default


def _boolean(value: object, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _bounded_int(value: object, default: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return min(maximum, max(minimum, value))

