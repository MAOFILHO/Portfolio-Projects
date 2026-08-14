"""Cold-start attribution for `_build_graph()` — the instrument behind `docs/RESULTS.md` §11.8.

Committed retroactively, Phase 9 criterion 1 follow-up (2026-08-14): the script that produced §11.8's
table lived only in the session scratchpad and was gone by the next session (`PROJECT_STATE.md`, "Profiling
script kept in the session scratchpad, not committed"). Marco's instruction on seeing that: keep
instruments, not scratch them. Reconstructed here from §11.8's method paragraph and the current source of
`_build_graph()`, not from the lost original bytes — if a re-run disagrees with §11.8's numbers, check this
script against `_build_graph()` for drift (see `profile()`'s docstring) before assuming the deployed system
changed.

WHAT THIS MEASURES, AND WHAT IT DOESN'T
    Instruments `_build_graph()` (`src/fnol_voice_agent/api/lex_codehook.py`) with `time.monotonic()`
    around each of its statements, in the same order, run as a standalone script — never imported by
    anything else in the process, so nothing pre-warms `sys.modules` before the first timer starts. This
    attributes RELATIVE proportions inside `_build_graph()` — which phase dominates — not the ABSOLUTE
    10,337–11,421ms measured on the deployed Lambda (`RESULTS.md` §11.5/§11.7). §11.8 Finding 3: even the
    slowest of three local runs sat 3,467–4,551ms under that real figure. Two unconfirmed, unsourced
    candidates for the remainder are named there (Lambda's 512MB memory → CPU share; `/opt`'s real storage
    substrate vs. a local bind mount) — neither is asserted as a number here or there.

HOW TO GET A COMPARABLE NUMBER — fresh interpreter, real layer, real base image
    A single run cannot distinguish a code property from a container-startup artifact. §11.8 Finding 2:
    the two boto3-client-construction phases were the ENTIRE source of a 3× outlier on the first container
    invocation of a session — a cold host-side page cache on the bind-mounted layer directory, nothing in
    `_build_graph()` itself. Run this at least three times, each its own `docker run --rm` (fresh
    interpreter every time — not a loop inside this script, which would reuse `sys.modules` and measure
    something else), against the AWS-published Lambda base image with the real built layer mounted at
    Lambda's own layer path:

        docker run --rm --platform linux/arm64 \\
          -v "$(pwd):/repo:ro" \\
          -v "$(pwd)/infra/terraform/stacks/main/.terraform-build/layer/python:/opt/python:ro" \\
          -e PYTHONPATH=/repo/src:/opt/python \\
          public.ecr.aws/lambda/python:3.12 \\
          python3 /repo/scripts/profile_cold_start.py

    `.terraform-build/layer/python` has to exist first (a layer build, not necessarily a full `terraform
    apply` — this script only reads it). Run outside that container, or without `/opt/python` mounted, and
    the script still executes — against whatever's already on `PYTHONPATH`, e.g. a dev venv — as a plain
    correctness check that `_build_graph()`'s statements still run in order without error. It is not a
    timing measurement in that mode, and the script says so on stderr rather than printing numbers next to
    §11.8's as if they were comparable.

DUMMY IDENTIFIERS, ZERO AWS, ZERO COST
    `FNOL_CHECKPOINT_TABLE` / `FNOL_VECTOR_TABLE` / `FNOL_GUARDRAIL_ID` / `FNOL_GUARDRAIL_VERSION` default
    to clearly-fake values below (override with real `docker run -e` flags if a specific value ever
    matters, which it shouldn't). Every phase here is construction only, never a read or a write —
    confirmed against each constructor's own source before this script was written: `DynamoDBSaver`,
    `DynamoVectorStore`, `BedrockEmbedder`, `BotoBedrockConverseClient`, and `BedrockGuardrailClient` are
    all pure boto3-client/string construction with no network I/O at `__init__` time. Dummy, non-blank
    guardrail id/version are required precisely so the constructor is actually exercised — a blank id or
    version makes `_build_graph()` skip it entirely, which would silently under-measure this phase, the
    same way it reads 0.0ms in §11.8 for a different reason (lazy client, real id/version, no boto3 call
    until `apply_guardrail()`). `ADR-013`: no `mock_aws()` anywhere in this file — not needed, nothing here
    ever reaches the network. Cost: $0.00.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any, Callable

# Set before any project import -- `DEFAULT_REGION` and the table/guardrail identifiers are read at
# import- or construction-time inside the phases below, and must already be in `os.environ` when that
# happens. `setdefault` so a real `docker run -e ...` override still wins.
os.environ.setdefault("FNOL_CHECKPOINT_TABLE", "profile-dummy-checkpoint-table")
os.environ.setdefault("FNOL_VECTOR_TABLE", "profile-dummy-vector-table")
os.environ.setdefault("FNOL_GUARDRAIL_ID", "profile-dummy-guardrail-id")
os.environ.setdefault("FNOL_GUARDRAIL_VERSION", "DRAFT")

# Lambda's real layer mount path -- if present, this run is inside a container with the actual built
# layer, and its numbers are comparable to §11.8. If absent, `main()` warns rather than reporting numbers
# as if they were.
_LAYER_MOUNT = Path("/opt/python")
_ON_LAMBDA_LAYER = _LAYER_MOUNT.is_dir()
if _ON_LAMBDA_LAYER and str(_LAYER_MOUNT) not in sys.path:
    sys.path.insert(0, str(_LAYER_MOUNT))


def _phase(label: str, fn: Callable[[], Any]) -> tuple[Any, tuple[str, float]]:
    """Runs `fn`, returns its result plus `(label, elapsed_ms)` -- the one shared timing primitive so
    every phase below is measured identically."""
    start = time.monotonic()
    result = fn()
    elapsed_ms = (time.monotonic() - start) * 1000.0
    return result, (label, elapsed_ms)


def profile() -> list[tuple[str, float]]:
    """Hand-mirrors `_build_graph()`'s statements (`src/fnol_voice_agent/api/lex_codehook.py`), in the
    same order, each wrapped in `_phase()`. Deliberately not a wrapper that imports and instruments the
    real function in place -- there is no way to get per-statement timing out of an unmodified function
    without either editing production code to add timers (not this script's place to do) or reimplementing
    its statements here. The tradeoff is real: this drifts silently if `_build_graph()`'s statements,
    order, or construction arguments change. Keep this function in sync with `_build_graph()` in the same
    commit as any change there -- the same discipline `bot.yaml.tftpl` needed after `D78` for a different
    kind of drift.
    """
    phases: list[tuple[str, float]] = []

    def _import_graph() -> Any:
        from fnol_voice_agent.agents.graph import build_graph

        return build_graph

    build_graph, timing = _phase("import agents.graph", _import_graph)
    phases.append(timing)

    def _import_rest() -> tuple[Any, ...]:
        from fnol_voice_agent.aws.bedrock_router import get_bedrock_runtime_client
        from fnol_voice_agent.aws.checkpointer import build_checkpointer
        from fnol_voice_agent.config.settings import DEFAULT_REGION
        from fnol_voice_agent.guardrails.client import BedrockGuardrailClient
        from fnol_voice_agent.knowledge.ingest import BedrockEmbedder, DynamoVectorStore

        return (
            get_bedrock_runtime_client,
            build_checkpointer,
            DEFAULT_REGION,
            BedrockGuardrailClient,
            BedrockEmbedder,
            DynamoVectorStore,
        )

    rest, timing = _phase("import (4 more modules, combined)", _import_rest)
    phases.append(timing)
    (
        get_bedrock_runtime_client,
        build_checkpointer,
        default_region,
        guardrail_client_cls,
        embedder_cls,
        vector_store_cls,
    ) = rest

    checkpointer, timing = _phase(
        "construct DynamoDBSaver",
        lambda: build_checkpointer(os.environ["FNOL_CHECKPOINT_TABLE"], region=default_region),
    )
    phases.append(timing)

    vector_store, timing = _phase(
        "construct DynamoVectorStore",
        lambda: vector_store_cls(table_name=os.environ["FNOL_VECTOR_TABLE"], region=default_region),
    )
    phases.append(timing)

    embedder, timing = _phase(
        "construct BedrockEmbedder", lambda: embedder_cls(region=default_region)
    )
    phases.append(timing)

    bedrock_caller, timing = _phase(
        "construct bedrock-runtime client",
        lambda: get_bedrock_runtime_client(region=default_region),
    )
    phases.append(timing)

    guardrail_id = os.environ["FNOL_GUARDRAIL_ID"]
    guardrail_version = os.environ["FNOL_GUARDRAIL_VERSION"]
    guardrail_client, timing = _phase(
        "construct BedrockGuardrailClient",
        lambda: guardrail_client_cls(guardrail_id, guardrail_version, region=default_region),
    )
    phases.append(timing)

    _, timing = _phase(
        "build_graph() assemble+compile",
        lambda: build_graph(
            vector_store=vector_store,
            embedder=embedder,
            bedrock_caller=bedrock_caller,
            guardrail_client=guardrail_client,
            checkpointer=checkpointer,
        ),
    )
    phases.append(timing)

    return phases


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of the printed table.",
    )
    args = parser.parse_args(argv)

    if not _ON_LAMBDA_LAYER:
        print(
            "=== WARNING: /opt/python not mounted -- this is NOT the real built layer at Lambda's real "
            "mount path. This run only checks that _build_graph()'s statements still execute in order; "
            "its timings are NOT comparable to docs/RESULTS.md §11.8 or to a real cold start. See this "
            "script's module docstring for the docker invocation that restores fidelity. ===",
            file=sys.stderr,
        )
    print(
        f"=== interpreter={platform.python_version()}  machine={platform.machine()}  "
        f"layer_mounted={_ON_LAMBDA_LAYER} ===",
        file=sys.stderr,
    )

    phases = profile()
    total_ms = sum(ms for _, ms in phases)

    if args.json:
        payload = {
            "layer_mounted": _ON_LAMBDA_LAYER,
            "machine": platform.machine(),
            "phases": [{"phase": label, "ms": round(ms, 1)} for label, ms in phases],
            "total_ms": round(total_ms, 1),
        }
        print(json.dumps(payload, indent=2))
    else:
        print(f"{'phase':38} {'ms':>10}")
        for label, ms in phases:
            print(f"{label:38} {ms:10.1f}")
        print(f"{'TOTAL':38} {total_ms:10.1f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
