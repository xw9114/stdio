from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import datetime, timezone

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

from app.models.task import AgentTask
from app.ui.history_panel import HistoryPanel, _relative_time

pytestmark = pytest.mark.skipif(os.name != "nt", reason="uses real QWidgets on Windows")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "未知时间"),
        ("2026-09-30T14:59:30+00:00", "刚刚"),
        ("2026-09-30T14:48:00+00:00", "12 分钟前"),
        ("2026-09-29T14:03:00+00:00", "昨天 14:03"),
        ("2026-09-28T09:00:00+00:00", "2026-09-28"),
        ("not-a-time", "未知时间"),
    ],
)
def test_relative_time_boundaries(value: str | None, expected: str) -> None:
    now = datetime(2026, 9, 30, 15, 0, tzinfo=timezone.utc)
    assert _relative_time(value, now) == expected


@pytest.fixture
def history_panel() -> Iterator[HistoryPanel]:
    panel = HistoryPanel()
    panel.resize(248, 560)
    panel.show()
    QApplication.processEvents()
    yield panel
    panel.close()


def _task(description: str, status: str = "passed") -> AgentTask:
    return AgentTask(
        description=description,
        project_path="C:\\project",
        brain="claude",
        executor="codex",
        max_retries=3,
        status=status,
        started_at="2026-09-30T14:48:00+00:00",
    )


def test_set_history_populates_thread_list(history_panel: HistoryPanel) -> None:
    tasks = [_task("修复登录问题"), _task("补充测试", "failed")]
    history_panel.set_history(tasks)

    items = history_panel.task_items()
    assert [item.data(Qt.ItemDataRole.UserRole) for item in items] == tasks
    assert all(history_panel.list_widget.itemWidget(item) is not None for item in items)
    # One project heading above both tasks.
    assert history_panel.list_widget.count() == len(tasks) + 1


def test_history_is_grouped_by_project_and_groups_fold(history_panel: HistoryPanel) -> None:
    first, second, third = _task("a"), _task("b"), _task("c")
    second.project_path = "E:/work/other-app/"
    history_panel.set_history([first, second, third])

    labels = [
        history_panel.list_widget.itemWidget(history_panel.list_widget.item(row)).findChild(QLabel, "projectGroupName")
        for row in range(history_panel.list_widget.count())
    ]
    names = [label.text() for label in labels if label is not None]
    assert names == ["project", "other-app"]
    assert [item.data(Qt.ItemDataRole.UserRole) for item in history_panel.task_items()] == [first, third, second]

    heading = history_panel.list_widget.item(0)
    history_panel._on_clicked(heading)
    assert history_panel.list_widget.item(1).isHidden() and history_panel.list_widget.item(2).isHidden()
    assert not history_panel.list_widget.item(4).isHidden(), "other projects stay open"
    history_panel._on_clicked(heading)
    assert not history_panel.list_widget.item(1).isHidden()


def test_sidebar_buttons_emit_requested_signals(history_panel: HistoryPanel) -> None:
    requested: list[str] = []
    history_panel.new_task_requested.connect(lambda: requested.append("new"))
    history_panel.environment_requested.connect(lambda: requested.append("environment"))
    history_panel.settings_requested.connect(lambda: requested.append("settings"))

    history_panel.new_task_button.click()
    history_panel.environment_button.click()
    history_panel.settings_button.click()

    assert requested == ["new", "environment", "settings"]


def test_clear_selection_does_not_emit_task_selected(history_panel: HistoryPanel) -> None:
    task = _task("修复登录问题")
    history_panel.set_history([task])
    selected: list[AgentTask] = []
    history_panel.task_selected.connect(selected.append)

    history_panel.list_widget.setCurrentItem(history_panel.task_items()[0])
    assert selected == [task]

    history_panel.clear_selection()
    assert history_panel.list_widget.currentRow() == -1
    assert not history_panel.list_widget.selectedItems()
    assert selected == [task]


def test_thread_items_tell_repeated_goals_apart() -> None:
    from PySide6.QtWidgets import QLabel

    from app.ui.history_panel import _ThreadItem, _compact_duration

    assert _compact_duration("2026-10-01T07:00:00+00:00", "2026-10-01T07:00:45+00:00") == "45 秒"
    assert _compact_duration("2026-10-01T07:00:00+00:00", "2026-10-01T07:11:20+00:00") == "11 分钟"
    assert _compact_duration("2026-10-01T07:00:00+00:00", "2026-10-01T08:05:00+00:00") == "1 小时 5 分"
    assert _compact_duration(None, "2026-10-01T07:00:00+00:00") == ""

    task = AgentTask(
        "给我做一个跑酷小游戏", "E:/t", "claude", "codex", 3,
        status="blocked", mode="single",
        started_at="2026-10-01T07:00:00+00:00", finished_at="2026-10-01T07:11:20+00:00",
    )
    item = _ThreadItem(task)
    assert item.detail_text.startswith("阻塞 · ")
    assert item.detail_text.endswith(" · 11 分钟 · 单 agent")


def test_projects_sharing_a_folder_name_stay_apart(history_panel: HistoryPanel) -> None:
    first, second, third = _task("a"), _task("b"), _task("c")
    first.project_path, second.project_path, third.project_path = "E:/a/app", "E:/b/app", "e:/A/app/"
    history_panel.set_history([first, second, third])
    names = [
        label.text()
        for row in range(history_panel.list_widget.count())
        if (widget := history_panel.list_widget.itemWidget(history_panel.list_widget.item(row))) is not None
        and (label := widget.findChild(QLabel, "projectGroupName")) is not None
    ]
    assert names == ["app · a", "app · b"]
    assert [item.data(Qt.ItemDataRole.UserRole) for item in history_panel.task_items()] == [first, third, second]
