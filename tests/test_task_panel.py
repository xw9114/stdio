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
