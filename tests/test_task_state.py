from app.core.task_state import (
    TaskPhase,
    final_phase,
    phase_from_log,
    phase_from_status,
    status_matches_task,
)


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


def test_status_matches_task_fails_closed_on_unverifiable_payload() -> None:
    # No current task: nothing to filter against, so any payload is accepted.
    assert status_matches_task({"status": "executing"}, None) is True

    # Matching goal: accepted.
    assert status_matches_task({"goal": "fix the bug"}, "fix the bug") is True

    # Different goal: a stale/foreign run's status must not be shown as ours.
    assert status_matches_task({"goal": "someone else's task"}, "fix the bug") is False

    # Missing or malformed goal field: previously treated as a match (fail
    # open); must now fail closed since we cannot verify it belongs to us.
    assert status_matches_task({"status": "executing"}, "fix the bug") is False
    assert status_matches_task({"goal": 123}, "fix the bug") is False


def test_status_matches_task_ignores_line_ending_and_edge_whitespace() -> None:
    assert status_matches_task({"goal": "line one\r\nline two"}, "line one\nline two") is True
    assert status_matches_task({"goal": "fix the bug"}, "  fix the bug\n") is True
    # Only the edges are normalized; inner content must still match exactly.
    assert status_matches_task({"goal": "line one"}, "line one\nline two") is False

