from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
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

        self.diff_button = QPushButton("查看 Diff")
        self.diff_button.setObjectName("toolButton")
        layout.addWidget(self.diff_button, 0, Qt.AlignmentFlag.AlignLeft)


class ChatView(QWidget):
    show_diff_requested = Signal()

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
        self._active_card.append_line(source, text)
        if source == "Error":
            self._active_card.set_state("failed")

    def add_result(self, task: AgentTask, payload: dict[str, Any] | None) -> None:
        ending_state = "done" if task.status == TaskPhase.PASSED else "failed"
        self._end_active(ending_state)
        result = _ResultCard(task, payload)
        result.diff_button.clicked.connect(self.show_diff_requested.emit)
        self._append_message(result)
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
