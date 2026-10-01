from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.models.task import AgentTask
from app.ui.theme import ACTIVE_COLOR, DANGER, DONE_COLOR, PENDING_COLOR


class _ThreadItem(QWidget):
    def __init__(self, task: AgentTask, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("threadItem")
        first_line = task.description.splitlines()[0].strip() if task.description else ""
        self._title_text = first_line or "未命名任务"
        if len(self._title_text) > 40:
            self._title_text = f"{self._title_text[:39]}…"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(5)

        self.title = QLabel()
        self.title.setObjectName("threadItemTitle")
        self.title.setTextFormat(Qt.TextFormat.PlainText)
        self.title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.title)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(6)
        dot = QFrame()
        dot.setFixedSize(8, 8)
        status = task.status.lower()
        if status == "passed":
            color = DONE_COLOR
        elif status in {"failed", "blocked"}:
            color = DANGER
        elif status in {"running", "planning", "executing", "retrying", "reviewing"}:
            color = ACTIVE_COLOR
        else:
            color = PENDING_COLOR
        dot.setStyleSheet(f"background: {color}; border-radius: 4px;")
        status_row.addWidget(dot)
        time_text = _relative_time(task.started_at)
        time_label = QLabel(f"{time_text} · 单 agent" if task.mode == "single" else time_text)
        time_label.setObjectName("threadItemTime")
        status_row.addWidget(time_label)
        status_row.addStretch()
        layout.addLayout(status_row)

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._update_title()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_title()

    def _update_title(self) -> None:
        width = max(40, self.width() - 20)
        self.title.setText(
            self.title.fontMetrics().elidedText(
                self._title_text, Qt.TextElideMode.ElideRight, width
            )
        )


class HistoryPanel(QWidget):
    new_task_requested = Signal()
    environment_requested = Signal()
    settings_requested = Signal()
    task_selected = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setMinimumWidth(200)
        self.setMaximumWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 14)
        layout.setSpacing(12)

        title = QLabel("Dual Agent Studio")
        title.setObjectName("appTitle")
        title.setProperty("sidebar", "true")
        layout.addWidget(title)

        self.new_task_button = QPushButton("+  新任务")
        self.new_task_button.setObjectName("newTaskButton")
        self.new_task_button.clicked.connect(self.new_task_requested)
        layout.addWidget(self.new_task_button)

        heading = QLabel("历史任务")
        heading.setObjectName("historyHeading")
        layout.addWidget(heading)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("threadList")
        self.list_widget.setSpacing(2)
        self.list_widget.currentItemChanged.connect(self._on_selected)
        layout.addWidget(self.list_widget, 1)

        self.environment_button = QPushButton("检查环境")
        self.environment_button.setObjectName("sidebarButton")
        self.environment_button.clicked.connect(self.environment_requested)
        layout.addWidget(self.environment_button)

        self.settings_button = QPushButton("设置")
        self.settings_button.setObjectName("sidebarButton")
        self.settings_button.clicked.connect(self.settings_requested)
        layout.addWidget(self.settings_button)

    def sizeHint(self) -> QSize:
        return QSize(248, 600)

    def set_history(self, history: list[AgentTask]) -> None:
        self.list_widget.clear()
        for task in history:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, task)
            item.setData(Qt.ItemDataRole.AccessibleTextRole, task.description)
            item.setToolTip(task.description)
            item.setSizeHint(QSize(0, 64))
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, _ThreadItem(task))

    def clear_selection(self) -> None:
        was_blocked = self.list_widget.blockSignals(True)
        try:
            self.list_widget.clearSelection()
            self.list_widget.setCurrentRow(-1)
        finally:
            self.list_widget.blockSignals(was_blocked)

    def _on_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        task = current.data(Qt.ItemDataRole.UserRole)
        if isinstance(task, AgentTask):
            self.task_selected.emit(task)


def _relative_time(value: str | None, now: datetime | None = None) -> str:
    if not value:
        return "未知时间"
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError:
        return "未知时间"

    reference = now or datetime.now().astimezone()
    if reference.tzinfo is None:
        reference = reference.astimezone()
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=reference.tzinfo)
    timestamp = timestamp.astimezone(reference.tzinfo)

    seconds = (reference - timestamp).total_seconds()
    if seconds < 60:
        return "刚刚"
    if timestamp.date() == reference.date():
        if seconds < 3600:
            return f"{int(seconds // 60)} 分钟前"
        return f"{int(seconds // 3600)} 小时前"
    if timestamp.date() == reference.date() - timedelta(days=1):
        return f"昨天 {timestamp:%H:%M}"
    return f"{timestamp:%Y-%m-%d}"


def _local_time(value: str | None) -> str:
    if not value:
        return "未知时间"
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value[:16]
