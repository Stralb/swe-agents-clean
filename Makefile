PYTHON ?= python3

.PHONY: help setup install check test collect scan

help:
	@printf 'setup    Install dependencies for offline checks\n'
	@printf 'install  Install the miner Python dependencies\n'
	@printf 'check    Run offline checks and selected tests\n'
	@printf 'test     Run selected miner unit tests\n'
	@printf 'collect  Collect issue-linked pull requests\n'
	@printf 'scan     Scan the configured cases\n'

setup:
	$(PYTHON) -m pip install pytest pytest-timeout requests PyYAML python-dotenv packaging langdetect

install:
	$(PYTHON) -m pip install -r requirements.txt

check:
	$(PYTHON) -m compileall -q src scripts analysis dataset tests
	$(PYTHON) -m analysis.matched_results --check
	$(PYTHON) -m analysis.cohort_lineage audit-recorded
	$(PYTHON) -m analysis.pathway_tables replay-indexed
	$(PYTHON) -m analysis.bootstrap_checks
	$(PYTHON) -m unittest discover -s tests -p 'test_matched_results.py' -v
	$(MAKE) test

test:
	$(PYTHON) -m pytest -vv --timeout=20 \
		tests/test_ai_markers.py tests/test_dependency_diff.py \
		tests/test_issue_linker.py tests/test_upstream_features.py \
		tests/test_filters.py tests/test_tool_applicability.py \
		tests/test_agentic_discovery.py tests/test_artifact_regions_methodology.py \
		tests/test_behaviour_filter.py tests/test_no_patch_patterns.py \
		tests/test_osv_alias_dedupe.py tests/test_semgrep_scanner.py \
		tests/test_codeql_diff_linking.py tests/test_codeql_default_all.py \
		tests/test_repo_window_collection.py tests/test_worker_pipeline.py

collect:
	$(PYTHON) -m scripts.ensure_db
	$(PYTHON) -m scripts.collect

scan:
	$(PYTHON) -m scripts.ensure_db
	$(PYTHON) -m scripts.scan
