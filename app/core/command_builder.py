from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.models.task import AgentTask


@dataclass(frozen=True, slots=True)
class CommandSpec:
    program: str
    arguments: tuple[str, ...]
    working_directory: str

    def as_list(self) -> list[str]:
        return [self.program, *self.arguments]


class CommandBuilder:
    def __init__(self, orchestrator_path: str) -> None:
        self.orchestrator_path = str(Path(orchestrator_path).expanduser())

    def build_run_command(self, task: AgentTask, *, quiet: bool = False) -> CommandSpec:
        arguments = [
            "run",
            "--cwd",
            task.project_path,
            "--brain",
            task.brain,
            "--executor",
            task.executor,
            "--max-retries",
            str(task.max_retries),
        ]
        if quiet:
            arguments.append("--quiet")
        arguments.append(task.description)
        return self._spec(arguments, task.project_path)

    def build_doctor_command(self, project_path: str) -> CommandSpec:
        return self._spec(["doctor", "--cwd", project_path], project_path)

    def build_init_command(self, project_path: str, *, force: bool = False) -> CommandSpec:
        arguments = ["init", "--cwd", project_path]
        if force:
            arguments.append("--force")
        return self._spec(arguments, project_path)

    def build_status_command(self, project_path: str) -> CommandSpec:
        return self._spec(["status", "--cwd", project_path, "--json"], project_path)

    def _spec(self, arguments: list[str], working_directory: str) -> CommandSpec:
        script = _node_forwarded_script(Path(self.orchestrator_path))
        if script is not None:
            return CommandSpec(
                program="node",
                arguments=(str(script), *arguments),
                working_directory=working_directory,
            )
        return CommandSpec(
            program=self.orchestrator_path,
            arguments=tuple(arguments),
            working_directory=working_directory,
        )


# Matches the one-line forwarder dual-agent.cmd consists of:
#   node "%~dp0src\cli.ts" %*
_NODE_FORWARDER = re.compile(r'^node\s+"%~dp0(?P<script>[^"%]+)"\s+%\*$', re.IGNORECASE)


def _node_forwarded_script(wrapper: Path) -> Path | None:
    """Return the script a pure `node "%~dp0<script>" %*` wrapper forwards to.

    Anything that goes through a .cmd is re-parsed by cmd.exe when it expands
    %*, which no quoting on our side can fully survive: reproduced, a
    multi-line task description is cut at its first newline, "a&b" runs "b"
    as a command, %VAR% is expanded and embedded quotes are dropped. When the
    wrapper does nothing but forward to node, launching node.exe directly
    passes the description through CreateProcess untouched. Any other
    wrapper content returns None so the caller keeps using the wrapper as-is
    rather than guessing what it does.
    """
    if wrapper.suffix.lower() not in {".cmd", ".bat"}:
        return None
    try:
        content = wrapper.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    lines = [
        line.strip()
        for line in content.splitlines()
        if line.strip() and line.strip().lower() != "@echo off"
    ]
    if len(lines) != 1:
        return None
    match = _NODE_FORWARDER.match(lines[0])
    if not match:
        return None
    script = wrapper.parent / match.group("script")
    return script if script.is_file() else None

