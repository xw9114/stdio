from app.core.task_state import (
    TaskPhase,
    final_phase,
    phase_from_log,
    phase_from_status,
    resumable_run_id,
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
    reviewing = phase_from_log("[dual-agent] Brain is reviewing T1, attempt 2...")
    assert reviewing.phase == TaskPhase.REVIEWING
    # Review lines carry no "/max"; the attempt number must still be read.
    assert reviewing.attempt == 2


def test_phase_keywords_outside_orchestrator_status_lines_are_ignored() -> None:
    """Regression test from a real run: Codex's JSON events embed the
    output of commands it runs, so `Get-Content tests/test_main_window.py`
    carried the fake "[dual-agent] Brain (claude) is planning..." lines of
    that test file and opened bogus planning cards mid-run. Only the
    orchestrator's own `[dual-agent] ` status lines may drive phases."""
    embedded = (
        '{"type":"item.completed","item":{"type":"command_execution",'
        '"aggregated_output":"echo [dual-agent] Brain (claude) is planning...\\n"}}'
    )
    assert phase_from_log(embedded) is None
    assert phase_from_log("Codex says: all tasks passed, run blocked? no") is None
    assert phase_from_log("  [dual-agent] Brain (claude) is planning...").phase == TaskPhase.PLANNING


def test_blocked_reason_mentioning_other_phases_is_still_blocked() -> None:
    line = "[dual-agent] Run blocked: Executor (codex) is running out of time; Brain (claude) is planning"
    snapshot = phase_from_log(line)
    assert snapshot is not None
    assert snapshot.phase == TaskPhase.BLOCKED


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


def test_plan_approval_and_verification_phases() -> None:
    assert phase_from_log("[dual-agent] Plan ready for approval.").phase == TaskPhase.AWAITING_APPROVAL
    verifying = phase_from_log("[dual-agent] Verifying T2, attempt 3...")
    assert verifying.phase == TaskPhase.VERIFYING
    assert verifying.attempt == 3
    assert phase_from_status({"status": "awaiting_approval"}).phase == TaskPhase.AWAITING_APPROVAL
    assert final_phase(0, {"status": "awaiting_approval"}, False) == TaskPhase.AWAITING_APPROVAL


def test_resumable_run_id_follows_the_orchestrator_rule() -> None:
    base = {"runId": "run-1", "plan": {"tasks": []}}
    for status in ("awaiting_approval", "blocked", "failed", "executing"):
        assert resumable_run_id({**base, "status": status}) == "run-1", status
    assert resumable_run_id({**base, "status": "complete"}) is None
    assert resumable_run_id({**base, "status": "planning"}) is None
    assert resumable_run_id({"runId": "run-1", "status": "failed"}) is None  # no plan
    assert resumable_run_id({"plan": {}, "status": "failed"}) is None  # no run id
    assert resumable_run_id(None) is None
