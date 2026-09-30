from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from app.constants import BRAIN_OPTIONS, EXECUTOR_OPTIONS
from app.models.settings import AppSettings


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(620)
        self._settings = replace(settings)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        path_row = QHBoxLayout()
        self.path_edit = QLineEdit(settings.orchestrator_path)
        browse = QPushButton("选择")
        browse.clicked.connect(self._browse)
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(browse)
        form.addRow("Orchestrator 路径", path_row)

        self.brain_combo = QComboBox()
        for option in BRAIN_OPTIONS:
            self.brain_combo.addItem(option.label, option.key)
        _set_combo(self.brain_combo, settings.default_brain)
        form.addRow("默认 Brain", self.brain_combo)

        self.executor_combo = QComboBox()
        for option in EXECUTOR_OPTIONS:
            self.executor_combo.addItem(option.label, option.key)
        _set_combo(self.executor_combo, settings.default_executor)
        form.addRow("默认 Executor", self.executor_combo)

        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(0, 20)
        self.retry_spin.setValue(settings.default_max_retries)
        form.addRow("默认最大返工", self.retry_spin)

        self.auto_scroll = QCheckBox("实时日志自动滚动")
        self.auto_scroll.setChecked(settings.auto_scroll_logs)
        form.addRow("", self.auto_scroll)
        self.startup_check = QCheckBox("启动时检查环境")
        self.startup_check.setChecked(settings.check_environment_on_start)
        form.addRow("", self.startup_check)
        self.auto_detect = QCheckBox("根据任务描述自动识别角色")
        self.auto_detect.setChecked(settings.auto_detect_roles)
        form.addRow("", self.auto_detect)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def settings(self) -> AppSettings:
        self._settings.orchestrator_path = self.path_edit.text().strip()
        self._settings.default_brain = str(self.brain_combo.currentData())
        self._settings.default_executor = str(self.executor_combo.currentData())
        self._settings.default_max_retries = self.retry_spin.value()
        self._settings.auto_scroll_logs = self.auto_scroll.isChecked()
        self._settings.check_environment_on_start = self.startup_check.isChecked()
        self._settings.auto_detect_roles = self.auto_detect.isChecked()
        return self._settings

    def _browse(self) -> None:
        filename, _selected = QFileDialog.getOpenFileName(
            self,
            "选择 dual-agent.cmd",
            self.path_edit.text(),
            "Command files (*.cmd);;All files (*)",
        )
        if filename:
            self.path_edit.setText(filename)


def _set_combo(combo: QComboBox, value: str) -> None:
    index = combo.findData(value)
    if index >= 0:
        combo.setCurrentIndex(index)

