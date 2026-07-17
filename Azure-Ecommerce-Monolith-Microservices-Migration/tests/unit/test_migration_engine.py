"""Unit tests for bff/app/migration_engine.py's pure state-machine logic —
no real subprocesses or Azure calls (those are exercised in the smoke tests
and in the manual live-migration verification)."""
import pytest

from app.migration_engine import MigrationEngine, StepStatus


def test_initial_snapshot_all_pending():
    engine = MigrationEngine()
    snapshot = engine.snapshot()
    assert snapshot["active_backend"] == "monolith"
    assert snapshot["running"] is False
    assert snapshot["last_error"] is None
    assert all(s["status"] == "pending" for s in snapshot["steps"])
    assert len(snapshot["steps"]) == 9


def test_reset_clears_progress():
    engine = MigrationEngine()
    engine.steps[0].status = StepStatus.DONE
    engine.active_backend = "microservices"
    engine.last_error = "boom"

    engine.reset()

    snapshot = engine.snapshot()
    assert snapshot["active_backend"] == "monolith"
    assert snapshot["last_error"] is None
    assert all(s["status"] == "pending" for s in snapshot["steps"])


@pytest.mark.asyncio
async def test_run_is_a_noop_while_already_running():
    engine = MigrationEngine()
    engine.running = True
    await engine.run("local")
    # run() should return immediately without touching step state
    assert all(s.status == StepStatus.PENDING for s in engine.steps)
