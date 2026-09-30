from __future__ import annotations

import base64
import json
import os
import shutil
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from app.core.command_builder import CommandSpec

_WINDOWS_LAUNCHER_SCRIPT = Path(__file__).resolve().parent / "windows_launcher.ps1"


def configure_process(process: QProcess, command: CommandSpec) -> None:
    process.setWorkingDirectory(command.working_directory)
    process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
    environment = QProcessEnvironment.systemEnvironment()
    environment.remove("FORCE_COLOR")
    environment.insert("NO_COLOR", "1")

    program = command.program
    if os.name == "nt":
        # QProcess calls CreateProcess directly on Windows and does not apply
        # the shell's PATHEXT-based lookup, so a bare name like "claude" is
        # never resolved to the "claude.cmd" shim that npm installs on
        # Windows (no .exe exists for it). Resolve it ourselves first so the
        # .cmd/.bat routing below sees the real, extension-bearing file.
        resolved = shutil.which(program)
        if resolved:
            program = resolved

    suffix = Path(program).suffix.lower()
    if os.name == "nt" and suffix in {".cmd", ".bat"}:
        # Do NOT route this through `cmd.exe /d /s /c "<flattened string>"`:
        # that requires collapsing the program path and every argument into
        # one string, and once more than one segment needs quoting (e.g. a
        # multi-word task description), cmd.exe's own /C quote-stripping
        # heuristic corrupts it - confirmed by reproduction, a multi-word
        # argument came back shredded into one argv token per word with a
        # stray leading/trailing quote character. PowerShell's array
        # splatting (see windows_launcher.ps1) passes each argument through
        # in one hop with no equivalent ambiguity.
        environment.insert("DUAL_AGENT_STUDIO_EXECUTABLE", program)
        environment.insert(
            "DUAL_AGENT_STUDIO_ARGUMENTS",
            base64.b64encode(json.dumps(list(command.arguments)).encode("utf-8")).decode("ascii"),
        )
        process.setProcessEnvironment(environment)
        process.setProgram(_resolve_powershell())
        process.setArguments(
            ["-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(_WINDOWS_LAUNCHER_SCRIPT)]
        )
        return

    process.setProcessEnvironment(environment)
    process.setProgram(program)
    process.setArguments(list(command.arguments))


def _resolve_powershell() -> str:
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    return str(Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe")


class CapturedProcess(QObject):
    finished = Signal(int, str, str)
    start_failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process = QProcess(self)
        self._stdout = bytearray()
        self._stderr = bytearray()
        self._reported_start_error = False
        self._process.readyReadStandardOutput.connect(self._read_stdout)
        self._process.readyReadStandardError.connect(self._read_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

    @property
    def running(self) -> bool:
        return self._process.state() != QProcess.ProcessState.NotRunning

    def start(self, command: CommandSpec) -> None:
        self._stdout.clear()
        self._stderr.clear()
        self._reported_start_error = False
        configure_process(self._process, command)
        self._process.start()

    def _read_stdout(self) -> None:
        self._stdout.extend(bytes(self._process.readAllStandardOutput()))

    def _read_stderr(self) -> None:
        self._stderr.extend(bytes(self._process.readAllStandardError()))

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart and not self._reported_start_error:
            self._reported_start_error = True
            self.start_failed.emit(self._process.errorString())

    def _on_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        self._read_stdout()
        self._read_stderr()
        self.finished.emit(
            exit_code,
            self._stdout.decode("utf-8", errors="replace"),
            self._stderr.decode("utf-8", errors="replace"),
        )


class TaskProcessManager(QObject):
    line_received = Signal(str, bool)
    started = Signal()
    finished = Signal(int, bool)
    start_failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process = QProcess(self)
        self._killer: QProcess | None = None
        self._stdout_buffer = ""
        self._stderr_buffer = ""
        self._cancel_requested = False
        self._reported_start_error = False
        self._process.readyReadStandardOutput.connect(self._read_stdout)
        self._process.readyReadStandardError.connect(self._read_stderr)
        self._process.started.connect(self.started)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

    @property
    def running(self) -> bool:
        return self._process.state() != QProcess.ProcessState.NotRunning

    @property
    def process_id(self) -> int:
        return int(self._process.processId())

    def start(self, command: CommandSpec) -> None:
        if self.running:
            raise RuntimeError("A task process is already running.")
        self._stdout_buffer = ""
        self._stderr_buffer = ""
        self._cancel_requested = False
        self._reported_start_error = False
        configure_process(self._process, command)
        self._process.start()

    def cancel(self) -> None:
        # Dual Agent Studio is Windows-only (taskkill.exe, COMSPEC/.cmd
        # routing in configure_process(), etc.), so process-tree cancellation
        # always goes through taskkill. The terminate() fallback below only
        # covers the unlikely race where the process has already exited
        # between the running check above and reading its pid.
        if not self.running:
            return
        self._cancel_requested = True
        pid = self.process_id
        if pid > 0:
            self._killer = QProcess(self)
            self._killer.finished.connect(self._killer.deleteLater)
            self._killer.start("taskkill.exe", ["/pid", str(pid), "/t", "/f"])
            QTimer.singleShot(3_000, self._kill_if_running)
            return
        self._process.terminate()
        QTimer.singleShot(3_000, self._kill_if_running)

    def _kill_if_running(self) -> None:
        if self.running:
            self._process.kill()

    def _read_stdout(self) -> None:
        chunk = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._stdout_buffer = self._emit_complete_lines(self._stdout_buffer + chunk, False)

    def _read_stderr(self) -> None:
        chunk = bytes(self._process.readAllStandardError()).decode("utf-8", errors="replace")
        self._stderr_buffer = self._emit_complete_lines(self._stderr_buffer + chunk, True)

    def _emit_complete_lines(self, value: str, is_error: bool) -> str:
        lines = value.splitlines(keepends=True)
        remainder = ""
        if lines and not lines[-1].endswith(("\n", "\r")):
            remainder = lines.pop()
        for line in lines:
            self.line_received.emit(line.rstrip("\r\n"), is_error)
        return remainder

    def _flush_buffers(self) -> None:
        self._read_stdout()
        self._read_stderr()
        if self._stdout_buffer:
            self.line_received.emit(self._stdout_buffer, False)
        if self._stderr_buffer:
            self.line_received.emit(self._stderr_buffer, True)
        self._stdout_buffer = ""
        self._stderr_buffer = ""

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart and not self._reported_start_error:
            self._reported_start_error = True
            self.start_failed.emit(self._process.errorString())

    def _on_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        self._flush_buffers()
        self.finished.emit(exit_code, self._cancel_requested)

