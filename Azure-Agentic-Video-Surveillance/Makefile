.PHONY: install deploy teardown status test smoke-pre smoke-post lint bicep-validate frontend-dev backend-dev

install:
	python3.12 -m venv .venv
	. .venv/bin/activate && pip install -e ".[dev]" && pip install -e ./shared

deploy:
	surveil-deploy deploy

teardown:
	surveil-deploy teardown

status:
	surveil-deploy status

test:
	pytest -v

smoke-pre:
	surveil-deploy smoke-test --stage pre

smoke-post:
	surveil-deploy smoke-test --stage post

lint:
	ruff check src tests shared backend/app function

bicep-validate:
	az bicep build --file infra/main.bicep --stdout > /dev/null

frontend-dev:
	cd frontend && npm install && npm run dev

backend-dev:
	. .venv/bin/activate && uvicorn app.main:app --reload --app-dir backend --port 8000
