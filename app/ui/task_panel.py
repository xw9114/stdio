from __future__ import annotations

from math import ceil
from typing import cast

from PySide6.QtCore import QEvent, QObject, QTimer, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
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
        self.setObjectName("composerHost")
        self._parser = NaturalLanguageParser()
        self._brain_manual = False
        self._executor_manual = False
        self._retry_manual = False
        self._parse_timer = QTimer(self)
        self._parse_timer.setSingleShot(True)
        self._parse_timer.setInterval(350)
        self._parse_timer.timeout.connect(self._apply_inference)

        # The splitter may leave less height than an eight-line draft needs.
        # Keeping the host scrollable prevents the workspace row from overlapping it.
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("composerScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        outer_layout.addWidget(self.scroll_area)

        content = QWidget()
        content.setObjectName("composerContent")
        self.scroll_area.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        self.composer = QFrame()
        self.composer.setObjectName("composer")
        self.composer.setProperty("focused", "false")
        composer_layout = QVBoxLayout(self.composer)
        composer_layout.setContentsMargins(12, 10, 12, 10)
        composer_layout.setSpacing(8)
        layout.addWidget(self.composer)

        self.description_edit = QPlainTextEdit()
        self.description_edit.setObjectName("composerInput")
        self.description_edit.setPlaceholderText(
            "描述任务、验收要求和测试范围…（Enter 发送，Shift+Enter 换行）"
        )
        self.description_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.description_edit.installEventFilter(self)
        self.description_edit.textChanged.connect(lambda: self._parse_timer.start())
        self.description_edit.document().contentsChanged.connect(self._update_description_height)
        self.description_edit.document().documentLayout().documentSizeChanged.connect(
            lambda _size: self._update_description_height()
        )
        composer_layout.addWidget(self.description_edit)

        chips = QHBoxLayout()
        chips.setContentsMargins(0, 0, 0, 0)
        chips.setSpacing(6)

        brain_label = QLabel("Brain")
        brain_label.setObjectName("chipLabel")
        chips.addWidget(brain_label)
        self.brain_combo = QComboBox()
        self.brain_combo.setObjectName("chip")
        self.brain_combo.setMinimumWidth(110)
        self.brain_combo.setMaximumWidth(136)
        for option in BRAIN_OPTIONS:
            self.brain_combo.addItem(option.label, option.key)
        self.brain_combo.activated.connect(self._mark_brain_manual)
        chips.addWidget(self.brain_combo)

        executor_label = QLabel("Executor")
        executor_label.setObjectName("chipLabel")
        chips.addWidget(executor_label)
        self.executor_combo = QComboBox()
        self.executor_combo.setObjectName("chip")
        self.executor_combo.setMinimumWidth(110)
        self.executor_combo.setMaximumWidth(136)
        for option in EXECUTOR_OPTIONS:
            self.executor_combo.addItem(option.label, option.key)
        self.executor_combo.activated.connect(self._mark_executor_manual)
        chips.addWidget(self.executor_combo)

        self.retry_spin = QSpinBox()
        self.retry_spin.setObjectName("chip")
        self.retry_spin.setRange(0, 20)
        self.retry_spin.setSuffix(" 次返工")
        self.retry_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.retry_spin.setMinimumWidth(82)
        self.retry_spin.setMaximumWidth(96)
        self.retry_spin.editingFinished.connect(self._mark_retry_manual)
        chips.addWidget(self.retry_spin)

        self.auto_detect_checkbox = QCheckBox("自动识别")
        self.auto_detect_checkbox.setToolTip("根据任务描述自动识别角色和返工次数")
        self.auto_detect_checkbox.toggled.connect(
            lambda checked: self._apply_inference() if checked else None
        )
        chips.addWidget(self.auto_detect_checkbox)
        chips.addStretch()

        self.start_button = QPushButton()
        self.start_button.setObjectName("sendButton")
        self.start_button.setFixedSize(32, 32)
        self.start_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp))
        self.start_button.setToolTip("发送 (Enter)")
        self.start_button.clicked.connect(self.start_requested)
        chips.addWidget(self.start_button)

        self.stop_button = QPushButton()
        self.stop_button.setObjectName("stopButton")
        self.stop_button.setFixedSize(32, 32)
        self.stop_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.stop_button.setToolTip("停止任务")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_requested)
        chips.addWidget(self.stop_button)
        self.stop_button.hide()
        composer_layout.addLayout(chips)

        workspace = QHBoxLayout()
        workspace.setContentsMargins(0, 0, 0, 0)
        workspace.setSpacing(8)
        workspace_label = QLabel("工作区")
        workspace_label.setObjectName("workspaceLabel")
        workspace.addWidget(workspace_label)
        self.project_edit = QLineEdit()
        self.project_edit.setObjectName("workspacePath")
        self.project_edit.setPlaceholderText(r"E:\projects\my-app")
        self.project_edit.setFixedHeight(32)
        self.project_edit.editingFinished.connect(
            lambda: self.project_changed.emit(self.project_edit.text().strip())
        )
        workspace.addWidget(self.project_edit, 1)
        self.browse_button = QPushButton("更换")
        self.browse_button.setObjectName("toolButton")
        self.browse_button.clicked.connect(self.browse_requested)
        workspace.addWidget(self.browse_button)
        self.init_button = QPushButton("初始化")
        self.init_button.setObjectName("toolButton")
        self.init_button.setToolTip("在当前项目执行 dual-agent init")
        self.init_button.clicked.connect(self.init_requested)
        workspace.addWidget(self.init_button)
        layout.addLayout(workspace)
        layout.addStretch()

        self._update_description_height()
        QTimer.singleShot(0, self._update_description_height)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.description_edit:
            if event.type() == QEvent.Type.FocusIn:
                self._set_composer_focused(True)
            elif event.type() == QEvent.Type.FocusOut:
                self._set_composer_focused(False)
            elif event.type() == QEvent.Type.KeyPress:
                key_event = cast(QKeyEvent, event)
                if (
                    key_event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}
                    and not key_event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                    and key_event.text() in {"\r", "\n"}
                    and self.start_button.isVisible()
                    and self.start_button.isEnabled()
                ):
                    self.start_requested.emit()
                    return True
        return super().eventFilter(watched, event)

    def _set_composer_focused(self, focused: bool) -> None:
        self.composer.setProperty("focused", "true" if focused else "false")
        style = self.composer.style()
        style.unpolish(self.composer)
        style.polish(self.composer)
        self.composer.update()

    def _update_description_height(self) -> None:
        line_height = self.description_edit.fontMetrics().lineSpacing()
        minimum = max(44, line_height + 18)
        maximum = min(200, minimum + 7 * line_height)
        visual_lines = self.description_edit.document().documentLayout().documentSize().height()
        document_height = ceil(visual_lines * line_height) + 18
        height = max(minimum, min(maximum, document_height))
        if self.description_edit.height() != height:
            self.description_edit.setFixedHeight(height)
        policy = (
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
            if document_height > maximum
            else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        if self.description_edit.verticalScrollBarPolicy() != policy:
            self.description_edit.setVerticalScrollBarPolicy(policy)

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

    def clear_description(self) -> None:
        self.description_edit.clear()

    def brain(self) -> str:
        return str(self.brain_combo.currentData())

    def executor(self) -> str:
        return str(self.executor_combo.currentData())

    def max_retries(self) -> int:
        return self.retry_spin.value()

    def set_running(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.start_button.setVisible(not running)
        self.stop_button.setEnabled(running)
        self.stop_button.setVisible(running)
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
