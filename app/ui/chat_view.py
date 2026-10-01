from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.constants import ROUTE_LABELS
from app.core.task_state import StateSnapshot, TaskPhase, usage_summary
from app.models.task import AgentTask
from app.ui.result_panel import _duration, _result_counts
from app.ui.theme import ACTIVE_COLOR, DANGER, DONE_COLOR, PENDING_COLOR


class _UserMessage(QWidget):
    def __init__(self, text: str, meta: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        bubble = QFrame()
        bubble.setObjectName("userBubble")
        self._bubble = bubble
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(text)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._label = label
        self._natural_width = max(
            label.fontMetrics().horizontalAdvance(line) for line in text.split("\n") or [""]
        ) + 64
        bubble_layout.addWidget(label)
        layout.addWidget(bubble, 0, Qt.AlignmentFlag.AlignRight)

        self._meta_label: QLabel | None = None
        if meta:
            meta_label = QLabel(meta)
            meta_label.setObjectName("muted")
            meta_label.setTextFormat(Qt.TextFormat.PlainText)
            meta_label.setWordWrap(True)
            layout.addWidget(meta_label, 0, Qt.AlignmentFlag.AlignRight)
            self._meta_label = meta_label

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        width = max(80, min(self._natural_width, 656, int(self.width() * 0.8)))
        if self._bubble.width() != width:
            self._bubble.setFixedWidth(width)
        bubble_height = self._label.heightForWidth(width - 28) + 20
        self._bubble.setFixedHeight(bubble_height)
        total_height = bubble_height
        if self._meta_label is not None:
            meta_width = min(self.width(), max(width, 320))
            self._meta_label.setFixedWidth(meta_width)
            meta_height = self._meta_label.heightForWidth(meta_width)
            self._meta_label.setFixedHeight(meta_height)
            total_height += 5 + meta_height
        if self.height() != total_height:
            self.setFixedHeight(total_height)


class _StepCard(QFrame):
    def __init__(
        self,
        title: str,
        attempt: int | None = None,
        phase: TaskPhase | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("stepCard")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.state = "pending"
        # A step reads as one quiet line once finished ("Brain 已验收修改 · 18 秒");
        # only the active step stands out. Finished titles switch from the
        # progressive "正在…" to "已…" so the history does not claim it is
        # still running.
        # The role already has its own coloured label; drop it from the title
        # so a row reads "Brain › 已验收修改", not "Brain › Brain 已验收修改".
        role_name = (
            "Brain"
            if phase in {TaskPhase.PLANNING, TaskPhase.REVIEWING}
            else "Executor" if phase in {TaskPhase.EXECUTING, TaskPhase.RETRYING} else ""
        )
        if role_name and title.startswith(f"{role_name} "):
            title = title[len(role_name) + 1 :]
        self._title = title
        self._attempt = attempt
        self._started = time.monotonic()
        self._elapsed: float | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 1, 10, 1)
        layout.setSpacing(4)
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self.dot = QFrame()
        self.dot.setFixedSize(8, 8)
        header_layout.addWidget(self.dot)

        if phase in {TaskPhase.PLANNING, TaskPhase.REVIEWING}:
            role = QLabel("Brain")
            role.setObjectName("roleLabel")
            role.setProperty("role", "brain")
            header_layout.addWidget(role)
        elif phase in {TaskPhase.EXECUTING, TaskPhase.RETRYING}:
            role = QLabel("Executor")
            role.setObjectName("roleLabel")
            role.setProperty("role", "executor")
            header_layout.addWidget(role)
        elif phase == TaskPhase.VERIFYING:
            role = QLabel("验证")
            role.setObjectName("roleLabel")
            role.setProperty("role", "verify")
            header_layout.addWidget(role)

        self.header = QToolButton()
        self.header.setObjectName("stepHeader")
        self.header.setText(title)
        self.header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.header.setArrowType(Qt.ArrowType.RightArrow)
        self.header.setCheckable(True)
        self.header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        header_layout.addWidget(self.header, 1)

        self.meta = QLabel()
        self.meta.setObjectName("stepMeta")
        header_layout.addWidget(self.meta)
        layout.addLayout(header_layout)

        self.log = QPlainTextEdit()
        self.log.setObjectName("stepLog")
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        self.log.setMaximumHeight(220)
        self.log.hide()
        layout.addWidget(self.log)
        self.header.toggled.connect(self._toggle_log)
        self.set_state("pending")

    def _toggle_log(self, expanded: bool) -> None:
        self.header.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self.log.setVisible(expanded)

    def append_line(self, source: str, text: str) -> None:
        self.log.appendPlainText(f"{source}: {text}" if source else text)

    def set_state(self, state: str) -> None:
        colors = {
            "pending": PENDING_COLOR,
            "active": ACTIVE_COLOR,
            "done": DONE_COLOR,
            "failed": DANGER,
        }
        if self.state == "active" and state in {"done", "failed"}:
            self._elapsed = time.monotonic() - self._started
        self.state = state
        color = colors.get(state, PENDING_COLOR)
        self.dot.setStyleSheet(f"background: {color}; border-radius: 4px;")
        self.header.setText(self._title.replace("正在", "已", 1) if state == "done" else self._title)
        parts = [f"第 {self._attempt} 次"] if self._attempt and self._attempt > 1 else []
        if self._elapsed is not None and self._elapsed >= 1:
            parts.append(_short_duration(self._elapsed))
        self.meta.setText(" · ".join(parts))
        for widget in (self, self.header):
            widget.setProperty("state", state)
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def line_count(self) -> int:
        return self.log.document().blockCount() if self.log.toPlainText() else 0


class _ResultCard(QFrame):
    def __init__(
        self,
        task: AgentTask,
        payload: dict[str, Any] | None,
        resumable: bool = False,
        isolation: dict[str, str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("resultCard")
        self.task_id = task.id
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        titles = {
            TaskPhase.PASSED: ("✓ 任务完成", "passed"),
            TaskPhase.BLOCKED: ("任务已阻塞", "failed"),
            TaskPhase.FAILED: ("任务失败", "failed"),
            TaskPhase.CANCELLED: ("任务已取消", "muted"),
        }
        title, status = titles.get(task.status, ("任务结束", "muted"))
        # Status on the left and the key numbers on the right of one line,
        # the summary under it: the outcome is readable at a glance.
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(12)
        status_label = QLabel(title)
        status_label.setObjectName("resultStatus")
        status_label.setProperty("status", status)
        top.addWidget(status_label)
        top.addStretch()
        retries, _, files = _result_counts(payload)
        numbers = [_duration(task.started_at, task.finished_at)]
        if retries:
            numbers.append(f"返工 {retries} 次")
        usage = usage_summary(payload)
        if usage:
            numbers.append(usage)
        metrics = QLabel(" · ".join(numbers))
        metrics.setObjectName("stepMeta")
        if files is not None:
            metrics.setToolTip(f"修改文件 {files} 个")
        top.addWidget(metrics)
        layout.addLayout(top)

        summary = QLabel(task.result_summary or "暂无结果概要")
        summary.setTextFormat(Qt.TextFormat.PlainText)
        summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        summary.setWordWrap(True)
        layout.addWidget(summary)

        self.isolation_label: QLabel | None = None
        self.apply_button: QPushButton | None = None
        self.discard_button: QPushButton | None = None
        if isolation:
            self.isolation_label = QLabel(f"未应用 · 改动在分支 {isolation['branch']} 上")
            self.isolation_label.setObjectName("isolationNote")
            self.isolation_label.setToolTip(
                "这次运行在独立的 git 分支上完成，你的工作区还没有变化。"
                "确认没问题后点「应用到工作区」；不想要就「丢弃改动」。"
            )
            layout.addWidget(self.isolation_label, 0, Qt.AlignmentFlag.AlignLeft)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(8)
        if isolation:
            self.apply_button = QPushButton("应用到工作区")
            self.apply_button.setObjectName("primaryButton")
            buttons.addWidget(self.apply_button)
            self.discard_button = QPushButton("丢弃改动")
            self.discard_button.setObjectName("toolButton")
            buttons.addWidget(self.discard_button)
        self.diff_button = QPushButton("查看 Diff")
        self.diff_button.setObjectName("toolButton")
        buttons.addWidget(self.diff_button)
        self.resume_button: QPushButton | None = None
        if resumable:
            self.resume_button = QPushButton("继续执行")
            self.resume_button.setObjectName("primaryButton")
            self.resume_button.setToolTip("保留已完成的任务，从中断的任务接着执行")
            buttons.addWidget(self.resume_button)
        buttons.addStretch()
        layout.addLayout(buttons)

    def settle_isolation(self, outcome: str) -> None:
        """The run's branch was applied or discarded: say so, retire the buttons."""
        if self.isolation_label is not None:
            self.isolation_label.setText(outcome)
        for button in (self.apply_button, self.discard_button):
            if button is not None:
                button.setEnabled(False)


class _PlanCard(QFrame):
    """The plan of a plan-only run, waiting for the user's go-ahead.

    The user can untick tasks (passed to `resume --skip`), answer the Brain's
    questions or add guidance (`--note`), start execution, ask for a new plan
    built from that guidance, or drop the plan. Once a choice is made the card
    locks so the same plan cannot be started twice."""

    approved = Signal(list, str)
    replan_requested = Signal(str)
    discarded = Signal()

    def __init__(self, plan: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("planCard")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        tasks = [task for task in plan.get("tasks") or [] if isinstance(task, dict)]
        self.title = QLabel(f"计划已就绪 · {len(tasks)} 个任务")
        self.title.setObjectName("planTitle")
        layout.addWidget(self.title)

        route = ROUTE_LABELS.get(str(plan.get("route") or ""))
        if route:
            reason = str(plan.get("routeReason") or "").strip()
            route_label = _wrapped_label(f"路线：{route}" + (f" — {reason}" if reason else ""))
            route_label.setObjectName("planRoute")
            layout.addWidget(route_label)

        summary_text = str(plan.get("summary") or "").strip()
        if summary_text:
            summary = _wrapped_label(summary_text)
            summary.setObjectName("muted")
            layout.addWidget(summary)

        questions = [str(item) for item in plan.get("questions") or [] if str(item).strip()]
        if questions:
            heading = QLabel("Brain 的问题")
            heading.setObjectName("planSection")
            layout.addWidget(heading)
            for index, question in enumerate(questions, start=1):
                layout.addWidget(_wrapped_label(f"{index}. {question}"))

        heading = QLabel("任务（取消勾选即跳过）")
        heading.setObjectName("planSection")
        layout.addWidget(heading)
        self.task_checks: dict[str, QCheckBox] = {}
        for task in tasks:
            task_id = str(task.get("id") or "")
            check = QCheckBox(f"{task_id}  {task.get('title') or ''}")
            check.setObjectName("planTask")
            check.setChecked(True)
            check.setToolTip(_task_tooltip(task))
            check.toggled.connect(self._update_buttons)
            layout.addWidget(check)
            self.task_checks[task_id] = check

        self.note_edit = QPlainTextEdit()
        self.note_edit.setObjectName("planNote")
        self.note_edit.setPlaceholderText(
            "回答上面的问题或补充要求（可选）。开始执行时会交给 Brain 和 Executor；"
            "重新规划时会附加到任务描述后面。"
        )
        self.note_edit.setFixedHeight(76)
        self.note_edit.textChanged.connect(self._update_buttons)
        layout.addWidget(self.note_edit)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(8)
        self.approve_button = QPushButton("开始执行")
        self.approve_button.setObjectName("primaryButton")
        self.approve_button.clicked.connect(self._approve)
        buttons.addWidget(self.approve_button)
        self.replan_button = QPushButton("按补充说明重新规划")
        self.replan_button.setObjectName("toolButton")
        self.replan_button.clicked.connect(self._replan)
        buttons.addWidget(self.replan_button)
        self.discard_button = QPushButton("放弃")
        self.discard_button.setObjectName("toolButton")
        self.discard_button.clicked.connect(self._discard)
        buttons.addWidget(self.discard_button)
        buttons.addStretch()
        layout.addLayout(buttons)
        self._update_buttons()

    def skipped_ids(self) -> list[str]:
        return [task_id for task_id, check in self.task_checks.items() if not check.isChecked()]

    def note(self) -> str:
        return self.note_edit.toPlainText().strip()

    def lock(self, outcome: str) -> None:
        self.title.setText(f"{self.title.text()} · {outcome}")
        for widget in (
            self.approve_button,
            self.replan_button,
            self.discard_button,
            self.note_edit,
            *self.task_checks.values(),
        ):
            widget.setEnabled(False)

    def _update_buttons(self) -> None:
        self.approve_button.setEnabled(
            any(check.isChecked() for check in self.task_checks.values())
        )
        self.replan_button.setEnabled(bool(self.note()))

    def _approve(self) -> None:
        self.lock("已开始执行")
        self.approved.emit(self.skipped_ids(), self.note())

    def _replan(self) -> None:
        self.lock("已重新规划")
        self.replan_requested.emit(self.note())

    def _discard(self) -> None:
        self.lock("已放弃")
        self.discarded.emit()


def _short_duration(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds} 秒"
    minutes, rest = divmod(seconds, 60)
    return f"{minutes} 分 {rest} 秒" if rest else f"{minutes} 分"


def _wrapped_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


def _task_tooltip(task: dict[str, Any]) -> str:
    lines = [str(task.get("instructions") or "").strip()]
    criteria = [str(item) for item in task.get("acceptanceCriteria") or []]
    if criteria:
        lines.append("验收标准：\n" + "\n".join(f"• {item}" for item in criteria))
    commands = [str(item) for item in task.get("validationCommands") or []]
    if commands:
        lines.append("验证命令：\n" + "\n".join(commands))
    return "\n\n".join(line for line in lines if line)


class ChatView(QWidget):
    show_diff_requested = Signal()
    resume_requested = Signal(object)
    apply_requested = Signal(object)
    discard_requested = Signal(object)
    plan_approved = Signal(list, str)
    plan_replan_requested = Signal(str)
    plan_discarded = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("chatArea")
        self._messages: list[QWidget] = []
        self._gaps: list[QWidget] = []
        self._active_card: _StepCard | None = None
        self._active_key: tuple[TaskPhase, int | None] | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.scroll_area)

        content = QWidget()
        self.scroll_area.setWidget(content)
        centered_layout = QHBoxLayout(content)
        centered_layout.setContentsMargins(24, 20, 24, 20)
        centered_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        centered_layout.addStretch()

        column = QWidget()
        column.setMaximumWidth(760)
        column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._column_layout = QVBoxLayout(column)
        self._column_layout.setContentsMargins(0, 0, 0, 0)
        self._column_layout.setSpacing(4)
        centered_layout.addWidget(column, 1)
        centered_layout.addStretch()

        self._empty_state = QWidget()
        empty_layout = QVBoxLayout(self._empty_state)
        empty_layout.setContentsMargins(0, 0, 0, 0)
        empty_layout.addStretch()
        title = QLabel("要让 Brain 和 Executor 做什么？")
        title.setObjectName("emptyStateTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setWordWrap(True)
        empty_layout.addWidget(title)
        subtitle = QLabel("在下方描述任务，Brain 负责规划与验收，Executor 负责修改代码。")
        subtitle.setObjectName("muted")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        empty_layout.addWidget(subtitle)
        empty_layout.addStretch()
        self._column_layout.addWidget(self._empty_state, 1)
        self._column_layout.addStretch()

    def clear(self) -> None:
        for widget in (*self._messages, *self._gaps):
            self._column_layout.removeWidget(widget)
            widget.deleteLater()
        self._messages.clear()
        self._gaps.clear()
        self._active_card = None
        self._active_key = None
        self._empty_state.show()
        self.scroll_area.verticalScrollBar().setValue(0)

    def add_user_message(self, text: str, meta: str = "") -> None:
        self._append_message(_UserMessage(text, meta))

    def set_phase(self, snapshot: StateSnapshot) -> None:
        if snapshot.phase in {
            TaskPhase.PLANNING,
            TaskPhase.EXECUTING,
            TaskPhase.RETRYING,
            TaskPhase.VERIFYING,
            TaskPhase.REVIEWING,
        }:
            key = (snapshot.phase, snapshot.attempt)
            if key == self._active_key:
                return
            self._end_active("done")
            card = _StepCard(snapshot.message, snapshot.attempt, snapshot.phase)
            card.set_state("active")
            self._active_card = card
            self._active_key = key
            self._append_message(card)
        elif snapshot.phase == TaskPhase.PASSED:
            self._end_active("done")
        elif snapshot.phase in {TaskPhase.BLOCKED, TaskPhase.FAILED, TaskPhase.CANCELLED}:
            self._end_active("failed")

    def append_log(self, source: str, text: str) -> None:
        if self._active_card is None:
            self._active_card = _StepCard("准备中")
            self._active_card.set_state("active")
            self._active_key = None
            self._append_message(self._active_card)
        # stderr ("Error" source) is deliberately not treated as failure:
        # agents write routine warnings there (Codex prints dozens of skill
        # loading errors on every start), which turned every card red.
        # Failure comes from the phase flow (blocked/failed) or the result.
        self._active_card.append_line(source, text)

    def add_result(
        self,
        task: AgentTask,
        payload: dict[str, Any] | None,
        *,
        resumable: bool = False,
        isolation: dict[str, str] | None = None,
    ) -> None:
        ending_state = "done" if task.status == TaskPhase.PASSED else "failed"
        self._end_active(ending_state)
        result = _ResultCard(task, payload, resumable, isolation)
        result.diff_button.clicked.connect(self.show_diff_requested.emit)
        if result.resume_button is not None:
            result.resume_button.clicked.connect(lambda: self.resume_requested.emit(task))
        if result.apply_button is not None:
            result.apply_button.clicked.connect(lambda: self.apply_requested.emit(task))
        if result.discard_button is not None:
            result.discard_button.clicked.connect(lambda: self.discard_requested.emit(task))
        self._append_message(result)
        self._active_card = None
        self._active_key = None

    def settle_isolation(self, task_id: str, outcome: str) -> None:
        for message in self._messages:
            if isinstance(message, _ResultCard) and message.task_id == task_id:
                message.settle_isolation(outcome)

    def add_plan(self, plan: dict[str, Any]) -> None:
        self._end_active("done")
        card = _PlanCard(plan)
        card.approved.connect(self.plan_approved.emit)
        card.replan_requested.connect(self.plan_replan_requested.emit)
        card.discarded.connect(self.plan_discarded.emit)
        self._append_message(card)
        self._active_card = None
        self._active_key = None

    def message_count(self) -> int:
        return len(self._messages)

    def _end_active(self, state: str) -> None:
        if self._active_card is not None and self._active_card.state == "active":
            self._active_card.set_state(state)

    def _append_message(self, message: QWidget) -> None:
        scrollbar = self.scroll_area.verticalScrollBar()
        near_bottom = scrollbar.maximum() - scrollbar.value() < 40
        self._empty_state.hide()
        # Step rows sit tight together; bubbles and cards get breathing room
        # where the conversation changes from one kind of message to another.
        previous = self._messages[-1] if self._messages else None
        if previous is not None and not (isinstance(previous, _StepCard) and isinstance(message, _StepCard)):
            spacer = QWidget()
            spacer.setFixedHeight(10)
            spacer.setObjectName("messageGap")
            self._column_layout.insertWidget(self._column_layout.count() - 2, spacer)
            self._gaps.append(spacer)
        # The column ends with the empty-state placeholder and a stretch.
        self._column_layout.insertWidget(self._column_layout.count() - 2, message)
        self._messages.append(message)
        if near_bottom:
            QTimer.singleShot(0, self, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
