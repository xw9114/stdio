from app.core.command_builder import CommandBuilder
from app.models.task import AgentTask


def test_build_run_command_preserves_chinese_and_space_paths() -> None:
    task = AgentTask(
        description="修复登录接口，并添加测试",
        project_path=r"E:\Projects\项目 With Spaces",
        brain="claude",
        executor="codex",
        max_retries=3,
    )
    command = CommandBuilder(
        r"E:\projects\dual-agent-orchestrator\dual-agent.cmd"
    ).build_run_command(task)

    assert command.as_list() == [
        r"E:\projects\dual-agent-orchestrator\dual-agent.cmd",
        "run",
        "--cwd",
        r"E:\Projects\项目 With Spaces",
        "--brain",
        "claude",
        "--executor",
        "codex",
        "--max-retries",
        "3",
        "修复登录接口，并添加测试",
    ]


def test_builds_doctor_init_and_status_commands() -> None:
    builder = CommandBuilder(r"E:\tools\dual-agent.cmd")
    assert builder.build_doctor_command(r"E:\repo").arguments == (
        "doctor",
        "--cwd",
        r"E:\repo",
    )
    assert builder.build_init_command(r"E:\repo", force=True).arguments[-1] == "--force"
    assert builder.build_status_command(r"E:\repo").arguments[-1] == "--json"

