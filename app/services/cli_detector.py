from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from app.core.command_builder import CommandBuilder, CommandSpec
from app.core.process_manager import CapturedProcess
from app.models.environment import EnvironmentCheck, EnvironmentStatus
from app.services.provider_service import ENV_KEYS, read_env_file


@dataclass(frozen=True, slots=True)
class _CheckSpec:
    key: str
    command: CommandSpec


class CliDetector(QObject):
    progress = Signal(str, object)
    finished = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._queue: deque[_CheckSpec] = deque()
        self._orchestrator_path = ""
        self._process: CapturedProcess | None = None
        self._status = EnvironmentStatus()

    @property
    def running(self) -> bool:
        return self._process is not None or bool(self._queue)

    def check(
        self, orchestrator_path: str, project_path: str, brain: str | None = None, executor: str | None = None
    ) -> None:
        if self.running:
            return
        project = Path(project_path)
        cwd = str(project if project.is_dir() else Path.cwd())
        self._status = EnvironmentStatus()
        self._orchestrator_path = orchestrator_path
        builder = CommandBuilder(orchestrator_path)
        # A profile from the API settings replaces the CLI's own login, so
        # its login status says nothing about whether runs will work.
        gateways = read_env_file()
        self._queue = deque(
            [
                _CheckSpec("claude_cli", CommandSpec("claude", ("--version",), cwd)),
                _CheckSpec("claude_auth", CommandSpec("claude", ("auth", "status"), cwd)),
                _CheckSpec("codex_cli", CommandSpec("codex", ("--version",), cwd)),
                _CheckSpec("codex_auth", CommandSpec("codex", ("login", "status"), cwd)),
                _CheckSpec("git", CommandSpec("git", ("--version",), cwd)),
                _CheckSpec(
                    "orchestrator",
                    CommandSpec(orchestrator_path, ("--help",), cwd),
                ),
                _CheckSpec("doctor", builder.build_doctor_command(cwd, brain, executor)),
            ]
        )
        for key, tool in (("claude_auth", "claude"), ("codex_auth", "codex")):
            base_url = gateways.get(ENV_KEYS[tool]["base_url"], "").strip()
            if base_url:
                self._queue = deque(spec for spec in self._queue if spec.key != key)
                self._record(key, bool(gateways.get(ENV_KEYS[tool]["api_key"], "").strip()), f"API 配置：{base_url}")
        self._run_next()

    def _run_next(self) -> None:
        if not self._queue:
            self.finished.emit(self._status)
            return
        spec = self._queue.popleft()
        # The configured dual-agent.cmd, not the program a check runs: the
        # builder launches its one-line node forwarder as `node cli.ts`, and
        # "node" is not a path, so doctor was always reported missing.
        if spec.key in {"orchestrator", "doctor"} and not Path(self._orchestrator_path).is_file():
            self._record(spec.key, False, f"找不到：{self._orchestrator_path}")
            self._run_next()
            return

        process = CapturedProcess(self)
        self._process = process
        process.finished.connect(
            lambda code, stdout, stderr: self._on_finished(
                process, spec, code, stdout, stderr
            )
        )
        process.start_failed.connect(
            lambda message: self._on_start_failed(process, spec, message)
        )
        process.start(spec.command)

    def _on_finished(
        self,
        process: CapturedProcess,
        spec: _CheckSpec,
        exit_code: int,
        stdout: str,
        stderr: str,
    ) -> None:
        self._release(process)
        combined = "\n".join(part.strip() for part in (stdout, stderr) if part.strip())
        detail = _format_detail(spec.key, combined)
        self._record(spec.key, exit_code == 0, detail or f"退出码 {exit_code}")
        self._run_next()

    def _on_start_failed(
        self, process: CapturedProcess, spec: _CheckSpec, message: str
    ) -> None:
        self._release(process)
        self._record(spec.key, False, f"无法启动：{message}")
        self._run_next()

    def _release(self, process: CapturedProcess) -> None:
        if self._process is process:
            self._process = None
        process.deleteLater()

    def _record(self, key: str, available: bool, detail: str) -> None:
        check = EnvironmentCheck(available=available, detail=detail)
        setattr(self._status, key, check)
        self.progress.emit(key, check)


def _format_detail(key: str, output: str) -> str:
    if key == "claude_auth" and output:
        try:
            payload = json.loads(output)
            if isinstance(payload, dict):
                logged_in = payload.get("loggedIn")
                method = payload.get("authMethod")
                return f"已登录 ({method or 'unknown'})" if logged_in else "未登录"
        except json.JSONDecodeError:
            pass
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if key == "doctor":
        return "\n".join(lines[-12:])
    return lines[0] if lines else "无输出"

