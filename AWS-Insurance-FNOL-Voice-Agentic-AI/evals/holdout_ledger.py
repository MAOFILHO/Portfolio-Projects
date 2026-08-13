"""The independent-set guard and its append-only ledger — Phase 7 `BUILD-PLAN.md` §2.2/§2.3.

Marco's constraint `C2`: *"The independent set is spent for L1. Do not tune L2 against it either — that set
is now the only uncontaminated measure of the union, and Phase 7 will want it intact to verify the fix."*

**The rule this implements is not "use it once."** Repeated *sampling* of a fixed configuration is
legitimate and necessary — L2 is stochastic, and `RESULTS.md` already says 26/26 on one run is not a rate.
What contaminates a held-out set is changing the system **in response to what it showed**. So:

    one configuration, any number of samples.

**What is guarded is the combination, not the read.** The first version of this module locked
`load_holdout(INDEPENDENT)` outright, and the regression gate immediately failed the build: locking the set
deleted `L1 recall, independent held-out set` from the Tier A baseline, and the gate treats a metric that
disappears as a breach -- *"deleting a metric is the cheapest way to make a gate green"*. That was the gate
being right. The L1 number on this set is **already spent** (Marco: *"the independent set is spent for L1"*)
and is published with a contamination warning, so continuing to report it costs nothing and drops a live
regression check if removed. Deterministic, offline, $0, and it reveals nothing new run-to-run.

What must stay unspent is the **model-based** measurement -- the union recall figure that will judge the
Phase 7 fix. So the guard is on the pair, in the style of `ADR-013`'s mock guard:

1. **Reading the independent set and then constructing a real Bedrock client** -- in either order, anywhere
   in the same process -- raises unless a `verification_run(...)` is active. A deterministic L1 pass reads
   the set and never builds a client, so it is unaffected. `scripts/measure_l2_precision.py` does both, so
   it must declare.
2. Entering that block **appends to the ledger**. There is no way to declare a run without leaving a record,
   because the guard and the recorder are one context manager rather than two things a future session has to
   remember to pair up. A ledger that can be skipped measures only the diligence of whoever last touched the
   harness.

The failure mode being guarded against is not a decision to cheat -- it is a convenient `make eval` in the
middle of a tuning loop.

`RESULTS.md` publishes **the count of distinct configuration fingerprints ever measured against this set.**
One is an honest verification. Six is de-facto tuning, visible to any reader without taking anyone's word
for it -- which is the point of publishing a number that can only ever embarrass us.

**Aborted runs are still recorded.** A run that raises appends an entry with `status: "aborted"`. Not as a
penalty -- a dropped connection is not misconduct -- but because a run that can be retried without leaving
a trace can be retried until it looks good, and the distinct-fingerprint count is unaffected by honest
retries of the same configuration anyway.

The ledger is append-only by convention *and* by check: loading it verifies that every entry already
present is still present and unchanged, so a rewrite of history fails loudly on the next append rather
than silently succeeding.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fnol_voice_agent.aws import mock_guard

LEDGER_PATH = Path(__file__).resolve().parent / "holdout_ledger.json"

_REPO_ROOT = Path(__file__).resolve().parent.parent

# Everything whose change makes a measurement a measurement of a *different system*. Deliberately
# includes the L1 lexicon source: the union metric this set exists to measure is L1 u L2, so a lexicon
# edit changes the configuration even though it touches no prompt.
#
# THE GUARDRAIL WAS MISSING FROM THIS TUPLE UNTIL STAGE 8, AND THAT WAS A DEFECT IN THE PUBLISHED
# COUNT ITSELF. Ledger entries #2 and #3 measured guardrail **v1** -- the configuration RESULTS.md
# section 3.9 records as a C1 breach that would have taken union recall from 1.000 to roughly 0.62 --
# and they carry the fingerprint `eb82350fee3e4555`. The guardrail was then narrowed to v2. The
# fingerprint did not move, because this tuple listed only Python under `src/`. Two materially
# different safety configurations hashed to the same value, and the number RESULTS.md publishes as
# "distinct configurations ever measured against this set" would have said 2 for three measurements
# of two different systems.
#
# The tuple was authored when the guardrail did not exist. Nobody widened it when the guardrail
# arrived, because the fingerprint's own tests all passed -- they exercise the files that ARE in the
# tuple. This is RESULTS.md section 3.10's general form again, one directory over: the check covered
# exactly the surface its author had in mind.
#
# The .tf file is the ARTIFACT, not the outcome -- a console edit or a half-applied plan leaves it
# unchanged while the live guardrail differs. That gap is closed at run time instead of here:
# `scripts/measure_composed_pipeline.py` calls `GetGuardrail` and records a hash of the LIVE
# configuration in the ledger entry. Hashing the file keeps this function offline and free, which it
# must be -- it is called inside `verification_run`, including in unit tests.
# Widened at Stage 8 from three files to six, because the measurement itself widened: the thing being
# verified is now L1 -> guardrail -> L2 as a composition, so every file that determines that path is
# part of the configuration. `graph.py` is over-inclusive on purpose -- an edit to an unrelated intent
# node moves the hash -- and over-inclusive is the safe direction: it can only inflate the published
# distinct-fingerprint count, which is the number designed to embarrass us.
#
# Widened a THIRD time at Phase 8 Stage 4, for the reason `D53` itself predicted: a defensible per-
# component change moved the composition, and this project's own Lambda wrapper around the graph is
# exactly that shape. `api/lex_codehook.py` decides whether L1 fires on the raw text before the graph is
# even invoked (its own bypass path, see the module docstring), and `agents/l3_lexicon.py` is a new
# detector this stage introduced that participates in the same pre-graph decision. `aws/checkpointer.py`
# determines whether `filled_slots` persists correctly across turns at all -- and `D79`'s
# `injuries_present`-confirmed-true escalation depends on that persistence working, not merely on the
# graph's own code. Same over-inclusive philosophy as `graph.py` above: an edit to the checkpointer's
# retry/backoff behaviour moves the hash even though it changes no detection logic, and that is the safe
# direction to be wrong in.
_FINGERPRINT_SOURCES = (
    "src/fnol_voice_agent/agents/lexicon.py",
    "src/fnol_voice_agent/aws/bedrock_router.py",
    "src/fnol_voice_agent/config/settings.py",
    "infra/terraform/stacks/guardrails/main.tf",
    "src/fnol_voice_agent/guardrails/client.py",
    "src/fnol_voice_agent/agents/nodes/guardrails_nodes.py",
    "src/fnol_voice_agent/agents/graph.py",
    "src/fnol_voice_agent/api/lex_codehook.py",
    "src/fnol_voice_agent/agents/l3_lexicon.py",
    "src/fnol_voice_agent/aws/checkpointer.py",
)


class UndeclaredHoldoutMeasurementError(RuntimeError):
    """A model call and a read of the independent set met in one process outside a declared run."""


class LedgerTamperError(RuntimeError):
    """An entry that was already in the ledger has been changed or removed."""


def config_fingerprint() -> str:
    """A short hash of the system-under-test, computed from the live source rather than
    supplied by the caller -- a caller-supplied fingerprint is a caller-supplied claim.

    Hashes file *contents*, not import-time values, so a change to a prompt string, the
    tool schema, a model ID, either temperature, the L1 lexicon, or the guardrail's Terraform
    all move it. It does **not** move for a change to the eval harness itself, which is
    correct: rerunning a fixed system through a fixed better-instrumented script is still one
    configuration.

    Entries #1-#3 in the committed ledger were produced under a narrower three-file definition
    that omitted the guardrail (see `_FINGERPRINT_SOURCES`). Each entry stores the source list
    it was computed from, so the ledger says which definition produced which hash rather than
    presenting four values as if they were commensurable.
    """
    digest = hashlib.sha256()
    for relative in _FINGERPRINT_SOURCES:
        path = _REPO_ROOT / relative
        digest.update(relative.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


@dataclass
class VerificationRun:
    """Handed to the caller inside a `verification_run` block. Metrics are recorded on it
    as they are computed; whatever is present when the block exits is what gets written."""

    reason: str
    fingerprint: str
    samples_per_item: int
    metrics: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def record(self, **metrics: Any) -> None:
        self.metrics.update(metrics)

    def note(self, text: str) -> None:
        self.notes.append(text)


_active: VerificationRun | None = None

# Process-level facts. Two booleans rather than one because the hazard is order-independent: a script
# may load the set and then call Bedrock, or build a client and then load the set.
_independent_set_read = False
_real_bedrock_client_built = False

_MESSAGE = (
    "Undeclared measurement against evals/holdout/injury_phrasings_independent.yaml.\n\n"
    "This process has both read the independent set and constructed a real Bedrock client. That "
    "combination is the model-based measurement the set exists for -- the only uncontaminated reading "
    "of union escalation recall (C2) -- and spending it by accident, typically a `make eval` in the "
    "middle of a tuning loop, is what this guard prevents.\n\n"
    "If the measurement is intended, declare it:\n\n"
    "    from evals.holdout_ledger import verification_run\n"
    "    with verification_run(reason='...', samples_per_item=5) as run:\n"
    "        ...\n\n"
    "Entering that block appends to evals/holdout_ledger.json, and the count of distinct configuration "
    "fingerprints in it is published in RESULTS.md. If it is not intended, tune against "
    "evals/tuning/injury_phrasings_tuning.yaml instead -- that set exists to be spent.\n\n"
    "A deterministic L1-only pass over the independent set is NOT affected by this guard: it makes no "
    "model call, its number is already spent, and it stays in the regression baseline."
)


def independent_set_unlocked() -> bool:
    return _active is not None


def _check_pair() -> None:
    if _active is None and _independent_set_read and _real_bedrock_client_built:
        raise UndeclaredHoldoutMeasurementError(_MESSAGE)


def note_independent_set_read() -> None:
    """Called by `load_holdout` for the independent set. Reading alone is permitted."""
    global _independent_set_read
    _independent_set_read = True
    _check_pair()


def _note_real_client_built(_what: str) -> None:
    """Subscribed to `mock_guard`'s observer hook. Building a client alone is permitted."""
    global _real_bedrock_client_built
    _real_bedrock_client_built = True
    _check_pair()


# Registered at import, and the already-constructed count is read at the same time. Both halves are
# needed: the observer catches clients built after this module loads, and the count catches a process
# that built one first (a script that opens Bedrock and only later imports the eval harness). Without
# the second, the guard would be defeated by import order alone -- not a hypothetical, since scripts in
# this repo do their imports at the top and construct clients wherever is convenient.
mock_guard.register_real_client_observer(_note_real_client_built)
if mock_guard.real_client_count() > 0:  # pragma: no cover - order-dependent, has its own test
    _real_bedrock_client_built = True


def reset_process_state() -> None:
    """Test-only. Not an escape hatch: it clears the two observation flags, so calling it in
    application code would only defer the same exception to the next read or client build."""
    global _independent_set_read, _real_bedrock_client_built
    _independent_set_read = False
    _real_bedrock_client_built = False


def load_ledger(*, path: Path = LEDGER_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries = json.loads(path.read_text())
    if not isinstance(entries, list):
        raise LedgerTamperError(f"{path}: expected a JSON list of entries")
    return entries


def distinct_fingerprints(*, path: Path = LEDGER_PATH) -> list[str]:
    """The published number. Order of first appearance, so it reads as a history."""
    seen: list[str] = []
    for entry in load_ledger(path=path):
        fingerprint = entry.get("fingerprint", "")
        if fingerprint and fingerprint not in seen:
            seen.append(fingerprint)
    return seen


def _append(entry: Mapping[str, Any], *, path: Path = LEDGER_PATH) -> None:
    existing = load_ledger(path=path)
    if path.exists():
        # Append-only, checked rather than trusted: re-read what we are about to preserve and
        # confirm nothing already written has moved. Cheap, and it turns a rewritten ledger from a
        # silent success into a failure at the next append.
        reread = json.loads(path.read_text())
        if reread != existing:
            raise LedgerTamperError(f"{path} changed while being appended to")
    path.write_text(json.dumps([*existing, dict(entry)], indent=2) + "\n")


@contextmanager
def verification_run(
    *,
    reason: str,
    samples_per_item: int,
    path: Path = LEDGER_PATH,
) -> Iterator[VerificationRun]:
    """Unlocks the independent set for the duration of the block and appends a ledger entry
    on exit -- including when the block raises.

    `reason` is free text and goes in the ledger verbatim. It is not validated, because a
    validator on a justification string only teaches the next author what to write.

    Not re-entrant: nesting means two runs believe they own the same measurement, and the
    ledger would record one of them.
    """
    global _active
    if _active is not None:
        raise RuntimeError(
            f"verification_run is already active (reason={_active.reason!r}). Nesting would record "
            f"one entry for two measurements."
        )
    run = VerificationRun(
        reason=reason,
        fingerprint=config_fingerprint(),
        samples_per_item=samples_per_item,
    )
    _active = run
    started = datetime.now(UTC).isoformat(timespec="seconds")
    status = "ok"
    error: str | None = None
    try:
        yield run
    except BaseException as exc:  # noqa: BLE001 -- recorded, then re-raised unchanged
        status = "aborted"
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        _active = None
        _append(
            {
                "started_utc": started,
                "finished_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                "status": status,
                "error": error,
                "reason": run.reason,
                "fingerprint": run.fingerprint,
                "fingerprint_sources": list(_FINGERPRINT_SOURCES),
                "samples_per_item": run.samples_per_item,
                "git_commit": _git_commit(),
                "metrics": run.metrics,
                "notes": run.notes,
            },
            path=path,
        )


def _find_git_dir() -> Path | None:
    """The git root is this project's *parent* (the monorepo), so walk up rather than
    assuming a depth."""
    for candidate in (_REPO_ROOT, *_REPO_ROOT.parents):
        git_dir = candidate / ".git"
        if git_dir.is_dir():
            return git_dir
    return None


def _git_commit() -> str:
    """Best-effort, resolved by reading refs rather than shelling out. A ledger entry is
    still worth writing without it, so anything unreadable is recorded as `unknown` rather
    than failing a run that has already spent money."""
    git_dir = _find_git_dir()
    if git_dir is None:
        return "unknown"
    try:
        ref = (git_dir / "HEAD").read_text().strip()
    except OSError:
        return "unknown"
    if not ref.startswith("ref: "):
        return ref[:12]  # detached HEAD
    name = ref[5:]
    try:
        return (git_dir / name).read_text().strip()[:12]
    except OSError:
        pass
    try:
        for line in (git_dir / "packed-refs").read_text().splitlines():
            if line.endswith(f" {name}"):
                return line.split()[0][:12]
    except OSError:
        return "unknown"
    return "unknown"


# There is deliberately no environment-variable escape hatch. `ADR-013`'s mock guard set the
# precedent -- "no escape hatch" -- and the reasoning transfers exactly: a bypass that lives in a
# shell profile or a CI secret is invisible in a diff, and this guard's entire value is that
# spending the independent set has to be a visible, deliberate edit. CI declares a verification run
# by calling a script that opens the context manager, like everything else does.
