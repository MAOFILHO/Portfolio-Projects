.PHONY: ingest test lint format typecheck eval bootstrap verify-backend verify-inference \
        verify-destroy-scope

# Only targets that are genuinely functional today are listed here. The Definition of Done's canonical
# targets (bootstrap, deploy, destroy, eval, redteam, simulate, verify-billable — see CLAUDE.md) are added
# in the phases that build what they need: nothing may be stubbed out and labeled "would work" before it
# actually does (CLAUDE.md's own rule, applied to this file too).

VENV := .venv/bin
BOOTSTRAP_DIR := infra/terraform/bootstrap

# One-time state backend setup: a versioned, encrypted, public-access-blocked S3 bucket, with native S3
# state locking (Terraform >= 1.10 `use_lockfile`) rather than a billable DynamoDB lock table.
#
# Idempotent -- re-running it on an existing backend is a no-op plan. NOT reached by `make destroy`, and
# the bucket carries `prevent_destroy`: a backend that can delete itself takes every other stack's state
# with it, including stacks/telephony, whose state points at a number that cannot be re-claimed for 180
# days.
#
# Cost: $0.00/mo. State objects are kilobytes against a 5 GB account-age-independent free allowance.
bootstrap:
	cd $(BOOTSTRAP_DIR) && terraform init -input=false && terraform apply -input=false
	@$(MAKE) --no-print-directory verify-backend

# A `backend "s3"` block cannot interpolate variables, so every stack repeats the bucket name as a
# literal. This target is what turns that duplication from trusted into checked: it compares each
# hardcoded name against the bootstrap stack's actual output and fails on any mismatch.
#
# The failure it exists to catch is quiet. A stack pointed at a bucket name that does not exist does not
# silently misbehave -- but a stack pointed at a name that differs only by region suffix would init a
# fresh, empty state and then plan to CREATE resources that already exist.
verify-backend:
	@expected=$$(cd $(BOOTSTRAP_DIR) && terraform output -raw state_bucket 2>/dev/null); \
	if [ -z "$$expected" ]; then \
		echo "verify-backend: no bootstrap output -- run 'make bootstrap' first"; exit 1; fi; \
	echo "verify-backend: expecting bucket $$expected"; \
	rc=0; \
	for f in $$(grep -rlE '^[[:space:]]*backend "s3" \{' infra/terraform --include='*.tf'); do \
		found=$$(awk '/^[[:space:]]*backend "s3" \{/,/^  }/' $$f | sed -n 's/.*bucket *= *"\([^"]*\)".*/\1/p'); \
		if [ "$$found" != "$$expected" ]; then \
			echo "  MISMATCH $$f: '$$found'"; rc=1; \
		else echo "  ok       $$f"; fi; \
	done; \
	exit $$rc

# Chunk + embed the policy corpus, load it into the vector store. Free by default: mock embeddings + a
# local in-memory table (see src/fnol_voice_agent/knowledge/ingest.py's module docstring). Real Bedrock
# embeddings require explicitly passing ARGS="--embeddings bedrock", billed against the $5 Phases 3-7
# standing-approval cap — never triggered by this target alone.
ingest:
	$(VENV)/python -m fnol_voice_agent.knowledge.ingest $(ARGS)

# Evaluation harness. Tier A only today: deterministic, no model calls, no AWS credentials, $0.00.
# Exits non-zero on any Tier A gate breach, which is what makes it usable as a CI gate.
#
# Tier B (real Bedrock calls, cost-gated against the $5 standing cap and the $1.00 Phase 6 sub-budget)
# lands at Stage 6 and will be opt-in behind an explicit flag — never the default, so this target cannot
# spend money by accident. Same posture as `ingest`: the free path is what you get for typing the name.
eval:
	$(VENV)/python -m evals.report $(ARGS)

# Run the unit test suite. No AWS credentials required — moto covers every AWS call in tests.
test:
	$(VENV)/python -m pytest tests/unit -v

# Constraint 17's property, asserted against the live resource rather than against the plan that
# created it. `ADR-016` wraps each `us.*` SYSTEM-DEFINED profile in an APPLICATION profile so Bedrock
# spend can carry a cost allocation tag; the risk Marco named on approving it is that the wrapper
# collapses the region set -- "exactly the shape where an assumption could hold in the docs and not in
# the response metadata."
#
# So this reads `GetInferenceProfile` from the API, not Terraform state, and fails if any of the three
# cross-region profiles reports fewer than 3 regions. `embedding` is expected to report 1: Titan has no
# us.* profile to inherit from, which is a documented single-region wrap and not a regression.
verify-inference:
	@$(VENV)/python scripts/verify_inference_profiles.py

# Constraint 16. Asserts that nothing destroyable can reach the protected DID: prevent_destroy is on the
# phone-number resource, its state key is unique, and no Makefile recipe names its directory. Static, no
# AWS calls, and it also runs inside `make test` -- see tests/unit/test_destroy_scope.py.
#
# There is no `destroy` target yet, so the third check currently passes with nothing to find. That is
# precisely when it has to be written: the moment the target appears is the moment nobody is looking.
verify-destroy-scope:
	@$(VENV)/python scripts/verify_destroy_scope.py

# ruff + black --check
# Everything that is checked. `evals` and `scripts` were outside this list until Phase 7
# Stage 0 -- the entire eval harness, i.e. the code that produces every published number, was
# never linted or type-checked while the phase reported "ruff/black/mypy strict clean".
#
# `redteam` added at Stage R, and it is the same omission one directory over: the note above was
# written about `evals`/`scripts` and did not generalise to the other directory that produces a
# published number. `make redteam`'s 11/11 came from code neither linted nor type-checked. It passed
# both on the first try, which is luck, not evidence -- the point is that nothing was checking.
CHECKED = src tests evals scripts redteam
# mypy --strict covers production + measurement code. `tests` is deliberately excluded and
# the reason is stated rather than left implicit: langgraph's StateGraph.add_node/Pregel.invoke
# overloads reject plain callables and dict payloads under strict mode. Those are third-party
# stub friction, not defects in the tests, and silencing ~20 of them with `type: ignore` would
# add noise without adding a single check. Revisit if langgraph's stubs improve.
TYPED = src evals scripts redteam

lint:
	$(VENV)/ruff check $(CHECKED)
	$(VENV)/black --check $(CHECKED)

# ruff --fix + black
format:
	$(VENV)/ruff check --fix $(CHECKED)
	$(VENV)/black $(CHECKED)

# mypy --strict
typecheck:
	PYTHONPATH=. $(VENV)/mypy $(TYPED)
