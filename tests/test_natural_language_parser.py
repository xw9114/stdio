import pytest

from app.core.natural_language_parser import NaturalLanguageParser


@pytest.mark.parametrize(
    ("text", "brain", "executor", "retries"),
    [
        (
            "Claude 负责分析和验收，Codex 负责修改代码，最多返工3次。",
            "claude",
            "codex",
            3,
        ),
        ("Codex 规划，Claude 执行，最多重试5次。", "codex", "claude", 5),
        ("让 Codex 负责规划，Claude 修改，返工 4 次。", "codex", "claude", 4),
        ("帮我修复登录接口并添加测试。", None, None, None),
    ],
)
def test_parses_role_and_retry_hints(
    text: str,
    brain: str | None,
    executor: str | None,
    retries: int | None,
) -> None:
    result = NaturalLanguageParser().parse(text)
    assert result.brain == brain
    assert result.executor == executor
    assert result.max_retries == retries


def test_retry_count_is_bounded() -> None:
    assert NaturalLanguageParser().parse("最多返工99次").max_retries == 20

