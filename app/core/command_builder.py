from __future__ import annotations

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
        return CommandSpec(
            program=self.orchestrator_path,
            arguments=tuple(arguments),
            working_directory=working_directory,
        )

