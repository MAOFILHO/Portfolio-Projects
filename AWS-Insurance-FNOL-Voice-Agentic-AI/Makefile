.PHONY: ingest test lint format typecheck eval bootstrap verify-backend verify-inference \
        verify-destroy-scope verify-flows verify-lex verify-charset verify-lambda-execution \
        deploy provision destroy teardown

# Only targets that are genuinely functional today are listed here. The Definition of Done's canonical
# targets (bootstrap, deploy, destroy, eval, redteam, simulate, verify-billable — see CLAUDE.md) are added
# in the phases that build what they need: nothing may be stubbed out and labeled "would work" before it
# actually does (CLAUDE.md's own rule, applied to this file too).

VENV := .venv/bin
BOOTSTRAP_DIR := infra/terraform/bootstrap

# Applied in this order and destroyed in the reverse of it. `stacks/main` reads the other two through
# `terraform_remote_state`, and a remote-state read of an unapplied stack fails with an empty-outputs
# error rather than a helpful one.
#
# The protected telephony stack is NOT in this list and must never be. `make verify-destroy-scope` fails
# the build if any recipe line here names its directory -- see scripts/verify_destroy_scope.py, and note
# that this comment is allowed to mention it while a recipe line is not.
DEPLOY_STACKS := infra/terraform/stacks/guardrails \
                 infra/terraform/stacks/inference \
                 infra/terraform/stacks/main
DESTROY_STACKS := infra/terraform/stacks/main \
                  infra/terraform/stacks/inference \
                  infra/terraform/stacks/guardrails

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

# Provision everything destroyable. Canonical name per the Definition of Done; `provision` is the alias
# kept for consistency with sibling projects in the monorepo.
#
# COST GATE. Every resource this creates is inside the `APPROVED: Phase 8` authorisation of 2026-08-12
# (provisioned resources, under $2) and the table backing that number is `docs/phase8/BUILD-PLAN.md` §3.
# At rest this stack is $0.00/month: Lambda, DynamoDB on-demand, S3 and CloudWatch are all free at this
# volume, Connect flows/queues/hours are not billed, and Lex bills per runtime REQUEST rather than for
# storing a bot. What costs money is a phone call, and nothing here places one.
#
# `-auto-approve` is deliberately ABSENT. CLAUDE.md requires the plan and its cost delta to be shown
# before an apply, and a target that skips the confirmation is a target that skips that rule.
deploy:
	@for d in $(DEPLOY_STACKS); do \
		echo "==> $$d"; \
		terraform -chdir=$$d init -input=false || exit 1; \
		terraform -chdir=$$d apply -input=false || exit 1; \
	done
	@$(MAKE) --no-print-directory verify-inference

provision: deploy

# Return to $0. Reverse order, because stacks/main reads the other two.
#
# WHAT THIS DOES NOT TOUCH, and both omissions are load-bearing:
#   * The protected DID. It lives in a stack this file does not name, in separate state, behind
#     `prevent_destroy`. `make verify-destroy-scope` fails the build if that ever stops being true.
#   * The state backend. A backend that can delete itself takes every other stack's state with it,
#     including the state that points at a number which cannot be re-claimed for 180 days.
#
# ONE CONSEQUENCE WORTH KNOWING BEFORE YOU RUN IT: destroying the guardrail stack deletes the published
# guardrail version that Phase 7's red-team results were measured against. `NOT-FIXED.md` #12 already
# records that shape -- publishing a new version deletes the old one -- and Phase 8 Stage 6 owns it. The
# evidence files and ledger entries stay attributable by `live_config_sha`; they stop being re-runnable.
destroy:
	@for d in $(DESTROY_STACKS); do \
		echo "==> $$d"; \
		terraform -chdir=$$d init -input=false || exit 1; \
		terraform -chdir=$$d destroy -input=false || exit 1; \
	done
	@$(MAKE) --no-print-directory verify-destroy-scope

teardown: destroy

# Constraint 18 and the contact tag schema, as a build failure rather than a convention.
#
# Fails on: any recorded participant, any screen-recorded participant, IVR recording left enabled, any
# occurrence of AnalyticsBehavior/ContactLens/RealTimeContactAnalysis, any contact tag key outside
# {Project, Env, FlowVersion}, and any flow path that can disconnect or transfer before it has been
# tagged. Flow files are globbed BY CONTENT -- some upstream exports have no extension, and an extension
# glob would examine zero files and pass.
#
# Also fails if it finds no flows at all, which is the same failure one level up.
verify-flows:
	@$(VENV)/python scripts/check_flows.py

# `D76`: aws_iam_role.lex_runtime failed at CreateRole on an em dash in `description` -- IAM
# validates that field against Latin-1 (tab/LF/CR plus U+0020-U+007E plus U+00A1-U+00FF) and rejects
# it, and terraform fmt/validate/plan and 488 unit tests all passed the string first. This is that check,
# moved to the front: every description/name/tag-value string under infra/terraform is in scope by
# default unless it never reaches an API (a variable/output's own description, an error_message) or is
# on the short exemption list in scripts/check_charset.py, each entry backed by a cited measurement.
#
# Also fails if an exemption's named file is in scope and no longer produces the match it was written
# for -- a stale exemption is a hole nobody is using, and this is the check that notices.
verify-charset:
	@$(VENV)/python scripts/check_charset.py

# Read the deployed Lex release back from the service and compare it against what Terraform declared.
#
# `RESULTS.md` §3.5.1 rule 1: the apply output is Terraform's record of its own request; the read is a
# fact. Everything is checked against the version THE ALIAS ACTUALLY POINTS AT, never against DRAFT --
# DRAFT is what an apply mutates, so a verifier reading it would agree with Terraform in exactly the
# cases where the deployment is broken.
#
# Catches, among others, the failure `AWS::Lex::BotVersion` produces by default: AWS documents that an
# unchanged DRAFT yields the PREVIOUS version rather than a new one, so the alias can keep serving an old
# definition while every artifact says otherwise. `release.yaml.tftpl` has a mechanism against that; this
# is the check that the mechanism worked.
#
# Control-plane reads only. Lex bills per runtime request; this costs $0.00.
verify-lex:
	@$(VENV)/python scripts/verify_lex_release.py

# `D80`/`D81`'s permanent execution gate: real `lambda:Invoke` calls against a 9-event matrix, asserting
# `FunctionError` absence and a path-specific marker per event -- not a bare `StatusCode: 200`, which is
# returned identically for a normal return and an unhandled exception (`D80`'s own diagnostic call missed
# this the first time, one layer up at the Lex boundary).
#
# Deliberately NOT a dependency of `deploy` in this pass, unlike the layer plan's original proposal --
# see scripts/verify_lambda_execution.py's own module docstring for why: 6 of its 9 events make real,
# small (~$0.002 total) Bedrock calls, and whether the Phase 3-7 Bedrock standing approval's wording
# extends to Phase 8 is Marco's call, not assumed here. Run it explicitly, after a deploy, until that is
# settled. NOT a pure liveness check for the same reason -- a failure on one of those 6 events is
# ambiguous between an infra regression and an ordinary model-classification miss; the script's own
# output says which is which per event.
verify-lambda-execution:
	@$(VENV)/python scripts/verify_lambda_execution.py

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
	@$(MAKE) --no-print-directory verify-flows
	@$(MAKE) --no-print-directory verify-charset

# ruff --fix + black
format:
	$(VENV)/ruff check --fix $(CHECKED)
	$(VENV)/black $(CHECKED)

# mypy --strict
typecheck:
	PYTHONPATH=. $(VENV)/mypy $(TYPED)
