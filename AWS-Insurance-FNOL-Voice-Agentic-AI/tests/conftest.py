"""Shared pytest fixtures.

The independent-set guard (`evals/holdout_ledger.py`) detects a **process-level** pair: this process has
read the independent held-out set *and* constructed a real AWS client. That is the right granularity for a
script, which is one logical unit of work, and the wrong granularity for a pytest session, where dozens of
unrelated tests share one interpreter.

Without isolation the guard fires on an accident of test ordering: `test_golden_set.py` reads the
independent set to check its composition, and forty tests later `test_guardrails_client.py` constructs a
client with a fake boto3 session. Neither test is measuring anything against the held-out set, and the
combination is meaningless -- but the guard cannot tell, because from its point of view both things
happened in one process.

**This does not weaken the guard where it matters.** Scripts and `make eval` run outside pytest and get no
reset, so a real undeclared measurement still raises. `tests/unit/test_holdout_ledger.py` deliberately
drives the pair within a single test to prove the detection still works.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from evals.holdout_ledger import reset_process_state


@pytest.fixture(autouse=True)
def _isolate_holdout_guard_state() -> Iterator[None]:
    reset_process_state()
    yield
    reset_process_state()
