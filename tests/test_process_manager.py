from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QProcess

from app.core.command_builder import CommandSpec
from app.core.process_manager import configure_process

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows-specific process launch behaviour")


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    yield app


def test_bare_name_on_path_resolves_through_cmd_shim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test for the environment-check bug: QProcess.start() calls
    CreateProcess directly on Windows and does not apply PATHEXT, so a bare
    name like "claude" was never resolved to the "claude.cmd" shim that npm
    installs (no .exe exists for it), and the process failed to start even
    though the CLI was genuinely installed. configure_process() must resolve
    the program with shutil.which() first so the .cmd/.bat routing applies.
    """
    shim_dir = tmp_path / "shimbin"
    shim_dir.mkdir()
    shim = shim_dir / "fakecli.cmd"
    shim.write_text("@echo off\r\necho ok\r\n", encoding="utf-8")

    monkeypatch.setenv("PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    process = QProcess()
    command = CommandSpec(program="fakecli", arguments=("--version",), working_directory=str(tmp_path))
    configure_process(process, command)

    assert process.program().lower().endswith("cmd.exe")
    args = process.arguments()
    assert args[:3] == ["/d", "/s", "/c"]
    assert str(shim).lower() in args[-1].lower()
    assert "--version" in args[-1]


def test_unresolvable_bare_name_falls_back_unchanged(tmp_path: Path) -> None:
    process = QProcess()
    command = CommandSpec(
        program="totally-nonexistent-cli-xyz", arguments=(), working_directory=str(tmp_path)
    )
    configure_process(process, command)

    assert process.program() == "totally-nonexistent-cli-xyz"
    assert process.arguments() == []


def test_absolute_cmd_path_still_routes_through_cmd(tmp_path: Path) -> None:
    script = tmp_path / "tool.cmd"
    script.write_text("@echo off\r\necho ok\r\n", encoding="utf-8")

    process = QProcess()
    command = CommandSpec(program=str(script), arguments=("run",), working_directory=str(tmp_path))
    configure_process(process, command)

    assert process.program().lower().endswith("cmd.exe")
    assert "run" in process.arguments()[-1]


def test_exe_program_is_passed_through_without_cmd_wrapping(tmp_path: Path) -> None:
    process = QProcess()
    command = CommandSpec(
        program=r"C:\Windows\System32\whoami.exe", arguments=(), working_directory=str(tmp_path)
    )
    configure_process(process, command)

    assert process.program() == r"C:\Windows\System32\whoami.exe"
    assert process.arguments() == []
