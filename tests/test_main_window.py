from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QFrame, QMessageBox

import app.utils.paths as paths_module
from app.core.task_state import TaskPhase, phase_from_status
from app.models.settings import AppSettings
from app.models.task import AgentTask
from app.services.settings_service import SettingsService
from app.ui.main_window import MainWindow, _parse_log_line

pytestmark = pytest.mark.skipif(os.name != "nt", reason="uses a Windows .cmd shim and real QWidgets")


def _write_success_shim(path: Path, goal: str) -> None:
    path.write_text(
        "@echo off\r\n"
        'if "%1"=="run" goto :run\r\n'
        'if "%1"=="status" goto :status\r\n'
        "exit /b 1\r\n"
        "\r\n"
        ":run\r\n"
        "echo [dual-agent] Brain (claude) is planning...\r\n"
        "echo [dual-agent] Executor (codex) is running T1, attempt 1/3...\r\n"
        "echo [dual-agent] Brain is reviewing T1, attempt 1...\r\n"
        "echo [dual-agent] All tasks passed.\r\n"
        "exit /b 0\r\n"
        "\r\n"
        ":status\r\n"
        f'echo {{"status": "complete", "goal": "{goal}"}}\r\n'
        "exit /b 0\r\n",
        encoding="utf-8",
    )


def _isolate_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """MainWindow constructs SettingsService()/HistoryService() with no
    injected path, so without this a test would read AND OVERWRITE the real
    user's data/settings.json and data/history.json. Redirect
    data_directory() to a throwaway folder for the duration of the test.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(paths_module, "data_directory", lambda: data_dir)
    return data_dir


def _seed_settings(data_dir: Path, **overrides: object) -> None:
    SettingsService(data_dir / "settings.json").save(AppSettings(**overrides))  # type: ignore[arg-type]


def test_full_task_flow_updates_result_status_and_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end regression test for the wiring in main_window.py: starting
    a task from the UI must drive the status panel, the result panel, the
    log panel and persisted history all the way to a PASSED outcome, using
    the real OrchestratorClient/GitManager plumbing (only the orchestrator
    executable itself is faked).
    """
    data_dir = _isolate_data_dir(monkeypatch, tmp_path)
    orchestrator = tmp_path / "dual-agent.cmd"
    goal = "fix login bug"
    _write_success_shim(orchestrator, goal)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    _seed_settings(
        data_dir,
        orchestrator_path=str(orchestrator),
        project_path=str(project_dir),
        check_environment_on_start=False,
        auto_detect_roles=False,
    )

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.task_panel.description_edit.setPlainText(goal)

    finished_signals: list[tuple[int, object, bool]] = []
    window.client.task_finished.connect(
        lambda code, payload, cancelled: (
            finished_signals.append((code, payload, cancelled)),
            app.quit(),
        )
    )

    window._start_task()
    assert window.client.running

    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(app.quit)
    timeout.start(15000)  # safety timeout
    app.exec()
    timeout.stop()

    assert finished_signals, "orchestrator task never finished"
    assert window.current_task is None

    assert window.result_panel.values["status"].text() == TaskPhase.PASSED.value
    assert window.status_panel.final_stage.detail.text() == "通过"
    assert "all tasks passed" in window.log_panel.editor.toPlainText().lower()

    assert len(window.history) == 1
    assert window.history[0].status == TaskPhase.PASSED.value
    assert window.history[0].description == goal
    assert window.chat_view.message_count() >= 2
    assert window.task_panel.description() == ""
    assert len(window.chat_view.findChildren(QFrame, "stepCard")) == 3

    on_disk = json.loads((data_dir / "history.json").read_text(encoding="utf-8"))
    assert len(on_disk) == 1
    assert on_disk[0]["status"] == TaskPhase.PASSED.value

    window.close()


def test_unwritable_log_file_does_not_abort_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test: an OSError while creating the per-task log file used
    to escape _start_task() after the UI had already entered its running
    state, leaving the window stuck with no process behind it."""
    data_dir = _isolate_data_dir(monkeypatch, tmp_path)
    orchestrator = tmp_path / "dual-agent.cmd"
    goal = "fix login bug"
    _write_success_shim(orchestrator, goal)
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _seed_settings(
        data_dir,
        orchestrator_path=str(orchestrator),
        project_path=str(project_dir),
        check_environment_on_start=False,
        auto_detect_roles=False,
    )

    def _raise_disk_full() -> Path:
        raise OSError("disk full")

    monkeypatch.setattr("app.ui.main_window.logs_directory", _raise_disk_full)

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.task_panel.description_edit.setPlainText(goal)
    finished: list[int] = []
    window.client.task_finished.connect(lambda code, *_: (finished.append(code), app.quit()))

    window._start_task()
    assert window.client.running
    assert "disk full" in window.log_panel.editor.toPlainText()

    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(app.quit)
    timeout.start(15000)  # safety timeout
    app.exec()
    timeout.stop()

    assert finished == [0]
    assert window.history[0].status == TaskPhase.PASSED.value
    assert window.history[0].log_path is None

    window.close()


def test_start_task_with_missing_project_warns_without_touching_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = _isolate_data_dir(monkeypatch, tmp_path)
    orchestrator = tmp_path / "dual-agent.cmd"
    _write_success_shim(orchestrator, "anything")

    _seed_settings(
        data_dir,
        orchestrator_path=str(orchestrator),
        project_path=str(tmp_path / "does-not-exist"),
        check_environment_on_start=False,
    )

    warnings: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(
            lambda *args, **kwargs: (warnings.append(args), QMessageBox.StandardButton.Ok)[-1]
        ),
    )

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.task_panel.description_edit.setPlainText("do something")

    window._start_task()

    assert warnings, "expected a warning dialog for the missing project directory"
    assert not window.client.running
    assert window.current_task is None

    window.close()


def test_new_task_resets_chat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = _isolate_data_dir(monkeypatch, tmp_path)
    orchestrator = tmp_path / "dual-agent.cmd"
    _write_success_shim(orchestrator, "anything")
    _seed_settings(data_dir, orchestrator_path=str(orchestrator), check_environment_on_start=False)

    window = MainWindow()
    window.chat_view.add_user_message("旧任务")
    window.thread_title.set_full_text("旧任务")

    window._new_task()

    assert window.chat_view.message_count() == 0
    assert window.thread_title.text() == "新任务"
    window.close()


def test_status_polling_does_not_add_step_cards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test for duplicate step cards seen in a real run: the
    3-second `status --json` poll also emitted phase_changed, and a poll that
    lagged behind the log (still "executing" after the log moved on to
    review) or reported a between-tasks state the log never prints each
    opened an extra card. Step cards must follow the ordered log only."""
    data_dir = _isolate_data_dir(monkeypatch, tmp_path)
    orchestrator = tmp_path / "dual-agent.cmd"
    _write_success_shim(orchestrator, "anything")
    _seed_settings(data_dir, orchestrator_path=str(orchestrator), check_environment_on_start=False)

    window = MainWindow()
    window.current_task = AgentTask("t", str(tmp_path), "claude", "codex", 3)
    window._append_log("Process", "[dual-agent] Executor (codex) is running T1, attempt 1/3...")
    window._append_log("Process", "[dual-agent] Brain is reviewing T1, attempt 1...")
    assert len(window.chat_view.findChildren(QFrame, "stepCard")) == 2
    assert window.phase_pill.toolTip() == "Brain 正在验收修改"

    stale = {
        "status": "executing",
        "tasks": [{"status": "running", "attempts": [{"number": 1}]}],
    }
    between_tasks = {"status": "executing", "tasks": [{"status": "complete"}]}
    window.client.phase_changed.emit(phase_from_status(stale))
    window.client.phase_changed.emit(phase_from_status(between_tasks))

    assert len(window.chat_view.findChildren(QFrame, "stepCard")) == 2
    assert window.phase_pill.toolTip() == "Brain 正在验收修改"
    window.current_task = None
    window.close()


def test_stderr_noise_does_not_mark_step_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test from a real run: Codex prints dozens of "failed to
    load skill" warnings on stderr at startup, which Studio labels [Error].
    Every Executor card turned red although all of them passed review.
    stderr is not a failure signal; the phase/result flow decides that."""
    data_dir = _isolate_data_dir(monkeypatch, tmp_path)
    orchestrator = tmp_path / "dual-agent.cmd"
    _write_success_shim(orchestrator, "anything")
    _seed_settings(data_dir, orchestrator_path=str(orchestrator), check_environment_on_start=False)

    window = MainWindow()
    window.current_task = AgentTask("t", str(tmp_path), "claude", "codex", 3)
    window._append_log("Process", "[dual-agent] Executor (codex) is running T1, attempt 1/3...")
    window._append_log("Error", "ERROR codex_core::session: failed to load skill SKILL.md")
    window._append_log("Process", "[dual-agent] Brain is reviewing T1, attempt 1...")

    executor_card = window.chat_view.findChildren(QFrame, "stepCard")[0]
    assert executor_card.state == "done"
    assert "failed to load skill" in executor_card.log.toPlainText()
    window.current_task = None
    window.close()


def test_idle_errors_do_not_add_cards_to_the_shown_conversation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed init/doctor or a client error while no task runs used to be
    appended to whatever conversation was on screen (e.g. a replayed history
    task) as a stray "准备中" card. It belongs in the log panel only."""
    data_dir = _isolate_data_dir(monkeypatch, tmp_path)
    orchestrator = tmp_path / "dual-agent.cmd"
    _write_success_shim(orchestrator, "anything")
    _seed_settings(data_dir, orchestrator_path=str(orchestrator), check_environment_on_start=False)
    monkeypatch.setattr(
        QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    )

    window = MainWindow()
    window._on_operation_finished("init", False, "init failed: config exists")

    assert window.chat_view.message_count() == 0
    assert "init failed" in window.log_panel.editor.toPlainText()
    window.close()


def test_parse_log_line() -> None:
    assert _parse_log_line("[Process] foo") == ("Process", "foo")
    assert _parse_log_line("没有前缀") is None


def test_start_failure_keeps_description(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = _isolate_data_dir(monkeypatch, tmp_path)
    orchestrator = tmp_path / "dual-agent.cmd"
    _write_success_shim(orchestrator, "anything")
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _seed_settings(
        data_dir,
        orchestrator_path=str(orchestrator),
        project_path=str(project_dir),
        check_environment_on_start=False,
        auto_detect_roles=False,
    )

    window = MainWindow()
    window.task_panel.description_edit.setPlainText("保留这段任务描述")

    def _fail_start(_task: AgentTask) -> None:
        raise RuntimeError("无法启动")

    monkeypatch.setattr(window.client, "run_task", _fail_start)
    window._start_task()

    assert window.task_panel.description() == "保留这段任务描述"
    assert window.result_panel.values["status"].text() == TaskPhase.FAILED.value
    window.close()


def test_history_replay_restores_steps_and_diff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = _isolate_data_dir(monkeypatch, tmp_path)
    orchestrator = tmp_path / "dual-agent.cmd"
    _write_success_shim(orchestrator, "anything")
    _seed_settings(data_dir, orchestrator_path=str(orchestrator), check_environment_on_start=False)
    log_path = tmp_path / "history.log"
    log_path.write_text(
        "[System] 项目：C:/project\n"
        "[Process] [dual-agent] Brain (claude) is planning...\n"
        "[Process] [dual-agent] Executor (codex) is running T1, attempt 1/3...\n"
        "[Process] [dual-agent] Brain is reviewing T1, attempt 1...\n"
        "[Process] [dual-agent] All tasks passed.\n",
        encoding="utf-8",
    )
    task = AgentTask(
        description="修复登录问题",
        project_path="C:/project",
        brain="claude",
        executor="codex",
        max_retries=3,
        status=TaskPhase.PASSED.value,
        log_path=str(log_path),
        result_summary="任务完成。",
        status_json={"status": "complete"},
    )

    window = MainWindow()
    window._show_history_task(task)

    assert window.chat_view.message_count() == 5
    assert len(window.chat_view.findChildren(QFrame, "stepCard")) == 3
    assert window.result_panel.values["status"].text() == TaskPhase.PASSED.value
    assert "is planning" in window.log_panel.editor.toPlainText()

    result = window.chat_view._messages[-1]
    result.diff_button.click()
    assert window.inspector_toggle.isChecked()
    assert not window.tabs.isHidden()
    assert window.tabs.currentWidget() == window.git_panel
    window.close()
