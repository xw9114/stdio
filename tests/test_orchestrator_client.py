from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QTimer

from app.core.orchestrator_client import OrchestratorClient
from app.core.task_state import TaskPhase
from app.models.task import AgentTask, utc_now_iso
from qt_helpers import run_event_loop

pytestmark = pytest.mark.skipif(os.name != "nt", reason="uses a Windows .cmd shim to fake dual-agent.cmd")


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    yield app


def _make_task(project_path: str, description: str = "fix login bug") -> AgentTask:
    return AgentTask(
        description=description,
        project_path=project_path,
        brain="claude",
        executor="codex",
        max_retries=3,
        status=TaskPhase.RUNNING.value,
        started_at=utc_now_iso(),
    )


def test_run_task_validates_paths_before_touching_any_process(tmp_path: Path) -> None:
    client = OrchestratorClient(str(tmp_path / "missing-dual-agent.cmd"))
    task = _make_task(str(tmp_path))
    with pytest.raises(FileNotFoundError):
        client.run_task(task)

    orchestrator = tmp_path / "dual-agent.cmd"
    orchestrator.write_text("@echo off\r\nexit /b 0\r\n", encoding="utf-8")
    client = OrchestratorClient(str(orchestrator))
    task = _make_task(str(tmp_path / "no-such-project"))
    with pytest.raises(FileNotFoundError):
        client.run_task(task)


def _write_success_shim(path: Path, goal: str) -> None:
    # Deliberately avoids `if "%1"=="run" ( ... )` multi-line blocks: cmd.exe
    # scans raw parenthesis characters (not quote-aware) to find a block's
    # end, and the log lines below contain literal "(claude)"/"(codex)",
    # which breaks that parsing. goto/labels sidestep the issue entirely.
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


def test_full_task_lifecycle_drives_phases_and_reports_passed(tmp_path: Path) -> None:
    """End-to-end regression test for the orchestration glue that is
    otherwise completely untested: log-line phase detection while the task
    process runs, then a final status --json poll after it exits, matched
    against the task and turned into a PASSED result.
    """
    goal = "fix login bug"
    orchestrator = tmp_path / "dual-agent.cmd"
    _write_success_shim(orchestrator, goal)

    client = OrchestratorClient(str(orchestrator))
    task = _make_task(str(tmp_path), description=goal)

    phases: list[TaskPhase] = []
    finished: list[tuple[int, object, bool]] = []
    errors: list[str] = []
    app = QCoreApplication.instance()

    client.phase_changed.connect(lambda snapshot: phases.append(snapshot.phase))
    client.error_occurred.connect(errors.append)
    client.task_finished.connect(lambda code, payload, cancelled: (
        finished.append((code, payload, cancelled)),
        app.quit(),
    ))

    client.run_task(task)

    run_event_loop(app, 15000)

    assert not errors, f"unexpected client errors: {errors}"
    assert finished, "task_finished was never emitted"
    exit_code, payload, cancelled = finished[0]
    assert exit_code == 0
    assert cancelled is False
    assert payload is not None and payload.get("status") == "complete"

    assert TaskPhase.PLANNING in phases
    assert TaskPhase.REVIEWING in phases
    assert phases[-1] == TaskPhase.PASSED


def _write_slow_shim(path: Path) -> None:
    # Sleeps long enough for the test to call cancel_task() before it would
    # otherwise print its success line and exit 0 on its own.
    path.write_text(
        "@echo off\r\n"
        'if "%1"=="run" goto :run\r\n'
        'if "%1"=="status" goto :status\r\n'
        "exit /b 1\r\n"
        "\r\n"
        ":run\r\n"
        "echo [dual-agent] Brain (claude) is planning...\r\n"
        "ping -n 6 127.0.0.1 >nul\r\n"
        "echo [dual-agent] All tasks passed.\r\n"
        "exit /b 0\r\n"
        "\r\n"
        ":status\r\n"
        'echo {"status": "blocked", "goal": "cancel me"}\r\n'
        "exit /b 0\r\n",
        encoding="utf-8",
    )


def test_cancel_task_reports_cancelled_not_the_orchestrators_own_exit_status(tmp_path: Path) -> None:
    orchestrator = tmp_path / "dual-agent.cmd"
    _write_slow_shim(orchestrator)

    client = OrchestratorClient(str(orchestrator))
    task = _make_task(str(tmp_path), description="cancel me")

    finished: list[tuple[int, object, bool]] = []
    app = QCoreApplication.instance()
    client.task_finished.connect(lambda code, payload, cancelled: (
        finished.append((code, payload, cancelled)),
        app.quit(),
    ))

    started = []
    client.task_started.connect(lambda: started.append(True))

    client.run_task(task)

    def cancel_once_started():
        if started:
            client.cancel_task()
            return True
        return False

    poll = QTimer()
    poll.timeout.connect(lambda: cancel_once_started() and poll.stop())
    poll.start(50)

    run_event_loop(app, 15000)

    assert finished, "task_finished was never emitted after cancellation"
    _exit_code, _payload, cancelled = finished[0]
    assert cancelled is True
