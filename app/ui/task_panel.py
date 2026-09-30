from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from app.constants import BRAIN_OPTIONS, EXECUTOR_OPTIONS
from app.core.natural_language_parser import NaturalLanguageParser
from app.models.settings import AppSettings


class TaskPanel(QFrame):
    browse_requested = Signal()
    init_requested = Signal()
    start_requested = Signal()
    stop_requested = Signal()
    project_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("section")
        self._parser = NaturalLanguageParser()
        self._brain_manual = False
        self._executor_manual = False
        self._retry_manual = False
        self._parse_timer = QTimer(self)
        self._parse_timer.setSingleShot(True)
        self._parse_timer.setInterval(350)
        self._parse_timer.timeout.connect(self._apply_inference)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        title = QLabel("任务")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        project_label = QLabel("项目目录")
        project_label.setObjectName("muted")
        layout.addWidget(project_label)
        project_row = QHBoxLayout()
        self.project_edit = QLineEdit()
        self.project_edit.setPlaceholderText(r"E:\projects\my-app")
        self.project_edit.editingFinished.connect(
            lambda: self.project_changed.emit(self.project_edit.text().strip())
        )
        project_row.addWidget(self.project_edit, 1)
        self.browse_button = QPushButton("选择项目")
        self.browse_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        self.browse_button.clicked.connect(self.browse_requested)
        project_row.addWidget(self.browse_button)
        self.init_button = QPushButton("初始化")
        self.init_button.setToolTip("在当前项目执行 dual-agent init")
        self.init_button.clicked.connect(self.init_requested)
        project_row.addWidget(self.init_button)
        layout.addLayout(project_row)

        task_label = QLabel("任务描述")
        task_label.setObjectName("muted")
        layout.addWidget(task_label)
        self.description_edit = QPlainTextEdit()
        self.description_edit.setPlaceholderText(
            "描述要完成的工作、验收要求和测试范围。\n"
            "例如：Claude 负责分析和验收，Codex 修改代码，最多返工 3 次。"
        )
        self.description_edit.setMinimumHeight(170)
        self.description_edit.textChanged.connect(lambda: self._parse_timer.start())
        layout.addWidget(self.description_edit, 1)

        options = QGridLayout()
        options.setHorizontalSpacing(12)
        options.setVerticalSpacing(9)
        options.addWidget(QLabel("Brain"), 0, 0)
        self.brain_combo = QComboBox()
        for option in BRAIN_OPTIONS:
            self.brain_combo.addItem(option.label, option.key)
        self.brain_combo.activated.connect(self._mark_brain_manual)
        options.addWidget(self.brain_combo, 0, 1)

        options.addWidget(QLabel("Executor"), 1, 0)
        self.executor_combo = QComboBox()
        for option in EXECUTOR_OPTIONS:
            self.executor_combo.addItem(option.label, option.key)
        self.executor_combo.activated.connect(self._mark_executor_manual)
        options.addWidget(self.executor_combo, 1, 1)

        options.addWidget(QLabel("最大返工"), 2, 0)
        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(0, 20)
        self.retry_spin.setSuffix(" 次")
        self.retry_spin.editingFinished.connect(self._mark_retry_manual)
        options.addWidget(self.retry_spin, 2, 1)
        options.setColumnStretch(1, 1)
        layout.addLayout(options)

        self.auto_detect_checkbox = QCheckBox("根据任务描述自动识别角色和返工次数")
        self.auto_detect_checkbox.toggled.connect(lambda checked: self._apply_inference() if checked else None)
        layout.addWidget(self.auto_detect_checkbox)

        buttons = QHBoxLayout()
        self.start_button = QPushButton("开始任务")
        self.start_button.setObjectName("primaryButton")
        self.start_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.start_button.clicked.connect(self.start_requested)
        buttons.addWidget(self.start_button)
        self.stop_button = QPushButton("停止")
        self.stop_button.setObjectName("dangerButton")
        self.stop_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_requested)
        buttons.addWidget(self.stop_button)
        buttons.addStretch()
        layout.addLayout(buttons)

    def apply_settings(self, settings: AppSettings) -> None:
        self.project_edit.setText(settings.project_path)
        self._set_combo_value(self.brain_combo, settings.default_brain)
        self._set_combo_value(self.executor_combo, settings.default_executor)
        self.retry_spin.setValue(settings.default_max_retries)
        self.auto_detect_checkbox.setChecked(settings.auto_detect_roles)
        self._brain_manual = False
        self._executor_manual = False
        self._retry_manual = False

    def set_project_path(self, path: str) -> None:
        self.project_edit.setText(path)
        self.project_changed.emit(path)

    def project_path(self) -> str:
        return self.project_edit.text().strip()

    def description(self) -> str:
        return self.description_edit.toPlainText().strip()

    def brain(self) -> str:
        return str(self.brain_combo.currentData())

    def executor(self) -> str:
        return str(self.executor_combo.currentData())

    def max_retries(self) -> int:
        return self.retry_spin.value()

    def set_running(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.browse_button.setEnabled(not running)
        self.init_button.setEnabled(not running)
        self.project_edit.setEnabled(not running)
        self.brain_combo.setEnabled(not running)
        self.executor_combo.setEnabled(not running)
        self.retry_spin.setEnabled(not running)

    def _apply_inference(self) -> None:
        if not self.auto_detect_checkbox.isChecked():
            return
        inferred = self._parser.parse(self.description_edit.toPlainText())
        if inferred.brain and not self._brain_manual:
            self._set_combo_value(self.brain_combo, inferred.brain)
        if inferred.executor and not self._executor_manual:
            self._set_combo_value(self.executor_combo, inferred.executor)
        if inferred.max_retries is not None and not self._retry_manual:
            self.retry_spin.setValue(inferred.max_retries)

    def _mark_brain_manual(self, _index: int) -> None:
        self._brain_manual = True

    def _mark_executor_manual(self, _index: int) -> None:
        self._executor_manual = True

    def _mark_retry_manual(self) -> None:
        self._retry_manual = True

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

