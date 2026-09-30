from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AgentOption:
    key: str
    label: str
    supports_brain: bool = True
    supports_executor: bool = True


AGENT_OPTIONS = (
    AgentOption("claude", "Claude Code CLI"),
    AgentOption("codex", "Codex CLI"),
    AgentOption("anthropic-api", "Claude API", supports_executor=False),
    AgentOption("openai-api", "OpenAI Responses API"),
    AgentOption("sub2api", "Sub2API"),
)

AGENT_LABELS = {option.key: option.label for option in AGENT_OPTIONS}
BRAIN_OPTIONS = tuple(option for option in AGENT_OPTIONS if option.supports_brain)
EXECUTOR_OPTIONS = tuple(option for option in AGENT_OPTIONS if option.supports_executor)

DEFAULT_ORCHESTRATOR_PATH = r"E:\codex\dual-agent-orchestrator\dual-agent.cmd"
MAX_HISTORY_ITEMS = 100
MAX_VISIBLE_LOG_LINES = 15_000
STATUS_POLL_INTERVAL_MS = 3_000
