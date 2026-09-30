from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

import app.utils.paths as paths_module
from app.core.task_state import TaskPhase
from app.models.settings import AppSettings
from app.services.settings_service import SettingsService
from app.ui.main_window import MainWindow

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

    QTimer.singleShot(15000, app.quit)  # safety timeout
    app.exec()

    assert finished_signals, "orchestrator task never finished"
    assert window.current_task is None

    assert window.result_panel.values["status"].text() == TaskPhase.PASSED.value
    assert window.status_panel.final_stage.detail.text() == "通过"
    assert "all tasks passed" in window.log_panel.editor.toPlainText().lower()

    assert len(window.history) == 1
    assert window.history[0].status == TaskPhase.PASSED.value
    assert window.history[0].description == goal

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

    QTimer.singleShot(15000, app.quit)  # safety timeout
    app.exec()

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
