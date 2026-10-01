from __future__ import annotations

import base64
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QProcess

from app.core.command_builder import CommandBuilder, CommandSpec
from app.core.process_manager import configure_process
from app.models.task import AgentTask
from qt_helpers import run_event_loop

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows-specific process launch behaviour")


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    yield app


def test_bare_name_on_path_resolves_through_powershell_launcher(
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

    assert process.program().lower().endswith("powershell.exe")
    assert "-File" in process.arguments()
    executable, forwarded_args = _decode_launcher_env(process)
    assert executable.lower() == str(shim).lower()
    assert forwarded_args == ["--version"]


def test_unresolvable_bare_name_falls_back_unchanged(tmp_path: Path) -> None:
    process = QProcess()
    command = CommandSpec(
        program="totally-nonexistent-cli-xyz", arguments=(), working_directory=str(tmp_path)
    )
    configure_process(process, command)

    assert process.program() == "totally-nonexistent-cli-xyz"
    assert process.arguments() == []


def test_absolute_cmd_path_routes_through_powershell_launcher(tmp_path: Path) -> None:
    script = tmp_path / "tool.cmd"
    script.write_text("@echo off\r\necho ok\r\n", encoding="utf-8")

    process = QProcess()
    command = CommandSpec(program=str(script), arguments=("run",), working_directory=str(tmp_path))
    configure_process(process, command)

    assert process.program().lower().endswith("powershell.exe")
    executable, forwarded_args = _decode_launcher_env(process)
    assert executable.lower() == str(script).lower()
    assert forwarded_args == ["run"]


def test_exe_program_is_passed_through_without_launcher(tmp_path: Path) -> None:
    process = QProcess()
    command = CommandSpec(
        program=r"C:\Windows\System32\whoami.exe", arguments=(), working_directory=str(tmp_path)
    )
    configure_process(process, command)

    assert process.program() == r"C:\Windows\System32\whoami.exe"
    assert process.arguments() == []


def test_multi_word_argument_survives_as_a_single_argv_element(tmp_path: Path) -> None:
    """Regression test for a real, reproduced bug: routing a multi-word
    argument (like a natural-language task description) through
    `cmd.exe /d /s /c "<flattened string>"` corrupted it once more than one
    segment needed quoting - the argument came back shredded into one argv
    token per word, with a stray leading/trailing quote character on the
    first/last word. Confirmed live against the real dual-agent-orchestrator:
    its stored `goal` field came back wrapped in literal quote characters for
    exactly this reason. The fix routes .cmd/.bat targets through
    windows_launcher.ps1's array splatting instead.

    Verified with a real spawned process (not just inspecting
    program()/arguments()) using a batch script that walks its OWN %1.. shift
    loop - cmd.exe's normal (non-/C) parameter handling, which is not the
    part that was ever broken - to record each argument it actually
    received, on its own line.
    """
    record_path = tmp_path / "recorded-args.txt"
    script = tmp_path / "dump-args.cmd"
    script.write_text(
        "@echo off\r\n"
        ":loop\r\n"
        'if "%~1"=="" goto done\r\n'
        # %~1 (not %1) strips the quote pair cmd.exe uses to delimit a
        # space-containing parameter, giving back the true content rather
        # than that delimiter's own literal quote characters.
        f'>> "{record_path}" echo(%~1\r\n'
        "shift\r\n"
        "goto loop\r\n"
        ":done\r\n",
        encoding="utf-8",
    )

    goal = (
        "Create a new file named hello.txt in the repository root containing "
        "exactly one line of text: Hello from Dual Agent Studio. "
        "Do not modify or create any other files."
    )
    expected_args = ["run", "--cwd", str(tmp_path), "--brain", "claude", "--executor", "codex", goal]

    process = QProcess()
    command = CommandSpec(program=str(script), arguments=tuple(expected_args), working_directory=str(tmp_path))
    configure_process(process, command)

    app = QCoreApplication.instance()
    finished: list[int] = []
    process.finished.connect(lambda code, _status: (finished.append(code), app.quit()))
    process.start()

    run_event_loop(app, 10000)

    assert finished == [0], "dump-args.cmd did not run to completion"
    recorded = record_path.read_text(encoding="utf-8").splitlines()
    assert recorded == expected_args, (
        "a multi-word argument must survive as ONE argv element, not be split "
        f"word-by-word; got: {recorded!r}"
    )


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not on PATH")
def test_goal_with_cmd_metacharacters_reaches_node_forwarder_intact(tmp_path: Path) -> None:
    """Regression test for a reproduced bug: through dual-agent.cmd's `%*`,
    cmd.exe cut a multi-line goal at its first newline, ran the text after
    "&" as a separate command, expanded %VAR% and dropped embedded quotes.
    CommandBuilder now launches node directly for such a forwarder; this
    checks with a real node process that every argument arrives unchanged.
    """
    record_path = tmp_path / "argv.json"
    wrapper = tmp_path / "dual-agent.cmd"
    wrapper.write_text('@echo off\r\nnode "%~dp0src\\cli.js" %*\r\n', encoding="utf-8")
    script = tmp_path / "src" / "cli.js"
    script.parent.mkdir()
    script.write_text(
        "require('fs').writeFileSync(process.env.ARGV_RECORD,"
        " JSON.stringify(process.argv.slice(2)));\n",
        encoding="utf-8",
    )
    goal = '修复 "登录" 按钮\n第二行：a&b | c ^ %PATH% !x! trailing\\'
    task = AgentTask(
        description=goal,
        project_path=str(tmp_path),
        brain="claude",
        executor="codex",
        max_retries=1,
    )

    process = QProcess()
    configure_process(process, CommandBuilder(str(wrapper)).build_run_command(task))
    environment = process.processEnvironment()
    environment.insert("ARGV_RECORD", str(record_path))
    process.setProcessEnvironment(environment)

    app = QCoreApplication.instance()
    finished: list[int] = []
    process.finished.connect(lambda code, _status: (finished.append(code), app.quit()))
    process.start()
    run_event_loop(app, 10000)

    assert finished == [0]
    recorded = json.loads(record_path.read_text(encoding="utf-8"))
    assert recorded[0] == "run"
    assert recorded[-1] == goal


def _decode_launcher_env(process: QProcess) -> tuple[str, list[str]]:
    environment = process.processEnvironment()
    executable = environment.value("DUAL_AGENT_STUDIO_EXECUTABLE")
    encoded_args = environment.value("DUAL_AGENT_STUDIO_ARGUMENTS")
    forwarded_args = json.loads(base64.b64decode(encoded_args).decode("utf-8"))
    return executable, forwarded_args
