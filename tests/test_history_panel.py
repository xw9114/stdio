from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import datetime, timezone

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

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

    assert history_panel.list_widget.count() == len(tasks)
    assert history_panel.list_widget.itemWidget(history_panel.list_widget.item(0)) is not None


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

    history_panel.list_widget.setCurrentRow(0)
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
    item = _ThreadItem(task)  # keep a reference: its labels die with it
    second_line = item.findChild(QLabel, "threadItemTime").text()
    assert second_line.startswith("阻塞 · ")
    assert second_line.endswith(" · 11 分钟 · 单 agent")
