.PHONY: setup run run-all provision pause resume teardown verify test smoke benchmark clean

setup:
	python3.12 scripts/setup.py

run:
	python3.12 scripts/run_local.py

run-all:
	python3.12 scripts/run_local.py --all

provision:
	python3.12 infra/provision.py --budget-email "$(BUDGET_EMAIL)" $(ARGS)

pause:
	python3.12 infra/pause.py

resume:
	python3.12 infra/resume.py

teardown:
	python3.12 infra/teardown.py

verify:
	python3.12 infra/verify_teardown.py

test:
	.venv/bin/python -m pytest tests/unit -v
	monolith/.venv/bin/python -m pytest monolith/tests -v
	microservices/user-service/.venv/bin/python -m pytest microservices/user-service/tests -v
	microservices/product-service/.venv/bin/python -m pytest microservices/product-service/tests -v
	microservices/order-service/.venv/bin/python -m pytest microservices/order-service/tests -v
	bff/.venv/bin/python -m pytest bff/tests -v

smoke:
	.venv/bin/python -m pytest tests/smoke -v

benchmark:
	bff/.venv/bin/python scripts/benchmark.py

clean:
	find . -name "instance" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	rm -rf results
