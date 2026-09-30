from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtWidgets import QFormLayout, QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from app.constants import AGENT_LABELS
from app.models.task import AgentTask


class ResultPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        form = QFormLayout()
        form.setHorizontalSpacing(24)
        self.values: dict[str, QLabel] = {}
        for key, title in (
            ("task", "任务"),
            ("status", "状态"),
            ("project", "项目"),
            ("brain", "Brain"),
            ("executor", "Executor"),
            ("duration", "运行时长"),
            ("retries", "返工次数"),
            ("tests", "测试"),
            ("files", "修改文件"),
        ):
            value = QLabel("—")
            value.setWordWrap(True)
            self.values[key] = value
            form.addRow(title, value)
        layout.addLayout(form)
        self.summary = QPlainTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setPlaceholderText("任务完成后将在这里显示可靠获取到的结果。")
        layout.addWidget(self.summary, 1)

    def set_task(self, task: AgentTask, payload: dict[str, Any] | None = None) -> None:
        self.values["task"].setText(_single_line(task.description))
        self.values["status"].setText(task.status)
        self.values["project"].setText(task.project_path)
        self.values["brain"].setText(AGENT_LABELS.get(task.brain, task.brain))
        self.values["executor"].setText(AGENT_LABELS.get(task.executor, task.executor))
        self.values["duration"].setText(_duration(task.started_at, task.finished_at))
        retries, tests, files = _result_counts(payload)
        self.values["retries"].setText(
            f"{retries} / {task.max_retries}" if retries is not None else "未知"
        )
        self.values["tests"].setText(tests or "未知")
        self.values["files"].setText(str(files) if files is not None else "未知")
        self.summary.setPlainText(task.result_summary or _payload_summary(payload))

    def clear(self) -> None:
        for value in self.values.values():
            value.setText("—")
        self.summary.clear()


def _single_line(value: str, limit: int = 160) -> str:
    collapsed = " ".join(value.split())
    return collapsed if len(collapsed) <= limit else f"{collapsed[:limit]}…"


def _duration(started: str | None, finished: str | None) -> str:
    if not started or not finished:
        return "未知"
    try:
        seconds = max(0, int((datetime.fromisoformat(finished) - datetime.fromisoformat(started)).total_seconds()))
    except ValueError:
        return "未知"
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours} 小时 {minutes} 分 {seconds} 秒"
    if minutes:
        return f"{minutes} 分 {seconds} 秒"
    return f"{seconds} 秒"


def _result_counts(payload: dict[str, Any] | None) -> tuple[int | None, str, int | None]:
    if not payload:
        return None, "", None
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        return None, "", None
    retries = 0
    test_lines: list[str] = []
    files: set[str] = set()
    for task in tasks:
        if not isinstance(task, dict):
            continue
        attempts = task.get("attempts")
        if not isinstance(attempts, list):
            continue
        retries += max(0, len(attempts) - 1)
        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue
            execution = attempt.get("execution")
            if not isinstance(execution, dict):
                continue
            changed = execution.get("filesChanged")
            if isinstance(changed, list):
                files.update(str(item) for item in changed if isinstance(item, str))
            tests = execution.get("tests")
            if isinstance(tests, list):
                for test in tests:
                    if isinstance(test, dict) and test.get("status") == "passed":
                        detail = test.get("detail")
                        if isinstance(detail, str) and detail.strip():
                            test_lines.append(detail.strip())
    return retries, "; ".join(test_lines[-3:]), len(files)


def _payload_summary(payload: dict[str, Any] | None) -> str:
    if not payload:
        return "没有获取到可验证的结构化结果。"
    if isinstance(payload.get("error"), str):
        return str(payload["error"])
    plan = payload.get("plan")
    if isinstance(plan, dict) and isinstance(plan.get("summary"), str):
        return str(plan["summary"])
    return "任务状态已记录，未提供额外概要。"

