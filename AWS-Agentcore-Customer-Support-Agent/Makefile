.PHONY: install prereq run test smoke clean verify

install:
	pip install -r requirements.txt
	pip install -r agentcore/frontend/requirements.txt

prereq:
	python main.py --prereq

run:
	python main.py --step all

test:
	pytest tests/test_step1_tools.py -v

smoke:
	pytest tests/smoke_test.py -v

clean:
	python main.py --cleanup

verify:
	bash scripts/verify_cleanup.sh
