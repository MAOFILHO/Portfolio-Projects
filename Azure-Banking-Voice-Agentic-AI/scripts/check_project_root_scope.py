"""Reject staged writes outside `PROJECT_ROOT` -- the tooling backstop `CLAUDE.md`'s scope rule never had.

WHY THIS EXISTS

    Mirrors `AWS-Insurance-FNOL-Voice-Agentic-AI/scripts/check_project_root_scope.py`, this project's
    sibling in the `Portfolio-Projects` monorepo (root `CLAUDE.md`: "no shared code between them"). FNOL
    earned this script the hard way -- `.serena/.gitignore` and `.serena/project.yml` committed outside
    its `PROJECT_ROOT` with no approval, on a docs-only commit where a broad `git add` silently swept in
    two untracked files sitting one level up. Azure-Banking-Voice-Agentic-AI adopts the same backstop
    from day one rather than waiting to earn it the same way.

WHAT IT CHECKS

    Every staged path (`git diff --cached --name-only`) must start with `PROJECT_ROOT` (this project's
    own directory, relative to the git repo root) -- with an exception only for a path named in
    `ALLOWLIST`, each with its own recorded, absolute-path approval. `ALLOWLIST` starts empty: no
    exception has been asked for or granted yet. Do not add one in advance of an actual approval.

RUNS AS

    Invoked by the shared dispatcher `scripts/git-hooks/pre-commit` at the monorepo root (installed to
    `.git/hooks/pre-commit` via this project's `make install-hooks`) whenever a commit stages any file
    under this project's `PROJECT_ROOT`. Also runnable standalone as `make verify-project-root-scope`
    against whatever is currently staged. The dispatcher is shared with FNOL's own check (and any future
    project's) because git allows only one `.git/hooks/pre-commit` per repo -- see that script's own
    header for why a single shared shim beats two independent ones silently overwriting each other.

LIMITATION, STATED RATHER THAN LEFT IMPLICIT

    This only protects a clone that has run `make install-hooks`. A fresh clone, or `git commit
    --no-verify`, bypasses it entirely -- a local hook is a backstop for this workspace, not a substitute
    for a server-side check. No CI-side equivalent exists yet.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

#: This project's own directory, relative to the git repository root. Every staged path must fall under
#: this prefix unless it is named in `ALLOWLIST` below.
PROJECT_ROOT = "Azure-Banking-Voice-Agentic-AI/"

#: Paths outside `PROJECT_ROOT` that are allowed to be staged, because a specific, recorded,
#: absolute-path approval exists for each one. Add an entry only alongside the approval that licenses it
#: -- never in advance of one. Starts empty: no exception has been requested yet.
ALLOWLIST: frozenset[str] = frozenset()


def scope_violations(
    staged_paths: list[str],
    project_root: str = PROJECT_ROOT,
    allowlist: frozenset[str] = ALLOWLIST,
) -> list[str]:
    """Return the subset of `staged_paths` that are outside `project_root` and not in `allowlist`.

    Pure function, no git/filesystem access -- this is what a unit test or a demonstration probes
    directly, so the logic is checkable without staging anything for real.
    """
    return [
        path
        for path in staged_paths
        if not path.startswith(project_root) and path not in allowlist
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
            "(Azure-Banking-Voice-Agentic-AI/) without an entry in ALLOWLIST."
        )
    )
    parser.parse_args(argv)

    git_root = _git_root()
    staged = _staged_paths(git_root)

    print(f"check-project-root-scope: {len(staged)} staged path(s), root {git_root}")

    violations = scope_violations(staged)

    if violations:
        print("check-project-root-scope: FAILED — staged path(s) outside PROJECT_ROOT:", file=sys.stderr)
        for path in violations:
            print(f"  {path}", file=sys.stderr)
        print(
            "\nPROJECT_ROOT is Azure-Banking-Voice-Agentic-AI/. A write outside it needs explicit "
            "approval requested by absolute path before it is committed. If that approval exists, add "
            "the path to ALLOWLIST in scripts/check_project_root_scope.py alongside a citation of where "
            "the approval is recorded.",
            file=sys.stderr,
        )
        return 1

    print("check-project-root-scope: ok — every staged path is inside PROJECT_ROOT or explicitly allowlisted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
