from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication

from app.core.git_manager import GitManager
from qt_helpers import run_event_loop

pytestmark = pytest.mark.skipif(os.name != "nt", reason="uses a Windows .cmd shim to fake git")


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    yield app


def _write_slow_git_shim(bin_dir: Path) -> None:
    # "status --short" sleeps briefly so a second refresh() call can land
    # while the first one is still in flight. "diff ..." echoes back the
    # -C path (its second argument) so the test can tell which project a
    # given refreshed() emission belongs to without reaching into private
    # GitManager state.
    script = bin_dir / "git.cmd"
    script.write_text(
        "@echo off\r\n"
        "echo %* | findstr /C:\"status\" >nul\r\n"
        "if %errorlevel%==0 (\r\n"
        "  ping -n 2 127.0.0.1 >nul\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "echo DIFF_FOR:%2\r\n"
        "exit /b 0\r\n",
        encoding="utf-8",
    )


def test_refresh_while_busy_coalesces_to_latest_request_instead_of_dropping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test: GitManager.refresh() used to silently drop a request
    that arrived while a previous status/diff round trip was still running.
    It must now remember only the latest request and run it automatically
    once the in-flight one finishes.
    """
    bin_dir = tmp_path / "shimbin"
    bin_dir.mkdir()
    _write_slow_git_shim(bin_dir)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    project_a = str(tmp_path / "project_a")
    project_b = str(tmp_path / "project_b")
    Path(project_a).mkdir()
    Path(project_b).mkdir()

    app = QCoreApplication.instance()
    manager = GitManager()
    results: list[tuple[str, str]] = []

    def on_refreshed(status: str, diff: str) -> None:
        results.append((status, diff))
        if len(results) >= 2:
            app.quit()

    manager.refreshed.connect(on_refreshed)

    manager.refresh(project_a)
    assert manager._process is not None and manager._process.running

    # Arrives while project_a's "status" call is still sleeping.
    manager.refresh(project_b)
    assert manager._pending_path == project_b, "second request should be queued, not dropped"
    assert manager._process is not None and manager._process.running, (
        "the in-flight process for project_a must not be replaced or duplicated"
    )

    run_event_loop(app, 15000)

    assert len(results) == 2, f"expected exactly two refreshed() emissions, got {results}"
    assert results[0][1] == f"DIFF_FOR:{project_a}"
    assert results[1][1] == f"DIFF_FOR:{project_b}"
    assert manager._pending_path is None


def test_fresh_repository_without_commits_shows_status_not_an_error(tmp_path: Path) -> None:
    """`git diff HEAD` fails in a repository with no commits (e.g. right
    after Studio's git init); the panel must show the status instead."""
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "game.py").write_text("print('run')\n", encoding="utf-8")

    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    manager = GitManager()
    results: list[tuple[str, ...]] = []
    manager.refreshed.connect(lambda status, diff: (results.append(("ok", status, diff)), app.quit()))
    manager.failed.connect(lambda message: (results.append(("failed", message)), app.quit()))
    manager.refresh(str(tmp_path))
    run_event_loop(app, 15000)

    assert results and results[0][0] == "ok", results
    assert "game.py" in results[0][1]
    assert "还没有任何提交" in results[0][2]
