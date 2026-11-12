PYTHON ?= python3

.PHONY: help setup install check test collect scan

help:
	@printf 'setup    Install dependencies for offline checks\n'
	@printf 'install  Install the miner Python dependencies\n'
	@printf 'check    Run offline checks and tests\n'
	@printf 'test     Run the unit tests\n'
	@printf 'collect  Collect issue-linked pull requests\n'
	@printf 'scan     Scan the configured cases\n'

setup:
	$(PYTHON) -m pip install pytest pytest-timeout requests PyYAML python-dotenv packaging langdetect

install:
	$(PYTHON) -m pip install -r requirements.txt

check:
	$(PYTHON) -m compileall -q miner replay checks tests
	$(PYTHON) -m checks.matched_results --check
	$(PYTHON) -m checks.cohort_lineage audit-recorded
	$(PYTHON) -m checks.pathway_tables replay-indexed
	$(PYTHON) -m checks.bootstrap_checks
	$(PYTHON) -m unittest discover -s tests -p 'test_matched_results.py' -v
	$(MAKE) test

test:
	$(PYTHON) -m pytest -q --timeout=60 tests

collect:
	$(PYTHON) -m miner init-db
	$(PYTHON) -m miner collect

scan:
	$(PYTHON) -m miner init-db
	$(PYTHON) -m miner scan
