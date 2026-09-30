from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InferredTaskOptions:
    brain: str | None = None
    executor: str | None = None
    max_retries: int | None = None


class NaturalLanguageParser:
    _agent = r"(claude|codex)"
    _brain_action = r"(?:规划|分析|检查|验收|审核|review|plan|planner|analy[sz]e)"
    _executor_action = r"(?:执行|修改|编码|实现|修复|开发|execute|implement|code|modify|fix)"

    def parse(self, text: str) -> InferredTaskOptions:
        lowered = text.lower()
        brain = self._find_role(lowered, self._brain_action)
        executor = self._find_role(lowered, self._executor_action)
        retries = self._find_retries(lowered)
        return InferredTaskOptions(brain=brain, executor=executor, max_retries=retries)

    def _find_role(self, text: str, action_pattern: str) -> str | None:
        patterns = (
            rf"{self._agent}\s*(?:负责|来|先)?\s*{action_pattern}",
            rf"{action_pattern}\s*(?:交给|由|让)?\s*{self._agent}",
        )
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                groups = [group for group in match.groups() if group in {"claude", "codex"}]
                if groups:
                    return groups[0]
        return None

    @staticmethod
    def _find_retries(text: str) -> int | None:
        patterns = (
            r"(?:最多|至多|最大)\s*(\d{1,2})\s*次\s*(?:返工|重试|修改)?",
            r"(?:返工|重试)\s*(\d{1,2})\s*次",
            r"(?:max(?:imum)?\s*)?(\d{1,2})\s*(?:retries|retry)",
        )
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return min(20, max(0, int(match.group(1))))
        return None

