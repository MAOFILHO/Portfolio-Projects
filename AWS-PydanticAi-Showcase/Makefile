.PHONY: install lint format typecheck test run docker-build docker-run

install:
	uv sync --group dev

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run pyright app tests evals

test:
	uv run pytest

run:
	uv run uvicorn app.main:app --reload

docker-build:
	docker build -t pydantic-ai-showcase .

docker-run:
	docker run --rm -p 8000:8000 --env-file .env pydantic-ai-showcase
