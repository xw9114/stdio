from pathlib import Path
import subprocess


ORCHESTRATOR_ROOT = Path(r"E:\projects\dual-agent-orchestrator")


def test_real_orchestrator_help_contract() -> None:
    result = subprocess.run(
        ["node", "src/cli.ts", "--help"],
        cwd=ORCHESTRATOR_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )
    assert result.returncode == 0
    assert "dual-agent run" in result.stdout
    assert "--brain anthropic-api|openai-api|claude|codex" in result.stdout
    assert "--executor openai-api|claude|codex" in result.stdout


def test_real_orchestrator_status_without_runs_is_non_json_but_successful() -> None:
    result = subprocess.run(
        ["node", "src/cli.ts", "status", "--cwd", str(ORCHESTRATOR_ROOT), "--json"],
        cwd=ORCHESTRATOR_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "No runs found for this workspace."



def test_real_orchestrator_parses_list_shaped_goals_and_notes(tmp_path: Path) -> None:
    """Both commands stop at a later check (no Git repository, no runs); what
    matters is that argument parsing accepted the dash-led values."""
    from app.core.command_builder import CommandBuilder
    from app.models.task import AgentTask

    builder = CommandBuilder(str(ORCHESTRATOR_ROOT / "dual-agent.cmd"))
    task = AgentTask("- fix the login", str(tmp_path), "claude", "codex", 1)
    for spec in (builder.build_run_command(task), builder.build_resume_command(task, "run-x", note="- keep it")):
        result = subprocess.run(
            ["node", "src/cli.ts", *spec.arguments],
            cwd=ORCHESTRATOR_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        output = result.stdout + result.stderr
        assert result.returncode != 0
        assert "ERR_PARSE_ARGS" not in output and "Unknown option" not in output and "ambiguous" not in output, output
