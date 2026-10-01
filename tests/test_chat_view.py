from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel

from app.core.task_state import StateSnapshot, TaskPhase
from app.models.task import AgentTask
from app.ui.chat_view import ChatView, _StepCard

pytestmark = pytest.mark.skipif(os.name != "nt", reason="uses real QWidgets on Windows")


@pytest.fixture
def chat_view() -> Iterator[ChatView]:
    view = ChatView()
    view.resize(900, 650)
    view.show()
    QApplication.processEvents()
    yield view
    view.close()


def test_empty_state_hides_for_user_message_and_returns_after_clear(chat_view: ChatView) -> None:
    title = chat_view.findChild(QLabel, "emptyStateTitle")
    assert title is not None
    assert title.isVisible()
    assert chat_view.message_count() == 0

    chat_view.add_user_message("修复登录问题", "Claude Code CLI → Codex CLI · 最多返工 3 次")
    QApplication.processEvents()

    assert not title.isVisible()
    assert chat_view.message_count() == 1

    chat_view.clear()
    QApplication.processEvents()

    assert title.isVisible()
    assert chat_view.message_count() == 0


def test_phase_transitions_create_distinct_cards_without_polling_duplicates(
    chat_view: ChatView,
) -> None:
    planning = StateSnapshot(TaskPhase.PLANNING, "Brain 正在分析并制定计划")
    executing = StateSnapshot(TaskPhase.EXECUTING, "Executor 正在修改并验证", 1)
    reviewing = StateSnapshot(TaskPhase.REVIEWING, "Brain 正在验收修改", 1)

    for snapshot in (planning, executing, reviewing):
        chat_view.set_phase(snapshot)
        chat_view.set_phase(snapshot)

    cards = chat_view.findChildren(_StepCard)
    assert len(cards) == 3
    assert chat_view.message_count() == 3
    assert [card.state for card in cards] == ["done", "done", "active"]
    assert cards[1].header.text() == executing.message
    assert cards[1].line_count() == 0

    chat_view.set_phase(StateSnapshot(TaskPhase.PASSED, "所有任务已通过验收"))
    assert cards[2].state == "done"


def test_log_without_phase_creates_card_and_stderr_does_not_fail_it(chat_view: ChatView) -> None:
    chat_view.append_log("Executor", "开始处理")
    QApplication.processEvents()

    cards = chat_view.findChildren(_StepCard)
    assert len(cards) == 1
    assert cards[0].header.text() == "准备中"
    assert cards[0].line_count() == 1
    assert cards[0].state == "active"
    assert not cards[0].log.isVisible()

    cards[0].header.click()
    assert cards[0].log.isVisible()
    chat_view.append_log("Error", "执行失败")
    assert cards[0].line_count() == 2
    # stderr lines are recorded but do not decide failure (agents write
    # routine warnings there); the blocked/failed phase or result does.
    assert cards[0].state == "active"
    chat_view.set_phase(StateSnapshot(TaskPhase.FAILED, "任务执行失败"))
    assert cards[0].state == "failed"


def test_result_adds_card_with_shared_metrics_and_diff_signal(chat_view: ChatView) -> None:
    chat_view.set_phase(StateSnapshot(TaskPhase.EXECUTING, "Executor 正在修改并验证", 1))
    task = AgentTask(
        description="修复登录问题",
        project_path="C:\\project",
        brain="claude",
        executor="codex",
        max_retries=3,
        status=TaskPhase.PASSED.value,
        started_at="2026-09-30T10:00:00+00:00",
        finished_at="2026-09-30T10:01:05+00:00",
        result_summary="登录测试已通过。",
    )
    payload = {
        "tasks": [
            {
                "attempts": [
                    {"execution": {"filesChanged": ["app/login.py"]}},
                    {"execution": {"filesChanged": ["app/login.py", "tests/test_login.py"]}},
                ]
            }
        ]
    }
    before = chat_view.message_count()
    requested: list[bool] = []
    chat_view.show_diff_requested.connect(lambda: requested.append(True))

    chat_view.add_result(task, payload)

    assert chat_view.message_count() == before + 1
    assert chat_view.findChildren(_StepCard)[0].state == "done"
    assert any(label.text() == "✓ 任务完成" for label in chat_view.findChildren(QLabel))
    assert any(
        label.text() == "耗时 1 分 5 秒 · 返工 1 · 修改文件 2"
        for label in chat_view.findChildren(QLabel)
    )
    result = chat_view._messages[-1]
    result.diff_button.click()
    assert requested == [True]


def test_new_messages_preserve_manual_scroll_position(chat_view: ChatView) -> None:
    chat_view.resize(900, 300)
    for index in range(20):
        chat_view.add_user_message(f"任务消息 {index}")
    QApplication.processEvents()

    scrollbar = chat_view.scroll_area.verticalScrollBar()
    assert scrollbar.maximum() > 40
    scrollbar.setValue(0)
    chat_view.add_user_message("新消息")
    QApplication.processEvents()

    assert scrollbar.value() == 0

    scrollbar.setValue(scrollbar.maximum())
    chat_view.add_user_message("底部消息")
    QApplication.processEvents()

    assert scrollbar.value() == scrollbar.maximum()


def test_plan_card_shows_the_route_and_why(chat_view: ChatView) -> None:
    chat_view.add_plan(
        {
            "route": "reviewed",
            "routeReason": "一个会话就能完成的小游戏",
            "summary": "s",
            "questions": [],
            "tasks": [{"id": "T1", "title": "Whole game"}],
        }
    )
    QApplication.processEvents()
    texts = [label.text() for label in chat_view.findChildren(QLabel, "planRoute")]
    assert texts == ["路线：执行后验收 — 一个会话就能完成的小游戏"]
