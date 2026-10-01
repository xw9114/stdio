from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.models.settings import AppSettings
from app.ui.task_panel import TaskPanel

pytestmark = pytest.mark.skipif(os.name != "nt", reason="uses real QWidgets on Windows")


@pytest.fixture
def task_panel() -> Iterator[TaskPanel]:
    panel = TaskPanel()
    panel.resize(620, 330)
    panel.show()
    QApplication.processEvents()
    yield panel
    panel.close()


def test_enter_sends_once_and_shift_enter_inserts_newline(task_panel: TaskPanel) -> None:
    sent: list[bool] = []
    task_panel.start_requested.connect(lambda: sent.append(True))
    task_panel.description_edit.setPlainText("第一行")
    task_panel.description_edit.setFocus()

    QTest.keyClick(task_panel.description_edit, Qt.Key.Key_Return)
    assert sent == [True]
    assert task_panel.description_edit.toPlainText() == "第一行"

    QTest.keyClick(
        task_panel.description_edit,
        Qt.Key.Key_Return,
        Qt.KeyboardModifier.ShiftModifier,
    )
    assert sent == [True]
    assert "\n" in task_panel.description_edit.toPlainText()


def test_running_state_switches_buttons(task_panel: TaskPanel) -> None:
    assert not task_panel.start_button.isHidden()
    assert task_panel.stop_button.isHidden()

    task_panel.set_running(True)
    assert task_panel.start_button.isHidden()
    assert not task_panel.stop_button.isHidden()
    assert not task_panel.start_button.isEnabled()
    assert task_panel.stop_button.isEnabled()

    task_panel.set_running(False)
    assert not task_panel.start_button.isHidden()
    assert task_panel.stop_button.isHidden()


def test_composer_focus_property_tracks_editor_focus(task_panel: TaskPanel) -> None:
    task_panel.description_edit.setFocus()
    QApplication.processEvents()
    assert task_panel.composer.property("focused") == "true"

    task_panel.project_edit.setFocus()
    QApplication.processEvents()
    assert task_panel.composer.property("focused") == "false"


def test_settings_and_clear_description_keep_public_api(task_panel: TaskPanel) -> None:
    settings = AppSettings(
        project_path="C:\\project",
        default_brain="codex",
        default_executor="claude",
        default_max_retries=4,
        auto_detect_roles=False,
    )
    task_panel.apply_settings(settings)

    assert task_panel.project_path() == settings.project_path
    assert task_panel.brain() == settings.default_brain
    assert task_panel.executor() == settings.default_executor
    assert task_panel.max_retries() == settings.default_max_retries

    task_panel.description_edit.setPlainText("修复登录问题")
    task_panel.clear_description()
    assert task_panel.description() == ""


def test_description_grows_then_scrolls_after_eight_lines(task_panel: TaskPanel) -> None:
    initial_height = task_panel.description_edit.height()
    task_panel.description_edit.setPlainText("\n".join(["一行"] * 8))
    QApplication.processEvents()
    eight_line_height = task_panel.description_edit.height()

    assert eight_line_height > initial_height
    assert eight_line_height <= 200
    assert (
        task_panel.description_edit.verticalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )

    task_panel.description_edit.setPlainText("\n".join(["一行"] * 9))
    QApplication.processEvents()

    assert task_panel.description_edit.height() <= 200
    assert task_panel.description_edit.verticalScrollBar().maximum() > 0


def test_composer_row_fits_narrow_and_wide_columns(task_panel: TaskPanel) -> None:
    """Regression test: at the 900px minimum window width with the inspector
    open the chat column is ~420px. A row of every option chip needed ~600px
    and pushed the send button out of view; the options now live in a
    popover behind one summary button, so the row fits either way."""

    def fully_visible(widget) -> bool:
        return widget.isVisible() and widget.visibleRegion().boundingRect() == widget.rect()

    for width in (370, 1000):
        task_panel.resize(width, 330)
        QApplication.processEvents()
        assert fully_visible(task_panel.start_button), width
        assert fully_visible(task_panel.mode_combo), width
        assert task_panel.options_button.isVisible(), width
        assert not task_panel.scroll_area.horizontalScrollBar().isVisible(), width


def test_options_live_in_a_popover_summarised_on_the_button(task_panel: TaskPanel) -> None:
    task_panel.resize(1000, 330)
    QApplication.processEvents()
    assert not task_panel.brain_combo.isVisible(), "options are not in the row"

    task_panel.retry_spin.setValue(5)
    task_panel.confirm_plan_checkbox.setChecked(True)
    summary = task_panel.options_button.toolTip()
    assert summary == f"{task_panel.brain_combo.currentText()} → {task_panel.executor_combo.currentText()} · 最多返工 5 次 · 先确认计划"
    assert task_panel.options_button.text().endswith("▾")

    task_panel.options_button.click()
    QApplication.processEvents()
    assert task_panel.options_popup.isVisible()
    assert task_panel.brain_combo.isVisible()
    task_panel.options_popup.hide()

    task_panel.mode_combo.setCurrentIndex(task_panel.mode_combo.findData("single"))
    assert task_panel.options_button.toolTip() == f"{task_panel.executor_combo.currentText()} 单独执行"


def test_single_agent_mode_disables_what_it_does_not_use(task_panel: TaskPanel) -> None:
    task_panel.confirm_plan_checkbox.setChecked(True)
    task_panel.mode_combo.setCurrentIndex(task_panel.mode_combo.findData("single"))

    assert task_panel.mode() == "single"
    assert not task_panel.brain_combo.isEnabled()
    assert not task_panel.retry_spin.isEnabled()
    assert not task_panel.confirm_plan_checkbox.isEnabled()
    assert task_panel.confirm_plan() is False
    assert task_panel.executor_combo.isEnabled()

    task_panel.set_running(True)
    assert not task_panel.mode_combo.isEnabled()
    task_panel.set_running(False)
    assert task_panel.mode_combo.isEnabled()
    assert not task_panel.brain_combo.isEnabled(), "still single-agent after a run"

    task_panel.mode_combo.setCurrentIndex(task_panel.mode_combo.findData("dual"))
    assert task_panel.brain_combo.isEnabled()
    assert task_panel.confirm_plan() is True


def test_mode_is_restored_from_settings(task_panel: TaskPanel) -> None:
    task_panel.apply_settings(AppSettings(run_mode="single"))
    assert task_panel.mode() == "single"
    assert not task_panel.brain_combo.isEnabled()
