from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class EnvironmentCheck:
    available: bool = False
    detail: str = "Not checked"


@dataclass(slots=True)
class EnvironmentStatus:
    claude_cli: EnvironmentCheck = field(default_factory=EnvironmentCheck)
    claude_auth: EnvironmentCheck = field(default_factory=EnvironmentCheck)
    codex_cli: EnvironmentCheck = field(default_factory=EnvironmentCheck)
    codex_auth: EnvironmentCheck = field(default_factory=EnvironmentCheck)
    git: EnvironmentCheck = field(default_factory=EnvironmentCheck)
    orchestrator: EnvironmentCheck = field(default_factory=EnvironmentCheck)
    doctor: EnvironmentCheck = field(default_factory=EnvironmentCheck)

    @property
    def ready(self) -> bool:
        return self.git.available and self.orchestrator.available and self.doctor.available

