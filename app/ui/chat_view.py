from __future__ import annotations

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

from app.core.task_state import StateSnapshot, TaskPhase
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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self.dot = QFrame()
        self.dot.setFixedSize(10, 10)
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
            header_layout.addWidget(role)

        self.header = QToolButton()
        self.header.setObjectName("stepHeader")
        self.header.setText(title)
        self.header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.header.setArrowType(Qt.ArrowType.RightArrow)
        self.header.setCheckable(True)
        self.header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        header_layout.addWidget(self.header, 1)

        if attempt is not None:
            attempt_label = QLabel(f"第 {attempt} 次")
            attempt_label.setObjectName("muted")
            header_layout.addWidget(attempt_label)
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
        self.state = state
        color = colors.get(state, PENDING_COLOR)
        self.dot.setStyleSheet(f"background: {color}; border-radius: 5px;")

    def line_count(self) -> int:
        return self.log.document().blockCount() if self.log.toPlainText() else 0


class _ResultCard(QFrame):
    def __init__(
        self,
        task: AgentTask,
        payload: dict[str, Any] | None,
        resumable: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("resultCard")
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
        status_label = QLabel(title)
        status_label.setObjectName("resultStatus")
        status_label.setProperty("status", status)
        layout.addWidget(status_label)

        summary = QLabel(task.result_summary or "暂无结果概要")
        summary.setTextFormat(Qt.TextFormat.PlainText)
        summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        summary.setWordWrap(True)
        layout.addWidget(summary)

        retries, _, files = _result_counts(payload)
        duration = _duration(task.started_at, task.finished_at)
        retry_text = str(retries) if retries is not None else "未知"
        file_text = str(files) if files is not None else "未知"
        metrics = QLabel(f"耗时 {duration} · 返工 {retry_text} · 修改文件 {file_text}")
        metrics.setObjectName("muted")
        metrics.setWordWrap(True)
        layout.addWidget(metrics)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(8)
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
    plan_approved = Signal(list, str)
    plan_replan_requested = Signal(str)
    plan_discarded = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("chatArea")
        self._messages: list[QWidget] = []
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
        column.setMaximumWidth(820)
        column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._column_layout = QVBoxLayout(column)
        self._column_layout.setContentsMargins(0, 0, 0, 0)
        self._column_layout.setSpacing(14)
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
        for message in self._messages:
            self._column_layout.removeWidget(message)
            message.deleteLater()
        self._messages.clear()
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
        self, task: AgentTask, payload: dict[str, Any] | None, *, resumable: bool = False
    ) -> None:
        ending_state = "done" if task.status == TaskPhase.PASSED else "failed"
        self._end_active(ending_state)
        result = _ResultCard(task, payload, resumable)
        result.diff_button.clicked.connect(self.show_diff_requested.emit)
        if result.resume_button is not None:
            result.resume_button.clicked.connect(lambda: self.resume_requested.emit(task))
        self._append_message(result)
        self._active_card = None
        self._active_key = None

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
        self._column_layout.insertWidget(len(self._messages), message)
        self._messages.append(message)
        if near_bottom:
            QTimer.singleShot(0, self, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
