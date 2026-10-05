from __future__ import annotations

from math import ceil
from pathlib import PureWindowsPath
from typing import cast

from PySide6.QtCore import QEvent, QObject, QPoint, QSize, QTimer, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.constants import BRAIN_OPTIONS, EXECUTOR_OPTIONS, RUN_MODES
from app.core.natural_language_parser import NaturalLanguageParser
from app.models.settings import AppSettings
from app.ui.icons import icon
from app.ui.shadow import ShadowSurface
from app.ui.theme import TEXT_MUTED


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

        # The window may leave less height than an eight-line draft needs;
        # the host scrolls rather than letting the rows overlap.
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("composerScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer_layout.addWidget(self.scroll_area)

        # Paints the composer's soft shadow; the side and bottom margins are
        # the room it spreads into.
        content = ShadowSurface()
        content.setObjectName("composerContent")
        self._surface = content
        self.scroll_area.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        layout.setContentsMargins(16, 8, 16, 18)
        layout.setSpacing(8)

        # Context chips above the prompt box, as in desktop agent apps: which
        # project the task runs in (click to change) and its one-off setup.
        self._project_path = ""
        context = QHBoxLayout()
        context.setContentsMargins(0, 0, 0, 0)
        context.setSpacing(6)
        self.browse_button = QPushButton()
        self.browse_button.setObjectName("contextChip")
        self.browse_button.setIcon(icon("folder", TEXT_MUTED, 15))
        self.browse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.browse_button.clicked.connect(self.browse_requested)
        context.addWidget(self.browse_button)
        self.init_button = QPushButton("初始化")
        self.init_button.setObjectName("contextChip")
        self.init_button.setIcon(icon("refresh", TEXT_MUTED, 15))
        self.init_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.init_button.setToolTip("在当前项目执行 dual-agent init（生成配置，必要时初始化 Git）")
        self.init_button.clicked.connect(self.init_requested)
        context.addWidget(self.init_button)
        context.addStretch()
        layout.addLayout(context)
        self._show_project_path()

        self.composer = QFrame()
        self.composer.setObjectName("composer")
        self.composer.setProperty("focused", "false")
        composer_layout = QVBoxLayout(self.composer)
        composer_layout.setContentsMargins(12, 10, 12, 10)
        composer_layout.setSpacing(8)
        layout.addWidget(self.composer)
        content.add_shadow(self.composer, 14)

        self.description_edit = QPlainTextEdit()
        self.description_edit.setObjectName("composerInput")
        self.description_edit.setPlaceholderText("描述任务和验收要求，Enter 发送，Shift+Enter 换行")
        self.description_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.description_edit.installEventFilter(self)
        self.description_edit.textChanged.connect(lambda: self._parse_timer.start())
        self.description_edit.document().contentsChanged.connect(self._update_description_height)
        self.description_edit.document().documentLayout().documentSizeChanged.connect(
            lambda _size: self._update_description_height()
        )
        composer_layout.addWidget(self.description_edit)

        # One quiet row under the prompt: the run mode, a summary button that
        # opens the agent options in a popover, and send/stop. With Brain,
        # Executor, retries and two checkboxes out of the row the composer
        # reads as a prompt box rather than a form, and the row fits the
        # ~420px chat column of the minimum window with the inspector open.
        chips = QHBoxLayout()
        chips.setContentsMargins(0, 0, 0, 0)
        chips.setSpacing(6)
        self._running = False

        self.mode_combo = _chip_combo()
        self.mode_combo.setObjectName("flatChip")
        for index, run_mode in enumerate(RUN_MODES):
            self.mode_combo.addItem(run_mode.label, run_mode.key)
            self.mode_combo.setItemData(index, run_mode.description, Qt.ItemDataRole.ToolTipRole)
        self.mode_combo.currentIndexChanged.connect(lambda _index: self._apply_mode())
        chips.addWidget(self.mode_combo)

        # A QPushButton, not a QToolButton: its label can be left-aligned in
        # the stylesheet, so the summary sits next to the mode picker. It
        # takes the free width and elides its text when the column narrows.
        self.options_button = QPushButton()
        self.options_button.setObjectName("optionsButton")
        self.options_button.setToolTip("Brain、Executor、返工次数和其他选项")
        self.options_button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.options_button.setMinimumWidth(60)
        self.options_button.clicked.connect(self._show_options)
        self.options_button.installEventFilter(self)
        chips.addWidget(self.options_button, 1)

        self.start_button = QPushButton()
        self.start_button.setObjectName("sendButton")
        self.start_button.setFixedSize(32, 32)
        self.start_button.setIcon(icon("send", "#ffffff", 16))
        self.start_button.setToolTip("发送 (Enter)")
        self.start_button.clicked.connect(self.start_requested)
        chips.addWidget(self.start_button)

        self.stop_button = QPushButton()
        self.stop_button.setObjectName("stopButton")
        self.stop_button.setFixedSize(32, 32)
        self.stop_button.setIcon(icon("stop", "#ffffff", 14))
        self.stop_button.setToolTip("停止任务")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_requested)
        chips.addWidget(self.stop_button)
        self.stop_button.hide()
        composer_layout.addLayout(chips)

        # The options popover: a frameless popup that closes on outside click.
        self.options_popup = QFrame(self, Qt.WindowType.Popup)
        self.options_popup.setObjectName("optionsPopup")
        options = QGridLayout(self.options_popup)
        options.setContentsMargins(14, 12, 14, 12)
        options.setHorizontalSpacing(10)
        options.setVerticalSpacing(8)

        brain_label = QLabel("Brain")
        brain_label.setObjectName("chipLabel")
        self._brain_label = brain_label
        self.brain_combo = _chip_combo("Brain")
        for option in BRAIN_OPTIONS:
            self.brain_combo.addItem(option.label, option.key)
        self.brain_combo.activated.connect(self._mark_brain_manual)
        options.addWidget(brain_label, 0, 0)
        options.addWidget(self.brain_combo, 0, 1)

        executor_label = QLabel("Executor")
        executor_label.setObjectName("chipLabel")
        self.executor_combo = _chip_combo("Executor")
        for option in EXECUTOR_OPTIONS:
            self.executor_combo.addItem(option.label, option.key)
        self.executor_combo.activated.connect(self._mark_executor_manual)
        options.addWidget(executor_label, 1, 0)
        options.addWidget(self.executor_combo, 1, 1)

        retry_label = QLabel("最多返工")
        retry_label.setObjectName("chipLabel")
        self.retry_spin = QSpinBox()
        self.retry_spin.setObjectName("chip")
        self.retry_spin.setRange(0, 20)
        self.retry_spin.setSuffix(" 次")
        self.retry_spin.editingFinished.connect(self._mark_retry_manual)
        options.addWidget(retry_label, 2, 0)
        options.addWidget(self.retry_spin, 2, 1)

        self.auto_detect_checkbox = QCheckBox("根据描述自动识别角色和返工次数")
        self.auto_detect_checkbox.toggled.connect(
            lambda checked: self._apply_inference() if checked else None
        )
        options.addWidget(self.auto_detect_checkbox, 3, 0, 1, 2)

        self.confirm_plan_checkbox = QCheckBox("先确认计划再修改代码")
        self.confirm_plan_checkbox.setToolTip(
            "Brain 规划完先停下，确认、删减任务或回答问题后再开始修改代码"
        )
        options.addWidget(self.confirm_plan_checkbox, 4, 0, 1, 2)

        for signal in (
            self.brain_combo.currentIndexChanged,
            self.executor_combo.currentIndexChanged,
            self.retry_spin.valueChanged,
            self.confirm_plan_checkbox.toggled,
        ):
            signal.connect(lambda *_: self._update_options_summary())

        layout.addStretch()

        self._update_description_height()
        QTimer.singleShot(0, self._update_description_height)
        self._update_options_summary()

    def sizeHint(self) -> QSize:
        # A scroll area's own hint ignores its content; use the content's, so
        # the composer takes the height it needs and no blank band below it.
        content = self.scroll_area.widget().sizeHint()
        return QSize(content.width(), content.height() + 2)

    def _options_summary(self) -> str:
        executor = self.executor_combo.currentText()
        if self.mode() == "single":
            return f"{executor} 单独执行"
        summary = f"{self.brain_combo.currentText()} → {executor} · 最多返工 {self.retry_spin.value()} 次"
        return summary + (" · 先确认计划" if self.confirm_plan_checkbox.isChecked() else "")

    def _update_options_summary(self) -> None:
        # Elided to the button's width; the full text stays in the tooltip.
        text = self._options_summary()
        width = max(20, self.options_button.width() - 28)
        self.options_button.setText(
            self.options_button.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, width) + "  ▾"
        )
        self.options_button.setToolTip(text)

    def _show_options(self) -> None:
        popup = self.options_popup
        popup.adjustSize()
        anchor = self.options_button.mapToGlobal(QPoint(0, 0))
        popup.move(anchor.x(), anchor.y() - popup.height() - 6)
        popup.show()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        # The description editor is filtered from early in __init__, before
        # the options button exists, so it is matched first.
        if watched is not self.description_edit:
            if watched is self.options_button and event.type() == QEvent.Type.Resize:
                self._update_options_summary()
            return super().eventFilter(watched, event)
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
            # The panel is sized to its content (sizeHint), so the window
            # re-lays out as the draft grows.
            self.updateGeometry()
        policy = (
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
            if document_height > maximum
            else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        if self.description_edit.verticalScrollBarPolicy() != policy:
            self.description_edit.setVerticalScrollBarPolicy(policy)

    def _show_project_path(self) -> None:
        path = self._project_path
        # Windows path parsing also accepts forward slashes.
        name = (PureWindowsPath(path.rstrip("\\/")).name or path) if path else "选择项目文件夹"
        self.browse_button.setText(name)
        self.browse_button.setToolTip(f"{path}\n点击更换项目" if path else "选择任务要修改的项目文件夹")

    def apply_settings(self, settings: AppSettings) -> None:
        self._project_path = settings.project_path.strip()
        self._show_project_path()
        self._set_combo_value(self.brain_combo, settings.default_brain)
        self._set_combo_value(self.executor_combo, settings.default_executor)
        self.retry_spin.setValue(settings.default_max_retries)
        self.auto_detect_checkbox.setChecked(settings.auto_detect_roles)
        self.confirm_plan_checkbox.setChecked(settings.confirm_plan)
        self._set_combo_value(self.mode_combo, settings.run_mode)
        self._apply_mode()
        self._brain_manual = False
        self._executor_manual = False
        self._retry_manual = False

    def set_project_path(self, path: str) -> None:
        self._project_path = path.strip()
        self._show_project_path()
        self.project_changed.emit(self._project_path)

    def project_path(self) -> str:
        return self._project_path

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
        self.executor_combo.setEnabled(not running)
        self.mode_combo.setEnabled(not running)
        self._running = running
        self._apply_mode()

    def mode(self) -> str:
        return str(self.mode_combo.currentData())

    def confirm_plan(self) -> bool:
        # A single-agent run has no plan to confirm.
        return self.mode() != "single" and self.confirm_plan_checkbox.isChecked()

    def _apply_mode(self) -> None:
        # Brain, retries and plan confirmation only exist when the Brain takes
        # part; disabling them shows what a single-agent run leaves out.
        dual = self.mode() != "single"
        editable = not self._running
        self._brain_label.setEnabled(dual)
        for widget in (self.brain_combo, self.retry_spin, self.confirm_plan_checkbox):
            widget.setEnabled(dual and editable)
        self.options_button.setEnabled(editable)
        # Sized to the current mode's label rather than the longest one (the
        # style also reserves room for an arrow), so the summary sits right
        # next to it.
        label_width = self.mode_combo.fontMetrics().horizontalAdvance(self.mode_combo.currentText())
        self.mode_combo.setFixedWidth(label_width + 22)
        self._update_options_summary()

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


class _ChipCombo(QComboBox):
    """A combo that prefers its full text width but may shrink below it.

    QComboBox's minimum width is the width of its longest item, so two
    agent pickers alone could not fit a narrow chat column. The full label
    stays available as a tooltip when the text is clipped."""

    _MINIMUM_WIDTH = 96

    def minimumSizeHint(self) -> QSize:
        hint = super().minimumSizeHint()
        return QSize(min(hint.width(), self._MINIMUM_WIDTH), hint.height())


def _chip_combo(role: str = "") -> QComboBox:
    combo = _ChipCombo()
    combo.setObjectName("chip")
    combo.currentTextChanged.connect(
        lambda text: combo.setToolTip(f"{role}：{text}" if role else text)
    )
    return combo
