.PHONY: install deploy teardown status smoke-pre smoke-post test lint clean

install:
	pip install -e ".[dev,observability]"

deploy:
	cdss-deploy deploy

teardown:
	cdss-deploy teardown

status:
	cdss-deploy status

smoke-pre:
	cdss-deploy smoke-test --stage pre

smoke-post:
	cdss-deploy smoke-test --stage post

test:
	pytest tests/ -m "not integration" -v

test-all:
	pytest tests/ -v

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	ruff format src/ tests/

clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
