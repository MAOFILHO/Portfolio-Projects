.PHONY: ingest test lint format typecheck eval

# Only targets that are genuinely functional today are listed here. The Definition of Done's canonical
# targets (bootstrap, deploy, destroy, eval, redteam, simulate, verify-billable — see CLAUDE.md) are added
# in the phases that build what they need: nothing may be stubbed out and labeled "would work" before it
# actually does (CLAUDE.md's own rule, applied to this file too).

VENV := .venv/bin

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
