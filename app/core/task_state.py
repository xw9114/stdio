from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class TaskPhase(StrEnum):
    IDLE = "idle"
    CHECKING = "checking"
    RUNNING = "running"
    PLANNING = "planning"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    RETRYING = "retrying"
    PASSED = "passed"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class StateSnapshot:
    phase: TaskPhase
    message: str
    attempt: int | None = None
    max_attempts: int | None = None


def phase_from_log(line: str) -> StateSnapshot | None:
    lowered = line.lower()
    if "is planning" in lowered:
        return StateSnapshot(TaskPhase.PLANNING, "Brain 正在分析并制定计划")
    if "executor" in lowered and "is running" in lowered:
        attempt, maximum = _parse_attempt(lowered)
        phase = TaskPhase.RETRYING if attempt and attempt > 1 else TaskPhase.EXECUTING
        return StateSnapshot(phase, "Executor 正在修改并验证", attempt, maximum)
    if "brain is reviewing" in lowered:
        attempt, _ = _parse_attempt(lowered)
        return StateSnapshot(TaskPhase.REVIEWING, "Brain 正在验收修改", attempt)
    if "all tasks passed" in lowered:
        return StateSnapshot(TaskPhase.PASSED, "所有任务已通过验收")
    if "run blocked" in lowered:
        return StateSnapshot(TaskPhase.BLOCKED, "任务已阻塞")
    return None


def phase_from_status(payload: dict[str, Any]) -> StateSnapshot:
    status = str(payload.get("status") or "").lower()
    if status == "planning":
        return StateSnapshot(TaskPhase.PLANNING, "Brain 正在分析并制定计划")
    if status == "complete":
        return StateSnapshot(TaskPhase.PASSED, "所有任务已通过验收")
    if status == "blocked":
        return StateSnapshot(TaskPhase.BLOCKED, str(payload.get("error") or "任务已阻塞"))
    if status == "failed":
        return StateSnapshot(TaskPhase.FAILED, str(payload.get("error") or "任务执行失败"))
    if status != "executing":
        return StateSnapshot(TaskPhase.RUNNING, "任务正在运行")

    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        return StateSnapshot(TaskPhase.EXECUTING, "Executor 正在工作")
    running = next(
        (task for task in tasks if isinstance(task, dict) and task.get("status") == "running"),
        None,
    )
    if not isinstance(running, dict):
        return StateSnapshot(TaskPhase.EXECUTING, "准备执行下一项任务")
    attempts = running.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        return StateSnapshot(TaskPhase.EXECUTING, "Executor 正在修改并验证", 1)
    latest = attempts[-1] if isinstance(attempts[-1], dict) else {}
    attempt_number = latest.get("number") if isinstance(latest.get("number"), int) else len(attempts)
    if "execution" in latest and "review" not in latest:
        return StateSnapshot(TaskPhase.REVIEWING, "Brain 正在验收修改", attempt_number)
    return StateSnapshot(
        TaskPhase.RETRYING if attempt_number > 1 else TaskPhase.EXECUTING,
        "Executor 正在根据反馈继续修改" if attempt_number > 1 else "Executor 正在修改并验证",
        attempt_number,
    )


def final_phase(exit_code: int, payload: dict[str, Any] | None, cancelled: bool) -> TaskPhase:
    if cancelled:
        return TaskPhase.CANCELLED
    status = str(payload.get("status") or "").lower() if payload else ""
    if exit_code == 0 and status == "complete":
        return TaskPhase.PASSED
    if status == "blocked" or exit_code == 2:
        return TaskPhase.BLOCKED
    if exit_code != 0 or status == "failed":
        return TaskPhase.FAILED
    return TaskPhase.UNKNOWN


def _parse_attempt(line: str) -> tuple[int | None, int | None]:
    import re

    match = re.search(r"attempt\s+(\d+)\s*/\s*(\d+)", line)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))

