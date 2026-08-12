.DEFAULT_GOAL := help
SHELL := /bin/bash
PY    := .venv/bin/python
PIP   := .venv/bin/pip
PYTEST:= .venv/bin/pytest
TF    := terraform -chdir=infra/terraform
export PYTHONPATH := src

# Load .env (if present) into make's own variable space so targets like
# `provision` can reference $(BUDGET_ALERT_EMAIL) etc. Does not export into
# child processes beyond what's referenced explicitly — the Python app still
# loads .env itself via pydantic-settings.
ifneq (,$(wildcard .env))
  include .env
  export
endif

.PHONY: help setup run provision hosting-role github-oidc teardown test test-unit smoke-pre smoke-post-provision \
        smoke-post-run smoke-post-teardown api frontend mcp-list fmt clean

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
setup: ## Create venv, install Python + frontend deps
	@test -d .venv || python3 -m venv .venv
	@$(PIP) install -q --upgrade pip
	@$(PIP) install -q -r requirements.txt
	@test -f .env || cp .env.example .env
	@cd frontend && npm install --silent
	@echo "✅ setup complete — edit .env, then 'make run'"

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
run: ## Run all three workflows end-to-end (honours DEMO_MODE, default mock)
	@$(PY) -m app.cli run-all

api: ## Start the FastAPI backend
	@$(PY) -m uvicorn app.main:app --reload --host $${API_HOST:-127.0.0.1} --port $${API_PORT:-8000}

frontend: ## Start the React dev server
	@cd frontend && npm run dev

mcp-list: ## List every tool exposed by the three MCP servers
	@$(PY) -m app.cli mcp-list

# ---------------------------------------------------------------------------
# Infrastructure
# ---------------------------------------------------------------------------
provision: smoke-pre ## Provision Azure infra (budget alert created FIRST)
	@$(TF) init -input=false
	@$(TF) apply -auto-approve -var="enable_next_suffix_probe=true" \
	  -var="dockerhub_username=$(DOCKERHUB_USERNAME)" \
	  -var="budget_contact_emails=$(if $(BUDGET_ALERT_EMAIL),[\"$(BUDGET_ALERT_EMAIL)\"],[])"
	@$(PY) -m app.cli sync-env
	@RUN_LIVE_SMOKE=1 $(MAKE) smoke-post-provision
	@echo ""
	@echo "🔴 Resources are live and billing. Run 'make teardown' when done."

hosting-role: ## One-time: create the least-privilege custom role the hosting OIDC identity assumes (must run before the first `make provision` that includes hosting.tf)
	@az role definition create --role-definition @infra/foundry-deployer-role.json
	@echo "✅ 'Foundry Platform Deployer' role created — safe to re-run (az updates in place)."

github-oidc: ## One-time: create the GitHub Actions OIDC identity in its own Terraform state (infra/terraform-identity/) — survives `make teardown`, unlike main.tf/hosting.tf's own resources
	@terraform -chdir=infra/terraform-identity init -input=false
	@terraform -chdir=infra/terraform-identity apply -auto-approve
	@echo "✅ identity ready. If its client_id changed, update the FOUNDRY_AZURE_CLIENT_ID GitHub Actions variable and infra/terraform/variables.tf's github_oidc_client_id default."

teardown: ## Destroy ALL tagged resources, at every suffix
	@$(PY) infra/terraform/scripts/sweep_orphans.py --tag foundry-agentic-platform --dry-run
	@$(TF) destroy -auto-approve -var="dockerhub_username=$(DOCKERHUB_USERNAME)" || true
	@$(PY) infra/terraform/scripts/sweep_orphans.py --tag foundry-agentic-platform
	@RUN_LIVE_SMOKE=1 $(MAKE) smoke-post-teardown
	@echo "✅ teardown complete and verified"

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
test: test-unit ## Alias for unit tests

test-unit: ## Unit tests (no cloud, no network)
	@$(PYTEST) tests/unit -q

smoke-pre: ## Pre-provision checks: python, az auth, region, model availability, quota
	@RUN_LIVE_SMOKE=1 $(PYTEST) tests/smoke_pre -q

smoke-post-provision: ## Assert every resource is live AND on the approved SKU
	@RUN_LIVE_SMOKE=1 $(PYTEST) tests/smoke_post_provision -q

smoke-post-run: ## Assert expected outputs exist and are non-empty
	@$(PYTEST) tests/smoke_post_run -q

smoke-post-teardown: ## Assert ZERO surviving tagged resources (release blocker)
	@RUN_LIVE_SMOKE=1 $(PYTEST) tests/smoke_post_teardown -q

# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------
fmt: ## Format Python
	@$(PY) -m ruff format src mcp_servers tests 2>/dev/null || echo "ruff not installed; skipping"

clean: ## Remove caches and build artefacts
	@find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	@rm -rf .pytest_cache .coverage htmlcov frontend/dist
	@echo "✅ cleaned"
