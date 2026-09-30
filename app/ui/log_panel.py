from __future__ import annotations

import html
from pathlib import Path

from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QPushButton,
    QPlainTextEdit,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from app.constants import MAX_VISIBLE_LOG_LINES


class LogPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        toolbar = QHBoxLayout()
        self.auto_scroll = QCheckBox("自动滚动")
        self.auto_scroll.setChecked(True)
        toolbar.addWidget(self.auto_scroll)
        toolbar.addStretch()
        copy_button = QPushButton("复制")
        copy_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        copy_button.clicked.connect(self._copy)
        toolbar.addWidget(copy_button)
        clear_button = QPushButton("清空")
        clear_button.clicked.connect(self.clear)
        toolbar.addWidget(clear_button)
        save_button = QPushButton("保存日志")
        save_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        save_button.clicked.connect(self._save)
        toolbar.addWidget(save_button)
        layout.addLayout(toolbar)

        self.editor = QPlainTextEdit()
        self.editor.setReadOnly(True)
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.editor.document().setMaximumBlockCount(MAX_VISIBLE_LOG_LINES)
        layout.addWidget(self.editor, 1)

    def append_line(self, source: str, text: str) -> None:
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        prefix_format = QTextCharFormat()
        prefix_format.setForeground(QColor(_source_color(source)))
        prefix_format.setFontWeight(600)
        cursor.insertText(f"[{source}] ", prefix_format)
        body_format = QTextCharFormat()
        body_format.setForeground(QColor("#d7dce3"))
        cursor.insertText(text + "\n", body_format)
        if self.auto_scroll.isChecked():
            self.editor.setTextCursor(cursor)
            self.editor.ensureCursorVisible()

    def clear(self) -> None:
        self.editor.clear()

    def set_text(self, value: str) -> None:
        self.editor.setPlainText(value)
        if self.auto_scroll.isChecked():
            self.editor.moveCursor(QTextCursor.MoveOperation.End)

    def _copy(self) -> None:
        self.editor.selectAll()
        self.editor.copy()
        self.editor.moveCursor(QTextCursor.MoveOperation.End)

    def _save(self) -> None:
        filename, _selected = QFileDialog.getSaveFileName(
            self,
            "保存日志",
            "dual-agent.log",
            "Log files (*.log);;Text files (*.txt);;All files (*)",
        )
        if filename:
            Path(filename).write_text(self.editor.toPlainText(), encoding="utf-8")


def _source_color(source: str) -> str:
    return {
        "System": "#87aebc",
        "Process": "#9da8b5",
        "Claude": "#d6a968",
        "Codex": "#68b69f",
        "Git": "#8e9fc8",
        "Warning": "#d7b35f",
        "Error": "#df7881",
        "Success": "#66bd99",
    }.get(source, "#9da8b5")

