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

@dataclass(frozen=True, slots=True)
class RunMode:
    key: str
    label: str
    description: str


# How much process a task gets. "auto" lets the Brain pick the route; the
# others force one, which is what side-by-side comparisons need.
RUN_MODES = (
    RunMode("auto", "自动", "Brain 先判断任务大小，再选择直接执行、执行后验收或拆分执行"),
    RunMode("reviewed", "执行后验收", "Executor 一次完成整个任务，Brain 独立验收，不通过就带着反馈重试"),
    RunMode("planned", "拆分执行", "Brain 拆成 2–4 个任务逐个验收，最后再整体验收一次"),
    RunMode("single", "单 agent", "只用 Executor，不规划、不验收；用来对比效果"),
)
RUN_MODE_LABELS = {mode.key: mode.label for mode in RUN_MODES}
ROUTE_LABELS = {"direct": "直接执行", "reviewed": "执行后验收", "planned": "拆分执行"}


def normalize_run_mode(value: object) -> str:
    # Before routing existed, "dual" always meant a multi-task plan.
    if value == "dual":
        return "planned"
    return value if isinstance(value, str) and value in RUN_MODE_LABELS else "auto"


DEFAULT_ORCHESTRATOR_PATH =r"E:\projects\dual-agent-orchestrator\dual-agent.cmd"
MAX_HISTORY_ITEMS = 100
MAX_VISIBLE_LOG_LINES = 15_000
STATUS_POLL_INTERVAL_MS = 3_000
