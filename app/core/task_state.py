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
    VERIFYING = "verifying"
    REVIEWING = "reviewing"
    AWAITING_APPROVAL = "awaiting_approval"
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


_STATUS_PREFIX = "[dual-agent] "


def phase_from_log(line: str) -> StateSnapshot | None:
    # Only the orchestrator's own status lines (`[dual-agent] <message>`, see
    # its cli.ts onStatus) may drive phases, matched from the start of the
    # message. Agents' event streams embed arbitrary command output - Codex
    # reading a test file full of fake "[dual-agent] ... is planning" lines
    # opened bogus planning cards mid-run - and a "Run blocked: <reason>"
    # reason can itself mention other phases, so it is checked first.
    stripped = line.lstrip()
    if not stripped.startswith(_STATUS_PREFIX):
        return None
    message = stripped[len(_STATUS_PREFIX):].lower()
    if message.startswith("run blocked"):
        return StateSnapshot(TaskPhase.BLOCKED, "任务已阻塞")
    if message.startswith("all tasks passed"):
        return StateSnapshot(TaskPhase.PASSED, "所有任务已通过验收")
    if message.startswith("plan ready for approval"):
        return StateSnapshot(TaskPhase.AWAITING_APPROVAL, "计划已生成，等待确认")
    if message.startswith("verifying"):
        attempt, _ = _parse_attempt(message)
        return StateSnapshot(TaskPhase.VERIFYING, "正在运行验证命令", attempt)
    if message.startswith("brain is reviewing"):
        attempt, _ = _parse_attempt(message)
        return StateSnapshot(TaskPhase.REVIEWING, "Brain 正在验收修改", attempt)
    if message.startswith("brain") and " is planning" in message:
        return StateSnapshot(TaskPhase.PLANNING, "Brain 正在分析并制定计划")
    if message.startswith("executor") and " is running" in message:
        attempt, maximum = _parse_attempt(message)
        phase = TaskPhase.RETRYING if attempt and attempt > 1 else TaskPhase.EXECUTING
        return StateSnapshot(phase, "Executor 正在修改并验证", attempt, maximum)
    return None


def phase_from_status(payload: dict[str, Any]) -> StateSnapshot:
    status = str(payload.get("status") or "").lower()
    if status == "planning":
        return StateSnapshot(TaskPhase.PLANNING, "Brain 正在分析并制定计划")
    if status == "complete":
        return StateSnapshot(TaskPhase.PASSED, "所有任务已通过验收")
    if status == "awaiting_approval":
        return StateSnapshot(TaskPhase.AWAITING_APPROVAL, "计划已生成，等待确认")
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


def status_matches_task(payload: dict[str, Any], task_description: str | None) -> bool:
    """Decide whether a ``status --json`` payload belongs to the given task.

    Fails closed: when there is a task to match against but the payload does
    not carry a usable ``goal`` field, we cannot verify it, so treat it as a
    mismatch rather than risk showing another run's state as if it were the
    current one.

    Both sides are normalized for line endings and surrounding whitespace:
    the orchestrator trims the goal it stores, and a CRLF picked up on the
    way through the command line must not turn a genuine match into a
    mismatch (which would degrade every final result to UNKNOWN).
    """
    if task_description is None:
        return True
    goal = payload.get("goal")
    return isinstance(goal, str) and _normalize_goal(goal) == _normalize_goal(task_description)


def _normalize_goal(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def final_phase(exit_code: int, payload: dict[str, Any] | None, cancelled: bool) -> TaskPhase:
    if cancelled:
        return TaskPhase.CANCELLED
    status = str(payload.get("status") or "").lower() if payload else ""
    if exit_code == 0 and status == "complete":
        return TaskPhase.PASSED
    if exit_code == 0 and status == "awaiting_approval":
        return TaskPhase.AWAITING_APPROVAL
    if status == "blocked" or exit_code == 2:
        return TaskPhase.BLOCKED
    if exit_code != 0 or status == "failed":
        return TaskPhase.FAILED
    return TaskPhase.UNKNOWN


_RESUMABLE_STATUSES = frozenset({"awaiting_approval", "blocked", "failed", "executing"})


def resumable_run_id(payload: dict[str, Any] | None) -> str | None:
    """Return the run id `dual-agent resume` can continue, if any.

    Mirrors the orchestrator's own rule: the run needs a plan and must have
    stopped short of completion ("executing" here means its process died,
    since this is only asked once the process has exited)."""
    if not payload or not isinstance(payload.get("plan"), dict):
        return None
    run_id = payload.get("runId")
    status = str(payload.get("status") or "")
    if isinstance(run_id, str) and run_id and status in _RESUMABLE_STATUSES:
        return run_id
    return None


def _parse_attempt(line: str) -> tuple[int | None, int | None]:
    import re

    # "attempt 2/4" on Executor lines, a bare "attempt 2" on review and
    # verification lines.
    match = re.search(r"attempt\s+(\d+)(?:\s*/\s*(\d+))?", line)
    if not match:
        return None, None
    maximum = match.group(2)
    return int(match.group(1)), int(maximum) if maximum else None

