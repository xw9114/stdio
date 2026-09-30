from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPlainTextEdit, QSplitter, QVBoxLayout, QWidget

from app.constants import AGENT_LABELS
from app.models.task import AgentTask


class HistoryPanel(QWidget):
    task_selected = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_selected)
        splitter.addWidget(self.list_widget)

        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        self.title = QLabel("选择一条历史任务")
        self.title.setObjectName("sectionTitle")
        self.meta = QLabel("")
        self.meta.setObjectName("muted")
        self.description = QPlainTextEdit()
        self.description.setReadOnly(True)
        detail_layout.addWidget(self.title)
        detail_layout.addWidget(self.meta)
        detail_layout.addWidget(self.description, 1)
        splitter.addWidget(detail_widget)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter)

    def set_history(self, history: list[AgentTask]) -> None:
        self.list_widget.clear()
        for task in history:
            timestamp = _local_time(task.started_at)
            first_line = " ".join(task.description.split())[:80]
            item = QListWidgetItem(f"{timestamp}\n{first_line}\n{task.status}")
            item.setData(Qt.ItemDataRole.UserRole, task)
            self.list_widget.addItem(item)

    def _on_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if not current:
            return
        task = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(task, AgentTask):
            return
        self.title.setText(task.status)
        self.meta.setText(
            f"{task.project_path}\n"
            f"{AGENT_LABELS.get(task.brain, task.brain)} → "
            f"{AGENT_LABELS.get(task.executor, task.executor)}"
        )
        self.description.setPlainText(task.description)
        self.task_selected.emit(task)


def _local_time(value: str | None) -> str:
    if not value:
        return "未知时间"
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value[:16]

