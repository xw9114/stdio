from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from app.core.command_builder import CommandSpec


def configure_process(process: QProcess, command: CommandSpec) -> None:
    process.setWorkingDirectory(command.working_directory)
    process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
    environment = QProcessEnvironment.systemEnvironment()
    environment.remove("FORCE_COLOR")
    environment.insert("NO_COLOR", "1")
    process.setProcessEnvironment(environment)

    suffix = Path(command.program).suffix.lower()
    if os.name == "nt" and suffix in {".cmd", ".bat"}:
        process.setProgram(os.environ.get("COMSPEC", "cmd.exe"))
        command_line = subprocess.list2cmdline(command.as_list())
        process.setArguments(["/d", "/s", "/c", command_line])
        return

    process.setProgram(command.program)
    process.setArguments(list(command.arguments))


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
        if not self.running:
            return
        self._cancel_requested = True
        pid = self.process_id
        if os.name == "nt" and pid > 0:
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

