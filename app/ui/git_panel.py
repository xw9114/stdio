from __future__ import annotations

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout, QWidget
from PySide6.QtCore import Qt, Signal


class GitPanel(QWidget):
    refresh_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        toolbar = QHBoxLayout()
        refresh = QPushButton("刷新")
        refresh.clicked.connect(self.refresh_requested)
        toolbar.addWidget(refresh)
        copy = QPushButton("复制 Diff")
        copy.clicked.connect(self._copy)
        toolbar.addWidget(copy)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self.status_view = QPlainTextEdit()
        self.status_view.setReadOnly(True)
        self.status_view.setMaximumHeight(130)
        self.status_view.setPlaceholderText("Git status")
        self.diff_view = QPlainTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.diff_view.setPlaceholderText("Git diff")
        splitter.addWidget(self.status_view)
        splitter.addWidget(self.diff_view)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

    def set_content(self, status: str, diff: str) -> None:
        self.status_view.setPlainText(status)
        self.diff_view.setPlainText(diff)

    def set_error(self, message: str) -> None:
        self.status_view.setPlainText(message)
        self.diff_view.clear()

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self.diff_view.toPlainText())

