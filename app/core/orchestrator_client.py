from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal

from app.constants import STATUS_POLL_INTERVAL_MS
from app.core.command_builder import CommandBuilder, CommandSpec
from app.core.process_manager import CapturedProcess, TaskProcessManager
from app.core.task_state import StateSnapshot, phase_from_log, phase_from_status
from app.models.task import AgentTask

LOGGER = logging.getLogger(__name__)


class OrchestratorClient(QObject):
    log_received = Signal(str, str)
    task_started = Signal()
    phase_changed = Signal(object)
    status_updated = Signal(object)
    task_finished = Signal(int, object, bool)
    operation_finished = Signal(str, bool, str)
    error_occurred = Signal(str)

    def __init__(self, orchestrator_path: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._builder = CommandBuilder(orchestrator_path)
        self._task_process = TaskProcessManager(self)
        self._task_process.line_received.connect(self._on_line)
        self._task_process.started.connect(self._on_task_started)
        self._task_process.finished.connect(self._on_task_process_finished)
        self._task_process.start_failed.connect(self._on_task_start_failed)

        self._status_timer = QTimer(self)
        self._status_timer.setInterval(STATUS_POLL_INTERVAL_MS)
        self._status_timer.timeout.connect(self._poll_status)
        self._status_process: CapturedProcess | None = None
        self._operation_process: CapturedProcess | None = None
        self._current_task: AgentTask | None = None
        self._pending_final: tuple[int, bool] | None = None

    @property
    def running(self) -> bool:
        return self._task_process.running

    def set_orchestrator_path(self, path: str) -> None:
        if self.running:
            raise RuntimeError("Cannot change orchestrator path while a task is running.")
        self._builder = CommandBuilder(path)

    def run_task(self, task: AgentTask) -> None:
        orchestrator = Path(self._builder.orchestrator_path)
        if not orchestrator.is_file():
            raise FileNotFoundError(f"找不到 dual-agent.cmd：{orchestrator}")
        if not Path(task.project_path).is_dir():
            raise FileNotFoundError(f"项目目录不存在：{task.project_path}")
        self._current_task = task
        self._pending_final = None
        self._task_process.start(self._builder.build_run_command(task))

    def cancel_task(self) -> None:
        self._task_process.cancel()

    def doctor(self, project_path: str) -> None:
        self._start_operation("doctor", self._builder.build_doctor_command(project_path))

    def init_project(self, project_path: str, *, force: bool = False) -> None:
        self._start_operation(
            "init",
            self._builder.build_init_command(project_path, force=force),
        )

    def get_status(self, project_path: str) -> None:
        self._start_status(self._builder.build_status_command(project_path), final=False)

    def _on_task_started(self) -> None:
        self.task_started.emit()
        self._status_timer.start()

    def _on_line(self, line: str, is_error: bool) -> None:
        self.log_received.emit("Error" if is_error else "Process", line)
        snapshot = phase_from_log(line)
        if snapshot:
            self.phase_changed.emit(snapshot)

    def _on_task_start_failed(self, message: str) -> None:
        self._status_timer.stop()
        self.error_occurred.emit(f"启动任务失败：{message}")
        self._pending_final = (-1, False)
        self._emit_final(None)

    def _on_task_process_finished(self, exit_code: int, cancelled: bool) -> None:
        self._status_timer.stop()
        self._pending_final = (exit_code, cancelled)
        if self._current_task:
            self._start_status(
                self._builder.build_status_command(self._current_task.project_path),
                final=True,
            )
        else:
            self._emit_final(None)

    def _poll_status(self) -> None:
        if self._current_task:
            self._start_status(
                self._builder.build_status_command(self._current_task.project_path),
                final=False,
            )

    def _start_status(self, command: CommandSpec, *, final: bool) -> None:
        if self._status_process and self._status_process.running:
            if final:
                self._status_process.finished.connect(
                    lambda _code, _out, _err: QTimer.singleShot(
                        0, lambda: self._start_status(command, final=True)
                    )
                )
            return

        process = CapturedProcess(self)
        self._status_process = process
        process.finished.connect(
            lambda code, stdout, stderr: self._on_status_finished(
                process, code, stdout, stderr, final
            )
        )
        process.start_failed.connect(
            lambda message: self._on_status_start_failed(process, message, final)
        )
        process.start(command)

    def _on_status_finished(
        self,
        process: CapturedProcess,
        exit_code: int,
        stdout: str,
        stderr: str,
        final: bool,
    ) -> None:
        if self._status_process is process:
            self._status_process = None
        process.deleteLater()
        payload = _parse_json_payload(stdout)
        if payload and self._status_matches_current_task(payload):
            self.status_updated.emit(payload)
            self.phase_changed.emit(phase_from_status(payload))
        else:
            payload = None
            if stderr.strip():
                LOGGER.warning("Status command failed (%s): %s", exit_code, stderr.strip())
        if final:
            self._emit_final(payload)

    def _on_status_start_failed(
        self, process: CapturedProcess, message: str, final: bool
    ) -> None:
        if self._status_process is process:
            self._status_process = None
        process.deleteLater()
        LOGGER.warning("Could not start status command: %s", message)
        if final:
            self._emit_final(None)

    def _status_matches_current_task(self, payload: dict[str, Any]) -> bool:
        if not self._current_task:
            return True
        goal = payload.get("goal")
        return not isinstance(goal, str) or goal == self._current_task.description

    def _emit_final(self, payload: dict[str, Any] | None) -> None:
        exit_code, cancelled = self._pending_final or (-1, False)
        self._pending_final = None
        self.task_finished.emit(exit_code, payload, cancelled)

    def _start_operation(self, name: str, command: CommandSpec) -> None:
        if self._operation_process and self._operation_process.running:
            self.error_occurred.emit("另一个后台操作仍在进行，请稍后重试。")
            return
        process = CapturedProcess(self)
        self._operation_process = process
        process.finished.connect(
            lambda code, stdout, stderr: self._on_operation_finished(
                process, name, code, stdout, stderr
            )
        )
        process.start_failed.connect(
            lambda message: self._on_operation_start_failed(process, name, message)
        )
        process.start(command)

    def _on_operation_finished(
        self,
        process: CapturedProcess,
        name: str,
        exit_code: int,
        stdout: str,
        stderr: str,
    ) -> None:
        if self._operation_process is process:
            self._operation_process = None
        process.deleteLater()
        output = "\n".join(part.strip() for part in (stdout, stderr) if part.strip())
        self.operation_finished.emit(name, exit_code == 0, output)

    def _on_operation_start_failed(
        self, process: CapturedProcess, name: str, message: str
    ) -> None:
        if self._operation_process is process:
            self._operation_process = None
        process.deleteLater()
        self.operation_finished.emit(name, False, f"启动失败：{message}")


def _parse_json_payload(output: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    for index, character in enumerate(output):
        if character != "{":
            continue
        try:
            value, _end = decoder.raw_decode(output[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None
