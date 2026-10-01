from pathlib import Path

import pytest

from app.core.command_builder import CommandBuilder
from app.models.task import AgentTask

NODE_FORWARDER = '@echo off\r\nnode "%~dp0src\\cli.ts" %*\r\n'


def _task(description: str = "修复登录接口，并添加测试") -> AgentTask:
    return AgentTask(
        description=description,
        project_path=r"E:\Projects\项目 With Spaces",
        brain="claude",
        executor="codex",
        max_retries=3,
    )


def test_build_run_command_preserves_chinese_and_space_paths(tmp_path: Path) -> None:
    # A wrapper that does not exist cannot be inspected, so it is used as-is.
    wrapper = str(tmp_path / "missing" / "dual-agent.cmd")
    command = CommandBuilder(wrapper).build_run_command(_task())

    assert command.as_list() == [
        wrapper,
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


def test_pure_node_forwarder_is_bypassed_so_cmd_never_parses_the_goal(tmp_path: Path) -> None:
    """dual-agent.cmd is `node "%~dp0src\\cli.ts" %*`. Going through it lets
    cmd.exe re-parse %*, which cut multi-line goals at the first newline and
    executed the text after "&" as a command. Running node directly avoids
    cmd.exe altogether."""
    wrapper = tmp_path / "dual-agent.cmd"
    wrapper.write_text(NODE_FORWARDER, encoding="utf-8")
    script = tmp_path / "src" / "cli.ts"
    script.parent.mkdir()
    script.write_text("", encoding="utf-8")
    goal = "第一行 a&b %PATH%\n第二行 \"quoted\""

    command = CommandBuilder(str(wrapper)).build_run_command(_task(goal))

    assert command.program == "node"
    assert command.arguments[0] == str(script)
    assert command.arguments[1] == "run"
    assert command.arguments[-1] == goal


@pytest.mark.parametrize(
    "content",
    [
        # Extra behaviour we would silently skip by bypassing the wrapper.
        '@echo off\r\nset NODE_OPTIONS=--max-old-space-size=4096\r\nnode "%~dp0src\\cli.ts" %*\r\n',
        # Not a pure forwarder of all arguments.
        '@echo off\r\nnode "%~dp0src\\cli.ts" run %*\r\n',
        # Different runtime.
        '@echo off\r\nbun "%~dp0src\\cli.ts" %*\r\n',
    ],
)
def test_other_wrappers_are_used_unchanged(tmp_path: Path, content: str) -> None:
    wrapper = tmp_path / "dual-agent.cmd"
    wrapper.write_text(content, encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "cli.ts").write_text("", encoding="utf-8")

    command = CommandBuilder(str(wrapper)).build_status_command(str(tmp_path))

    assert command.program == str(wrapper)


def test_forwarder_pointing_at_missing_script_is_used_unchanged(tmp_path: Path) -> None:
    wrapper = tmp_path / "dual-agent.cmd"
    wrapper.write_text(NODE_FORWARDER, encoding="utf-8")

    command = CommandBuilder(str(wrapper)).build_status_command(str(tmp_path))

    assert command.program == str(wrapper)


def test_plan_only_and_resume_commands(tmp_path: Path) -> None:
    builder = CommandBuilder(str(tmp_path / "missing" / "dual-agent.cmd"))
    task = _task("Add rate limiting")

    plan = builder.build_run_command(task, plan_only=True)
    assert plan.arguments[0] == "run"
    assert "--plan-only" in plan.arguments
    assert plan.arguments[-1] == "Add rate limiting"

    note = "Use SQLite.\nKeep the API stable."
    resume = builder.build_resume_command(task, "run-42", skip=["T2", "T3"], note=f"  {note}\n")
    args = list(resume.arguments)
    assert args[0] == "resume"
    assert args[args.index("--run-id") + 1] == "run-42"
    assert args[args.index("--skip") + 1] == "T2,T3"
    assert args[args.index("--note") + 1] == note
    assert args[args.index("--brain") + 1] == "claude"
    assert task.description not in args, "resume continues a stored run and takes no goal"

    bare = builder.build_resume_command(task, "run-42")
    assert "--skip" not in bare.arguments
    assert "--note" not in bare.arguments


def test_single_agent_run_never_asks_for_a_plan(tmp_path: Path) -> None:
    builder = CommandBuilder(str(tmp_path / "missing" / "dual-agent.cmd"))
    task = _task("Make a runner game")
    task.mode = "single"

    arguments = builder.build_run_command(task, plan_only=True).arguments

    assert "--single-agent" in arguments
    assert "--plan-only" not in arguments, "the orchestrator rejects the combination"
    assert arguments[-1] == "Make a runner game"


def test_run_modes_map_to_orchestrator_routes(tmp_path: Path) -> None:
    builder = CommandBuilder(str(tmp_path / "missing" / "dual-agent.cmd"))
    expected = {
        "auto": [],
        "reviewed": ["--route", "reviewed"],
        "planned": ["--route", "planned"],
        "parallel": ["--route", "parallel"],
    }
    for mode, route_args in expected.items():
        task = _task("goal")
        task.mode = mode
        arguments = list(builder.build_run_command(task, plan_only=True).arguments)
        assert "--plan-only" in arguments, mode
        assert "--single-agent" not in arguments, mode
        if route_args:
            index = arguments.index("--route")
            assert arguments[index : index + 2] == route_args
        else:
            assert "--route" not in arguments, "auto leaves the choice to the Brain"
