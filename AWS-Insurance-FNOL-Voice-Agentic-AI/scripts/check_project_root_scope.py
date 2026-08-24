"""Reject staged writes outside `PROJECT_ROOT` — the tooling backstop `CLAUDE.md`'s scope rule never had.

WHY THIS EXISTS

    `CLAUDE.md`'s scope rule ("writes outside PROJECT_ROOT require explicit approval, requested by
    absolute path, before the change") existed as prose only. Investigated 2026-08-15
    (`docs/RESULTS.md` §14.3) after `.serena/.gitignore` and `.serena/project.yml` were found committed
    outside `PROJECT_ROOT` at `e0452cb` with no approval: no pre-commit hook was installed, no path
    restriction existed in `.claude/settings.json`, no CI check inspected staged paths. The boundary was
    judgment-enforced only, and it failed on its easiest case — a docs-only commit, five in-scope files,
    where a broad `git add` silently swept in two untracked files sitting one level up. This script is the
    backstop: mechanical, not memory-dependent.

WHAT IT CHECKS

    Every staged path (`git diff --cached --name-only`) must start with `PROJECT_ROOT` (this project's own
    directory, relative to the git repo root) — with one named exception, `ALLOWLIST`, for the single file
    this project's own history has an actual, recorded, absolute-path approval for: the monorepo-root copy
    of the eval-gate workflow (Phase 10, `RESULTS.md` §12.1/§12.6).

    A new exception is not something this script grants on its own. `CLAUDE.md` names two more anticipated
    instances (the root `.gitignore`, the root `README.md` project index, Phase 12) — each gets its own
    approval when it happens, and `ALLOWLIST` is where that approval becomes mechanically enforced, not
    where it gets assumed in advance.

RUNS AS

    Invoked by the shared dispatcher `scripts/git-hooks/pre-commit` at the monorepo root (installed to
    `.git/hooks/pre-commit` via this project's `make install-hooks` — `.git/hooks/` is not tracked by git
    itself, so the hook must be (re)installed per clone), and as `make verify-project-root-scope` for a
    standalone check against whatever is currently staged. The dispatcher is shared with
    Azure-Banking-Voice-Agentic-AI's own check (and any future project's) as of 2026-08-19, because git
    allows only one `.git/hooks/pre-commit` per repo — see that dispatcher's own header for why a single
    shared shim beats two independent ones silently overwriting each other.

LIMITATION, STATED RATHER THAN LEFT IMPLICIT

    This only protects a clone that has run `make install-hooks`. A fresh clone, or `git commit
    --no-verify`, bypasses it entirely — a local hook is a backstop for this workspace, not a substitute
    for a server-side check. No CI-side equivalent exists yet; if one is wanted, it would compare
    `git diff --name-only <base>..<head>` the same way, inside the eval-gate workflow or a sibling job.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

#: This project's own directory, relative to the git repository root. Every staged path must fall under
#: this prefix unless it is named in `ALLOWLIST` below.
PROJECT_ROOT = "AWS-Insurance-FNOL-Voice-Agentic-AI/"

#: Paths outside `PROJECT_ROOT` that are allowed to be staged, because a specific, recorded,
#: absolute-path approval exists for each one. Add an entry only alongside the approval that licenses it —
#: never in advance of one, per `CLAUDE.md`'s scope rule ("monorepo convention is not pre-authorisation").
ALLOWLIST: frozenset[str] = frozenset(
    {
        # Phase 10, Marco-approved by absolute path (/Users/marco/K21/Real-world/.github/workflows/...),
        # verified byte-identical to the PROJECT_ROOT source. RESULTS.md §12.1/§12.6.
        ".github/workflows/aws-insurance-fnol-voice-agentic-ai-eval-gate.yml",
        # setup-matt-pocock-skills scaffold, Marco-approved 2026-08-16 by absolute path via
        # AskUserQuestion ("Yes, approve and record it") in the Claude Code session that authored
        # them, naming each of the four paths below explicitly:
        #   /Users/marco/K21/Real-world/CLAUDE.md
        #   /Users/marco/K21/Real-world/docs/agents/domain.md
        #   /Users/marco/K21/Real-world/docs/agents/issue-tracker.md
        #   /Users/marco/K21/Real-world/docs/agents/triage-labels.md
        # No RESULTS.md entry exists for this approval (it predates this project's own session log
        # for that date) — this comment is the citation.
        "CLAUDE.md",
        "docs/agents/domain.md",
        "docs/agents/issue-tracker.md",
        "docs/agents/triage-labels.md",
    }
)


def scope_violations(
    staged_paths: list[str],
    project_root: str = PROJECT_ROOT,
    allowlist: frozenset[str] = ALLOWLIST,
) -> list[str]:
    """Return the subset of `staged_paths` that are outside `project_root` and not in `allowlist`.

    Pure function, no git/filesystem access — this is what a unit test or a demonstration probes
    directly, so the logic is checkable without staging anything for real.
    """
    return [
        path for path in staged_paths if not path.startswith(project_root) and path not in allowlist
    ]


def _git_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(out.stdout.strip())


def _staged_paths(git_root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        check=True,
        capture_output=True,
        text=True,
        cwd=git_root,
    )
    return [line for line in out.stdout.splitlines() if line]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reject a commit whose staged paths fall outside PROJECT_ROOT "
            "(AWS-Insurance-FNOL-Voice-Agentic-AI/) without an entry in ALLOWLIST."
        )
    )
    parser.parse_args(argv)

    git_root = _git_root()
    staged = _staged_paths(git_root)

    print(f"check-project-root-scope: {len(staged)} staged path(s), root {git_root}")

    violations = scope_violations(staged)

    if violations:
        print(
            "check-project-root-scope: FAILED — staged path(s) outside PROJECT_ROOT:",
            file=sys.stderr,
        )
        for path in violations:
            print(f"  {path}", file=sys.stderr)
        print(
            "\nPROJECT_ROOT is AWS-Insurance-FNOL-Voice-Agentic-AI/. A write outside it needs explicit "
            "approval requested by absolute path, per CLAUDE.md's scope rule, before it is committed. If "
            "that approval exists, add the path to ALLOWLIST in "
            "scripts/check_project_root_scope.py alongside a citation of where the approval is recorded.",
            file=sys.stderr,
        )
        return 1

    print(
        "check-project-root-scope: ok — every staged path is inside PROJECT_ROOT or explicitly allowlisted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
