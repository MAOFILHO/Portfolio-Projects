.PHONY: install-hooks verify-project-root-scope install test lint

# Only targets that are genuinely functional today are listed here -- mirrors FNOL's own Makefile
# discipline (AWS-Insurance-FNOL-Voice-Agentic-AI/Makefile: "nothing may be stubbed out and labeled
# 'would work' before it actually does"). The canonical targets this project will eventually need
# (install, test, lint, fixtures, deploy, teardown -- see docs/PLAN.md "Project layout") are added in
# the phases that build what they need.

VENV := .venv/bin

# Where each suite's WHOLE output is kept, regardless of what the caller does to this target's
# stdout. `docs/phase4/findings.md` "Open: one unreproduced test failure": a run reported
# `FAILED (failures=1)` and the failure's name was lost, because that run was piped through `grep`
# and only the summary line survived. A name is the one thing that would settle it, so the run now
# keeps its own copy that no downstream pipe can trim.
#
# Redirect-then-cat rather than `tee`: `tee` returns its own exit status, which would turn a red
# suite green, and `set -o pipefail` is not available in the `/bin/sh` GitHub's ubuntu runners use.
# Both suites finish in about a second, so nothing is lost by printing at the end instead of
# streaming.
VOICE_AGENT_TEST_LOG := .test-output-voice-agent.log
CORE_BANKING_TEST_LOG := .test-output-mock-core-banking.log

# STAGED-not-tree scope: checks whatever is CURRENTLY STAGED via `git diff --cached`, not the working
# tree -- this is the manual escape hatch and the same check `install-hooks` wires into the shared
# pre-commit dispatcher, not something a future `make lint` would call (lint checks the whole tree; this
# checks a commit-in-progress, which only exists mid-`git add`).
verify-project-root-scope:
	@if [ -x "$(VENV)/python" ]; then $(VENV)/python scripts/check_project_root_scope.py; \
	else python3 scripts/check_project_root_scope.py; fi

# Installs everything `make test` needs: the voice-agent package, editable, with its dependencies.
# The two separate requirements.txt files this project carried through Phase 1 were consolidated
# into voice-agent/pyproject.toml by the Phase 2.1 restructure (issue #17). Installing the package
# is also what lets tests/ import it normally -- no sys.path manipulation. .venv/ is gitignored, so
# a fresh clone has neither the venv nor these packages until this runs; creates the venv if
# missing so `make test` works right after clone with no separate manual step to remember.
install:
	@test -x "$(VENV)/python" || python3 -m venv .venv
	@$(VENV)/pip install -q -e "voice-agent[test]"
	@$(VENV)/pip install -q -e "mock-core-banking[dev]"

# Stdlib unittest, not pytest -- no test runner was installed and a handful of tests didn't justify
# adding one.
# Both deployables, one command. They stay separate suites -- docs/PLAN.md decision 9 is
# "shared-nothing", and mock-core-banking's tests must run without the voice agent installed
# (issue #30). This target is the convenience of running both, not a merging of them.
test: install
	@$(VENV)/python -m unittest discover -s tests -v > $(VOICE_AGENT_TEST_LOG) 2>&1; status=$$?; \
	  cat $(VOICE_AGENT_TEST_LOG); \
	  test $$status -eq 0 || { echo "make test: whole output kept in $(VOICE_AGENT_TEST_LOG)"; exit $$status; }
	@$(VENV)/python -m unittest discover -s mock-core-banking/tests -v > $(CORE_BANKING_TEST_LOG) 2>&1; status=$$?; \
	  cat $(CORE_BANKING_TEST_LOG); \
	  test $$status -eq 0 || { echo "make test: whole output kept in $(CORE_BANKING_TEST_LOG)"; exit $$status; }

# docs/PLAN.md's Verification section: "make lint runs ruff + mypy. CI static check enforces B3's
# allowlist across the tree." Added in the phase that makes all three actually pass (issue #23),
# per this Makefile's standing rule against stubbing a target ahead of its work.
#
# The B3 static check is deliberately separate from the runtime boot guard: the guard proves what
# is deployed is approved, this proves what is written in the source is approved. Neither covers
# the other's gap.
#
# check_no_phone_number_release.py is Phase 7 D5: no Bicep module or deploy tooling may create,
# delete, or replace the ACS phone number, or use Complete-mode deployment, anywhere in the tree.
lint: install
	@$(VENV)/pip install -q -e "voice-agent[dev]"
	@$(VENV)/ruff check --config voice-agent/pyproject.toml voice-agent mock-core-banking tests scripts
	@$(VENV)/mypy --config-file voice-agent/pyproject.toml voice-agent/azbank_voice_agent mock-core-banking/azbank_core_banking
	@$(VENV)/python scripts/check_b3_allowlist.py
	@$(VENV)/python scripts/check_no_phone_number_release.py

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
