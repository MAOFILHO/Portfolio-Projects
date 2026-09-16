"""Shared helpers for this project's fail-closed static tree scanners (check_b3_allowlist.py,
check_no_phone_number_release.py, check_aoai_key_migration_consistency.py).

Extracted 2026-09-16 -- a code-review Standards-axis pass on Phase 7's first two commits found the
new D5 check's scan/report loop closely mirroring B3's own, already-existing one: compile patterns,
walk a file list, resolve a match offset to a line number, flatten a snippet for display, print a
uniform violation list. What was actually identical across all of them is pulled out here --
deliberately just `lineno`, `flatten`, and the print-and-exit-code tail, not a speculative scanning
framework. Each check keeps its own pattern set and its own violation-collection logic (B3's is
conditional against a live allowlist, D5's is any-match-is-a-violation, and they should stay that
different rather than be forced into one shape neither needs).
"""


def lineno(text, offset):
    """1-indexed line number of a character offset -- so a match spanning multiple lines (e.g. a
    literal pair wrapped across lines) still gets a sensible line to point at: where it starts."""
    return text.count("\n", 0, offset) + 1


def flatten(snippet):
    """Collapse whitespace/newlines in a matched snippet to one line, for display only."""
    return " ".join(snippet.split())


def report(violations, title, footer, ok_message):
    """Print a uniform violation list and return the process exit code.

    `violations` is a list of (relative_path, lineno, reason, flattened_snippet) tuples, already
    collected by the caller. Returns 1 if `violations` is non-empty (having printed `title`, each
    violation, then `footer`), else prints `ok_message` and returns 0.
    """
    if violations:
        print(f"{title}\n")
        for path, line, reason, snippet in violations:
            print(f"  {path}:{line}: {reason}")
            print(f"      {snippet}")
        print(f"\n{footer}")
        return 1

    print(ok_message)
    return 0
