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
    assert "--brain anthropic-api|openai-api|sub2api|claude|codex" in result.stdout
    assert "--executor openai-api|sub2api|claude|codex" in result.stdout


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

