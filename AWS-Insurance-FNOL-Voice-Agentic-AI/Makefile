.PHONY: ingest test lint format typecheck

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

# Run the unit test suite. No AWS credentials required — moto covers every AWS call in tests.
test:
	$(VENV)/python -m pytest tests/unit -v

# ruff + black --check
lint:
	$(VENV)/ruff check src tests
	$(VENV)/black --check src tests

# ruff --fix + black
format:
	$(VENV)/ruff check --fix src tests
	$(VENV)/black src tests

# mypy --strict
typecheck:
	$(VENV)/mypy src
