from app.core.task_state import TaskPhase, final_phase, phase_from_log, phase_from_status


def test_parses_orchestrator_log_phases() -> None:
    assert phase_from_log("[dual-agent] Brain (claude) is planning...").phase == TaskPhase.PLANNING
    executing = phase_from_log(
        "[dual-agent] Executor (codex) is running T1, attempt 2/4..."
    )
    assert executing is not None
    assert executing.phase == TaskPhase.RETRYING
    assert executing.attempt == 2
    assert executing.max_attempts == 4
    assert phase_from_log("[dual-agent] Brain is reviewing T1, attempt 2...").phase == TaskPhase.REVIEWING


def test_status_json_drives_phase_without_guessing() -> None:
    payload = {
        "status": "executing",
        "tasks": [
            {
                "status": "running",
                "attempts": [{"number": 1, "execution": {"summary": "done"}}],
            }
        ],
    }
    assert phase_from_status(payload).phase == TaskPhase.REVIEWING
    assert final_phase(0, {"status": "complete"}, False) == TaskPhase.PASSED
    assert final_phase(0, None, False) == TaskPhase.UNKNOWN
    assert final_phase(2, {"status": "blocked"}, False) == TaskPhase.BLOCKED
    assert final_phase(0, {"status": "complete"}, True) == TaskPhase.CANCELLED

