from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)

from app.constants import BRAIN_OPTIONS, EXECUTOR_OPTIONS
from app.models.settings import AppSettings
from app.ui.wallpaper import BLUR_LEVELS, IMAGE_FILTER, PRESETS, is_preset, preset_value

# Called with (wallpaper, blur level, veil percent) while the dialog is open.
AppearancePreview = Callable[[str, int, int], None]


class SettingsDialog(QDialog):
    def __init__(
        self,
        settings: AppSettings,
        parent=None,  # type: ignore[no-untyped-def]
        preview: AppearancePreview | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(620)
        self._settings = replace(settings)
        self._preview = preview
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        layout.addWidget(_section("运行"))
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
        self.notify_check = QCheckBox("任务结束时通知（Studio 不在前台时）")
        self.notify_check.setChecked(settings.notify_on_finish)
        form.addRow("", self.notify_check)
        self.keep_awake_check = QCheckBox("任务运行期间阻止电脑睡眠")
        self.keep_awake_check.setToolTip("电脑睡眠会让正在运行的 Brain 和 Executor 中断；任务结束后自动恢复")
        self.keep_awake_check.setChecked(settings.keep_awake)
        form.addRow("", self.keep_awake_check)
        layout.addLayout(form)

        layout.addWidget(_section("外观"))
        appearance = QFormLayout()
        wallpaper_row = QHBoxLayout()
        self.wallpaper_combo = QComboBox()
        self.wallpaper_combo.addItem("无壁纸", "")
        for preset in PRESETS:
            self.wallpaper_combo.addItem(f"渐变 · {preset.label}", preset_value(preset.key))
        if settings.wallpaper and not is_preset(settings.wallpaper):
            self._add_image_item(settings.wallpaper)
        _set_combo(self.wallpaper_combo, settings.wallpaper)
        self.wallpaper_combo.currentIndexChanged.connect(lambda _index: self._appearance_changed())
        wallpaper_row.addWidget(self.wallpaper_combo, 1)
        choose_image = QPushButton("选择图片…")
        choose_image.clicked.connect(self._choose_image)
        wallpaper_row.addWidget(choose_image)
        appearance.addRow("壁纸", wallpaper_row)

        self.blur_slider, self._blur_label, blur_row = _slider(0, 3, 1, settings.wallpaper_blur)
        self.blur_slider.valueChanged.connect(lambda _value: self._appearance_changed())
        appearance.addRow("图片模糊", blur_row)
        self.veil_slider, self._veil_label, veil_row = _slider(0, 90, 5, settings.wallpaper_veil)
        self.veil_slider.valueChanged.connect(lambda _value: self._appearance_changed())
        appearance.addRow("遮罩浓度", veil_row)
        hint = QLabel("遮罩是盖在壁纸上的一层半透明浅色。深色图片会自动加深到文字清晰为止，这里调的是在此之上再加多少。")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        appearance.addRow("", hint)
        layout.addLayout(appearance)
        self._update_appearance_labels()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        save.setText("保存")
        save.setObjectName("primaryButton")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
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
        self._settings.notify_on_finish = self.notify_check.isChecked()
        self._settings.keep_awake = self.keep_awake_check.isChecked()
        self._settings.wallpaper = str(self.wallpaper_combo.currentData() or "")
        self._settings.wallpaper_blur = self.blur_slider.value()
        self._settings.wallpaper_veil = self.veil_slider.value()
        return self._settings

    def _add_image_item(self, path: str) -> None:
        index = self.wallpaper_combo.findData(path)
        if index < 0:
            self.wallpaper_combo.addItem(f"图片 · {Path(path).name}", path)
            index = self.wallpaper_combo.count() - 1
            self.wallpaper_combo.setItemData(index, path, Qt.ItemDataRole.ToolTipRole)
        self.wallpaper_combo.setCurrentIndex(index)

    def _choose_image(self) -> None:
        current = str(self.wallpaper_combo.currentData() or "")
        start = str(Path(current).parent) if current and not is_preset(current) else str(Path.home() / "Pictures")
        filename, _selected = QFileDialog.getOpenFileName(self, "选择壁纸图片", start, IMAGE_FILTER)
        if filename:
            self._add_image_item(filename)

    def _appearance_changed(self) -> None:
        self._update_appearance_labels()
        if self._preview is not None:
            self._preview(
                str(self.wallpaper_combo.currentData() or ""),
                self.blur_slider.value(),
                self.veil_slider.value(),
            )

    def _update_appearance_labels(self) -> None:
        wallpaper = str(self.wallpaper_combo.currentData() or "")
        # Blur only applies to photos; the gradients are soft already.
        self.blur_slider.setEnabled(bool(wallpaper) and not is_preset(wallpaper))
        self.veil_slider.setEnabled(bool(wallpaper))
        self._blur_label.setText(BLUR_LEVELS[self.blur_slider.value()])
        self._veil_label.setText(f"{self.veil_slider.value()}%")

    def _browse(self) -> None:
        filename, _selected = QFileDialog.getOpenFileName(
            self,
            "选择 dual-agent.cmd",
            self.path_edit.text(),
            "Command files (*.cmd);;All files (*)",
        )
        if filename:
            self.path_edit.setText(filename)


def _section(title: str) -> QLabel:
    label = QLabel(title)
    label.setObjectName("sectionTitle")
    return label


def _slider(minimum: int, maximum: int, step: int, value: int) -> tuple[QSlider, QLabel, QHBoxLayout]:
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(minimum, maximum)
    slider.setSingleStep(step)
    slider.setPageStep(step)
    slider.setValue(value)
    label = QLabel()
    label.setObjectName("muted")
    label.setMinimumWidth(56)
    row = QHBoxLayout()
    row.addWidget(slider, 1)
    row.addWidget(label)
    return slider, label, row


def _set_combo(combo: QComboBox, value: str) -> None:
    index = combo.findData(value)
    if index >= 0:
        combo.setCurrentIndex(index)
