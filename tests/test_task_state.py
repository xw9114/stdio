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


def test_whole_result_review_and_verification_phases() -> None:
    review = phase_from_log("[dual-agent] Brain is reviewing the whole result against the goal...")
    assert review.phase == TaskPhase.REVIEWING
    assert review.message == "Brain 正在整体验收"
    verify = phase_from_log("[dual-agent] Verifying the whole result...")
    assert verify.phase == TaskPhase.VERIFYING
    assert verify.message == "正在整体运行验证命令"
    # Route lines are informational, not a phase.
    assert phase_from_log("[dual-agent] Route: reviewed - one session is enough") is None


def test_active_isolation_only_while_the_branch_is_pending() -> None:
    from app.core.task_state import active_isolation

    worktree = {"path": "C:/runs/r1/worktree", "branch": "dual-agent/r1", "base": "abc123"}
    assert active_isolation({"isolation": {**worktree, "state": "active"}}) == worktree
    assert active_isolation({"isolation": {**worktree, "state": "applied"}}) is None
    assert active_isolation({"isolation": {**worktree, "state": "discarded"}}) is None
    assert active_isolation({"isolation": {"state": "active", "path": "p"}}) is None  # incomplete
    assert active_isolation({"status": "complete"}) is None
    assert active_isolation(None) is None


def test_usage_summary_marks_cost_as_partial_when_some_turns_are_unpriced() -> None:
    from app.core.task_state import usage_summary

    claude_only = {
        "usage": {
            "total": {"inputTokens": 400_000, "outputTokens": 10_000, "costUsd": 1.2185},
            "steps": [{"label": "plan", "costUsd": 0.63}, {"label": "review", "costUsd": 0.58}],
        }
    }
    assert usage_summary(claude_only) == "tokens 410.0k · 费用 $1.22"

    with_codex = {
        "usage": {
            "total": {"inputTokens": 540_000, "outputTokens": 11_000, "costUsd": 1.2185},
            "steps": [{"label": "plan", "costUsd": 1.2185}, {"label": "T1-execute-1"}],
        }
    }
    assert usage_summary(with_codex) == "tokens 551.0k · 费用 $1.22（仅含 Claude 部分）"

    codex_only = {"usage": {"total": {"inputTokens": 900, "outputTokens": 100}, "steps": [{}]}}
    assert usage_summary(codex_only) == "tokens 1.0k"
    assert usage_summary({"status": "complete"}) is None
    assert usage_summary(None) is None
