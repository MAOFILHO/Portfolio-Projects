.PHONY: setup tf-init plan provision run api teardown test test-unit test-pre test-post test-post-run test-post-teardown lint typecheck frontend

VENV := .venv/bin

# Backend resource names are created deterministically by scripts/bootstrap_state.sh from
# PROJECT_SUFFIX, so derive them here rather than requiring two more hand-set env vars that
# were never in .env.example. Override by exporting TF_STATE_BUCKET / TF_LOCK_TABLE.
TF_STATE_BUCKET ?= bedrock-platform-$(PROJECT_SUFFIX)-tfstate
TF_LOCK_TABLE   ?= bedrock-platform-$(PROJECT_SUFFIX)-tflock
# The live state key. NOT namespaced by PROJECT_SUFFIX — the suffix already namespaces the
# bucket itself. Pointing at a key that does not exist makes terraform init succeed against
# an EMPTY state, and the next plan proposes creating a duplicate of every live resource.
TF_STATE_KEY    ?= bedrock-platform/terraform.tfstate

# Terraform must be told the region explicitly. var.aws_region defaults to us-east-1, so
# omitting it silently targets the wrong region regardless of AWS_REGION in .env.
TF_VARS = -var="project_suffix=$(PROJECT_SUFFIX)" \
          -var="aws_region=$(AWS_REGION)" \
          -var="budget_alert_email=$(BUDGET_ALERT_EMAIL)" \
          -var="budget_limit_usd=$(BUDGET_LIMIT_USD)"

setup:
	$(VENV)/pip install --upgrade pip
	$(VENV)/pip install -r requirements.txt -r requirements-dev.txt
	# Install the project itself. Without this `import bedrock_platform` fails, so a
	# fresh clone passes lint and mypy (both path-based) but every test errors on import.
	$(VENV)/pip install -e .

tf-init:
	@test -n "$(PROJECT_SUFFIX)" || (echo "ERROR: PROJECT_SUFFIX is not set — source .env first." && exit 1)
	@test -n "$(AWS_REGION)" || (echo "ERROR: AWS_REGION is not set — source .env first." && exit 1)
	cd infra/terraform && terraform init -reconfigure \
		-backend-config="bucket=$(TF_STATE_BUCKET)" \
		-backend-config="dynamodb_table=$(TF_LOCK_TABLE)" \
		-backend-config="key=$(TF_STATE_KEY)"

plan: tf-init
	cd infra/terraform && terraform plan $(TF_VARS)

provision: tf-init
	$(VENV)/python scripts/print_cost_estimate.py
	cd infra/terraform && terraform apply $(TF_VARS)
	@echo "Resources are live and billing. Run 'make teardown' when done."

run:
	$(VENV)/python scripts/run_pipeline.py --scenario $(SCENARIO)
	@echo "Resources are live and billing. Run 'make teardown' when done."

teardown: tf-init
	$(VENV)/python scripts/teardown.py
	cd infra/terraform && terraform destroy -auto-approve $(TF_VARS)

test: test-unit test-pre test-post test-post-run

test-unit:
	$(VENV)/pytest tests/unit -v -s

test-pre:
	$(VENV)/pytest tests/pre_provision -v

test-post:
	$(VENV)/pytest tests/post_provision -v

test-post-run:
	$(VENV)/pytest tests/post_run -v

test-post-teardown:
	$(VENV)/pytest tests/post_teardown -v

lint:
	$(VENV)/ruff check src tests scripts
	$(VENV)/ruff format --check src tests scripts

typecheck:
	$(VENV)/mypy

api:
	$(VENV)/uvicorn bedrock_platform.api.app:app --host 0.0.0.0 --port $${API_PORT:-8000} --reload

frontend:
	cd frontend && npm run dev
