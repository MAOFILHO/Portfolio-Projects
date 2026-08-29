.PHONY: install-hooks verify-project-root-scope test

# Only targets that are genuinely functional today are listed here -- mirrors FNOL's own Makefile
# discipline (AWS-Insurance-FNOL-Voice-Agentic-AI/Makefile: "nothing may be stubbed out and labeled
# 'would work' before it actually does"). The canonical targets this project will eventually need
# (install, test, lint, fixtures, deploy, teardown -- see docs/PLAN.md "Project layout") are added in
# the phases that build what they need.

VENV := .venv/bin

# STAGED-not-tree scope: checks whatever is CURRENTLY STAGED via `git diff --cached`, not the working
# tree -- this is the manual escape hatch and the same check `install-hooks` wires into the shared
# pre-commit dispatcher, not something a future `make lint` would call (lint checks the whole tree; this
# checks a commit-in-progress, which only exists mid-`git add`).
verify-project-root-scope:
	@if [ -x "$(VENV)/python" ]; then $(VENV)/python scripts/check_project_root_scope.py; \
	else python3 scripts/check_project_root_scope.py; fi

# Phase 1's mock-accounts module. Stdlib unittest, not pytest -- no test runner was installed yet
# and three tests don't justify adding one.
test:
	@python3 -m unittest discover -s tests -v

# `.git/hooks/` is not tracked by git -- a fresh clone has no hook until this runs once. The hook
# installed here is the SHARED monorepo dispatcher (../scripts/git-hooks/pre-commit), not a copy local to
# this project -- git allows only one `.git/hooks/pre-commit`, and this project shares that slot with
# AWS-Insurance-FNOL-Voice-Agentic-AI (and any future project that registers itself in the dispatcher).
# Running this target is safe to repeat and safe to run from either project: it always installs the same
# file, so it can never silently disarm the other project's scope check. See the dispatcher's own header
# comment for the full rationale (Marco-approved 2026-08-19, AskUserQuestion "Multi-project dispatcher").
install-hooks:
	@git_root=$$(git rev-parse --show-toplevel); \
	cp "$$git_root/scripts/git-hooks/pre-commit" "$$git_root/.git/hooks/pre-commit"; \
	chmod +x "$$git_root/.git/hooks/pre-commit"; \
	echo "install-hooks: installed shared dispatcher to $$git_root/.git/hooks/pre-commit"
