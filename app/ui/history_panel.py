from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import PureWindowsPath

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
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.constants import RUN_MODE_LABELS
from app.models.task import AgentTask
from app.ui.icons import icon
from app.ui.theme import ACTIVE_COLOR, DANGER, TEXT, TEXT_MUTED

# Marks a list row as a project heading rather than a task.
_GROUP_ROLE = Qt.ItemDataRole.UserRole + 1


class _ThreadItem(QWidget):
    """One task as a single quiet line: the title, a dot for anything that
    did not simply pass, and a short time. The full status, duration and mode
    go into the row's tooltip (`detail_text`)."""

    def __init__(self, task: AgentTask, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("threadItem")
        first_line = task.description.splitlines()[0].strip() if task.description else ""
        self._title_text = first_line or "未命名任务"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(34, 0, 10, 0)
        layout.setSpacing(8)

        self.title = QLabel()
        self.title.setObjectName("threadItemTitle")
        self.title.setTextFormat(Qt.TextFormat.PlainText)
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.title, 1)

        status = task.status.lower()
        # Passed runs are the normal case and stay unmarked; colour is kept
        # for what needs attention, which also tells repeated goals apart.
        color = None
        if status in {"failed", "blocked"}:
            color = DANGER
        elif status in {"running", "planning", "executing", "retrying", "reviewing", "awaiting_approval"}:
            color = ACTIVE_COLOR
        if color:
            dot = QFrame()
            dot.setFixedSize(6, 6)
            dot.setStyleSheet(f"background: {color}; border-radius: 3px;")
            layout.addWidget(dot)

        self.time = QLabel(_relative_time(task.started_at))
        self.time.setObjectName("threadItemTime")
        layout.addWidget(self.time)

        parts = [_STATUS_WORDS.get(status, "未完成"), _relative_time(task.started_at)]
        took = _compact_duration(task.started_at, task.finished_at)
        if took:
            parts.append(took)
        if task.mode != "auto":
            parts.append(RUN_MODE_LABELS.get(task.mode, task.mode))
        self.detail_text = " · ".join(parts)

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._update_title()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_title()

    def _update_title(self) -> None:
        width = max(40, self.title.width())
        self.title.setText(
            self.title.fontMetrics().elidedText(self._title_text, Qt.TextElideMode.ElideRight, width)
        )


class _ProjectHeading(QWidget):
    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("projectGroup")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)
        folder = QLabel()
        folder.setPixmap(icon("folder", TEXT_MUTED, 16).pixmap(16, 16))
        layout.addWidget(folder)
        label = QLabel(name)
        label.setObjectName("projectGroupName")
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(label, 1)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


def _project_name(path: str) -> str:
    # Windows path parsing also accepts forward slashes.
    cleaned = path.strip().rstrip("\\/")
    return PureWindowsPath(cleaned).name or cleaned or "未指定项目"


class HistoryPanel(QWidget):
    new_task_requested = Signal()
    environment_requested = Signal()
    settings_requested = Signal()
    task_selected = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setMinimumWidth(200)
        self.setMaximumWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 18, 10, 0)
        layout.setSpacing(2)

        title = QLabel("Dual Agent")
        title.setObjectName("appTitle")
        title.setProperty("sidebar", "true")
        title.setContentsMargins(10, 0, 0, 14)
        layout.addWidget(title)

        self.new_task_button = _nav_button("new", "新任务")
        self.new_task_button.clicked.connect(self.new_task_requested)
        layout.addWidget(self.new_task_button)

        self.environment_button = _nav_button("pulse", "检查环境")
        self.environment_button.clicked.connect(self.environment_requested)
        layout.addWidget(self.environment_button)

        layout.addSpacing(20)
        heading = QLabel("历史任务")
        heading.setObjectName("historyHeading")
        heading.setContentsMargins(10, 0, 0, 4)
        layout.addWidget(heading)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("threadList")
        self.list_widget.setSpacing(1)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.currentItemChanged.connect(self._on_selected)
        self.list_widget.itemClicked.connect(self._on_clicked)
        layout.addWidget(self.list_widget, 1)

        footer = QWidget()
        footer.setObjectName("sidebarFooter")
        footer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(10, 8, 0, 10)
        footer_layout.setSpacing(2)
        self.workspace_label = QLabel("未选择项目")
        self.workspace_label.setObjectName("footerStatus")
        self.workspace_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        footer_layout.addWidget(self.workspace_label, 1)
        self.settings_button = QToolButton()
        self.settings_button.setObjectName("iconButton")
        self.settings_button.setIcon(icon("settings", TEXT_MUTED, 18))
        self.settings_button.setIconSize(QSize(18, 18))
        self.settings_button.setToolTip("设置")
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.clicked.connect(self.settings_requested)
        footer_layout.addWidget(self.settings_button)
        layout.addWidget(footer)

    def sizeHint(self) -> QSize:
        return QSize(256, 600)

    def set_history(self, history: list[AgentTask]) -> None:
        """Lists the tasks under one heading per project, projects ordered by
        their most recent task (the history arrives newest first)."""
        self.list_widget.clear()
        groups: dict[str, list[AgentTask]] = {}
        for task in history:
            groups.setdefault(_project_name(task.project_path), []).append(task)
        for name, tasks in groups.items():
            heading = QListWidgetItem()
            heading.setData(_GROUP_ROLE, name)
            # Clickable, to fold the group, but never selected.
            heading.setFlags(Qt.ItemFlag.ItemIsEnabled)
            heading.setSizeHint(QSize(0, 34))
            heading.setToolTip(tasks[0].project_path)
            self.list_widget.addItem(heading)
            self.list_widget.setItemWidget(heading, _ProjectHeading(name))
            for task in tasks:
                widget = _ThreadItem(task)
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, task)
                item.setData(Qt.ItemDataRole.AccessibleTextRole, task.description)
                item.setToolTip(f"{task.description}\n{widget.detail_text}")
                item.setSizeHint(QSize(0, 32))
                self.list_widget.addItem(item)
                self.list_widget.setItemWidget(item, widget)

    def set_workspace(self, path: str) -> None:
        self.workspace_label.setText(_project_name(path) if path.strip() else "未选择项目")
        self.workspace_label.setToolTip(path)

    def task_items(self) -> list[QListWidgetItem]:
        items = (self.list_widget.item(row) for row in range(self.list_widget.count()))
        return [item for item in items if isinstance(item.data(Qt.ItemDataRole.UserRole), AgentTask)]

    def clear_selection(self) -> None:
        was_blocked = self.list_widget.blockSignals(True)
        try:
            self.list_widget.clearSelection()
            self.list_widget.setCurrentRow(-1)
        finally:
            self.list_widget.blockSignals(was_blocked)

    def _on_clicked(self, item: QListWidgetItem) -> None:
        if item.data(_GROUP_ROLE) is None:
            return
        # Fold or unfold the tasks up to the next project heading.
        rows: list[QListWidgetItem] = []
        row = self.list_widget.row(item) + 1
        while row < self.list_widget.count() and self.list_widget.item(row).data(_GROUP_ROLE) is None:
            rows.append(self.list_widget.item(row))
            row += 1
        hide = any(not task_item.isHidden() for task_item in rows)
        for task_item in rows:
            task_item.setHidden(hide)

    def _on_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        task = current.data(Qt.ItemDataRole.UserRole)
        if isinstance(task, AgentTask):
            self.task_selected.emit(task)


def _nav_button(icon_name: str, text: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("navButton")
    button.setIcon(icon(icon_name, TEXT, 18))
    button.setIconSize(QSize(18, 18))
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


_STATUS_WORDS = {
    "passed": "完成",
    "blocked": "阻塞",
    "failed": "失败",
    "cancelled": "已取消",
    "awaiting_approval": "待确认计划",
    "running": "运行中",
}


def _compact_duration(started: str | None, finished: str | None) -> str:
    """'45 秒', '11 分钟', '1 小时 5 分' - or '' when unknown."""
    if not started or not finished:
        return ""
    try:
        seconds = int((datetime.fromisoformat(finished) - datetime.fromisoformat(started)).total_seconds())
    except ValueError:
        return ""
    if seconds < 0:
        return ""
    if seconds < 60:
        return f"{seconds} 秒"
    if seconds < 3600:
        return f"{round(seconds / 60)} 分钟"
    hours, rest = divmod(seconds, 3600)
    return f"{hours} 小时 {rest // 60} 分" if rest >= 60 else f"{hours} 小时"


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
