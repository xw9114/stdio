from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout


class WelcomeDialog(QDialog):
    def __init__(self, orchestrator_path: str, parent=None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(parent)
        self.setWindowTitle("欢迎使用 Dual Agent Studio")
        self.setMinimumWidth(620)
        layout = QVBoxLayout(self)
        title = QLabel("欢迎使用 Dual Agent Studio")
        title.setObjectName("appTitle")
        description = QLabel(
            "首先确认 Claude、Codex、Git 和 dual-agent orchestrator 已安装。\n"
            "Studio 不读取或保存任何登录凭据。"
        )
        description.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(description)

        row = QHBoxLayout()
        self.path_edit = QLineEdit(orchestrator_path)
        choose = QPushButton("选择 dual-agent.cmd")
        choose.clicked.connect(self._browse)
        row.addWidget(self.path_edit, 1)
        row.addWidget(choose)
        layout.addLayout(row)

        start = QPushButton("开始使用")
        start.setObjectName("primaryButton")
        start.clicked.connect(self._accept_if_valid)
        layout.addWidget(start)

    def orchestrator_path(self) -> str:
        return self.path_edit.text().strip()

    def _browse(self) -> None:
        filename, _selected = QFileDialog.getOpenFileName(
            self,
            "选择 dual-agent.cmd",
            self.path_edit.text(),
            "Command files (*.cmd);;All files (*)",
        )
        if filename:
            self.path_edit.setText(filename)

    def _accept_if_valid(self) -> None:
        path = Path(self.orchestrator_path())
        if not path.is_file():
            QMessageBox.warning(self, "路径无效", f"找不到 dual-agent.cmd：\n{path}")
            return
        self.accept()

