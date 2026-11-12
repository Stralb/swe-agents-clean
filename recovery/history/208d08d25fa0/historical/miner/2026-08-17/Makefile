PYTHON ?= python3
PYTHONPATH ?= .
CONFIG ?= config.yml
DB_PATH ?= data/miner.db
GH_TOKEN ?=
# Main controls
# MODE=full  -> default smart scan: cheap scanners first, then gradual CodeQL
# MODE=fast  -> Gitleaks + dependency diff/OSV, no CodeQL
# SCOPE=all  -> main methodology: collect/scan all eligible candidates, enrich with agentic markers
# SCOPE=ai   -> narrow marker-positive candidate mode only
MODE ?= full
SCOPE ?= all
ACTION ?= stats
AI_PROFILE ?= balanced
AI_DISCOVERY ?= hybrid
FETCH_COMMIT_MESSAGES_FOR_AI ?= true
SEARCH_PER_PAGE ?= 25
MAX_SEARCH_TERMS ?= 6
SEARCH_PAUSE_SECONDS ?= 25
SECONDARY_WAIT_SECONDS ?= 30
MAX_SECONDARY_RETRIES ?= 0
GITHUB_MIN_REMAINING ?= 100
GITHUB_SEARCH_MIN_REMAINING ?= 0
WORKER_IDLE_SECONDS ?= 10
WORKER_MAX_LOOPS ?= 0
GITHUB_WORKERS ?= 1
SOURCE_WORKERS ?= 1
DEP_WORKERS ?= 1
SECRET_WORKERS ?= 1
CODEQL_WORKERS ?= 1
CODEQL_TMPDIR ?= /tmp/miner-codeql-tmp
RETRIEVAL_MODE ?= repo_window_pr_search
LOOKBACK_START ?= 2025-01-01
REPO_SHARD_COUNT ?=1
REPO_SHARD_INDEX ?=0
MONTH_SHARD_COUNT ?=1
MONTH_SHARD_INDEX ?=0
REPO_MONTH_PER_PAGE ?=50
REPO_MONTH_MAX_PAGES ?=2
REPO_WINDOW_PER_PAGE ?=50
REPO_WINDOW_MAX_PAGES ?=2
REPO_WINDOW_SPLIT_THRESHOLD ?=100
ACTIVE_REPO_SEED ?=true
ACTIVE_REPO_SEED_MAX_PAGES ?=2
ACTIVE_REPO_SEED_PER_PAGE ?=100
ISSUE_MIN_BODY_CHARS ?=200
EXCLUDE_DOCS_SCOPE_ONLY ?=true
REQUIRE_HIGH_YIELD_SURFACE ?=true
MAX_CHANGED_FILES_FOR_EVIDENCE ?=75
MAX_LINKED_ISSUES_PER_PR_FOR_EVIDENCE ?=1
GITHUB_SEARCH_MIN_INTERVAL_SECONDS ?=2.35
GITHUB_CORE_MIN_INTERVAL_SECONDS ?=0
GITHUB_REQUEST_JITTER_SECONDS ?=0.65

MAX_REPOS ?=
MAX_PRS ?=50
MAX_CASES ?=100
MAX_CASES_PER_REPO ?=3
MAX_SECONDS ?=1800
RANDOM_SEED ?=42
REPO_SAMPLE_STRATEGY ?=active_first
CASE_SAMPLE_STRATEGY ?=random
REPO_SAMPLE_POOL_MULTIPLIER ?=4
CASE_SAMPLE_POOL_MULTIPLIER ?=4
CODEQL_MAX_PER_RUN ?=3
CODEQL_TIMEOUT_SECONDS ?=600
CODEQL_TRIGGER ?=all_codeql
CODEQL_LANGUAGE ?=auto
CODEQL_QUERY_SUITE ?=
CODEQL_BUILD_MODE ?=none
GITHUB_LANGUAGES ?=Python,JavaScript,TypeScript
REQUIRE_PRIMARY_WORKER ?=true
REPO_WINDOW_EXHAUSTIVE_SPLIT ?=false
SEMGREP_CONFIG ?=p/security-audit
SEMGREP_TIMEOUT_SECONDS ?=300
OVERNIGHT_MAX_REPOS ?=200
OVERNIGHT_MAX_PRS ?=200
OVERNIGHT_MAX_CASES ?=2000
OVERNIGHT_MAX_SECONDS ?=25200
FORCE_REFRESH ?=false
FORCE_RESCAN ?=false
GITHUB_CACHE ?=true

SCAN_CODEQL := $(if $(filter full,$(MODE)),true,false)
SCAN_GITLEAKS ?=true
SCAN_OSV ?=true
SCAN_SEMGREP ?=false
SCAN_DEPENDENCY_DOWNGRADE ?=true
AI_FLAG := $(if $(filter ai,$(SCOPE)),true,false)

TOKEN_ENV = $(if $(GH_TOKEN),GITHUB_TOKEN=$(GH_TOKEN),$(if $(GITHUB_TOKEN),GITHUB_TOKEN=$(GITHUB_TOKEN),))
ENV_VARS = PYTHONPATH=$(PYTHONPATH) CONFIG=$(CONFIG) DB_PATH=$(DB_PATH) MAX_REPOS=$(MAX_REPOS) MAX_PRS=$(MAX_PRS) MAX_CASES=$(MAX_CASES) MAX_SECONDS=$(MAX_SECONDS) MAX_CASES_PER_REPO=$(MAX_CASES_PER_REPO) RANDOM_SEED=$(RANDOM_SEED) REPO_SAMPLE_STRATEGY=$(REPO_SAMPLE_STRATEGY) CASE_SAMPLE_STRATEGY=$(CASE_SAMPLE_STRATEGY) REPO_SAMPLE_POOL_MULTIPLIER=$(REPO_SAMPLE_POOL_MULTIPLIER) CASE_SAMPLE_POOL_MULTIPLIER=$(CASE_SAMPLE_POOL_MULTIPLIER) CODEQL_MAX_PER_RUN=$(CODEQL_MAX_PER_RUN) CODEQL_TIMEOUT_SECONDS=$(CODEQL_TIMEOUT_SECONDS) CODEQL_TRIGGER=$(CODEQL_TRIGGER) CODEQL_LANGUAGE=$(CODEQL_LANGUAGE) CODEQL_QUERY_SUITE=$(CODEQL_QUERY_SUITE) CODEQL_BUILD_MODE=$(CODEQL_BUILD_MODE) CODEQL_TMPDIR=$(CODEQL_TMPDIR) MINER_CODEQL_TMPDIR=$(CODEQL_TMPDIR) SEMGREP_CONFIG=$(SEMGREP_CONFIG) SEMGREP_TIMEOUT_SECONDS=$(SEMGREP_TIMEOUT_SECONDS) SCAN_CODEQL=$(SCAN_CODEQL) SCAN_GITLEAKS=$(SCAN_GITLEAKS) SCAN_OSV=$(SCAN_OSV) SCAN_DEPENDENCY_DOWNGRADE=$(SCAN_DEPENDENCY_DOWNGRADE) SCAN_SEMGREP=$(SCAN_SEMGREP) FORCE_REFRESH=$(FORCE_REFRESH) FORCE_RESCAN=$(FORCE_RESCAN) GITHUB_CACHE=$(GITHUB_CACHE) AI_ONLY=$(AI_FLAG) SCAN_AI_ONLY=$(AI_FLAG) AI_PROFILE=$(AI_PROFILE) AI_DISCOVERY=$(AI_DISCOVERY) FETCH_COMMIT_MESSAGES_FOR_AI=$(FETCH_COMMIT_MESSAGES_FOR_AI) SEARCH_PER_PAGE=$(SEARCH_PER_PAGE) MAX_SEARCH_TERMS=$(MAX_SEARCH_TERMS) SEARCH_PAUSE_SECONDS=$(SEARCH_PAUSE_SECONDS) SECONDARY_WAIT_SECONDS=$(SECONDARY_WAIT_SECONDS) MAX_SECONDARY_RETRIES=$(MAX_SECONDARY_RETRIES) GITHUB_MIN_REMAINING=$(GITHUB_MIN_REMAINING) GITHUB_SEARCH_MIN_REMAINING=$(GITHUB_SEARCH_MIN_REMAINING) WORKER_IDLE_SECONDS=$(WORKER_IDLE_SECONDS) WORKER_MAX_LOOPS=$(WORKER_MAX_LOOPS) RETRIEVAL_MODE=$(RETRIEVAL_MODE) LOOKBACK_START=$(LOOKBACK_START) GITHUB_LANGUAGES=$(GITHUB_LANGUAGES) REQUIRE_PRIMARY_WORKER=$(REQUIRE_PRIMARY_WORKER) REQUIRE_HIGH_YIELD_SURFACE=$(REQUIRE_HIGH_YIELD_SURFACE) MAX_CHANGED_FILES_FOR_EVIDENCE=$(MAX_CHANGED_FILES_FOR_EVIDENCE) MAX_LINKED_ISSUES_PER_PR_FOR_EVIDENCE=$(MAX_LINKED_ISSUES_PER_PR_FOR_EVIDENCE) REPO_WINDOW_EXHAUSTIVE_SPLIT=$(REPO_WINDOW_EXHAUSTIVE_SPLIT) GITHUB_SEARCH_MIN_INTERVAL_SECONDS=$(GITHUB_SEARCH_MIN_INTERVAL_SECONDS) GITHUB_CORE_MIN_INTERVAL_SECONDS=$(GITHUB_CORE_MIN_INTERVAL_SECONDS) GITHUB_REQUEST_JITTER_SECONDS=$(GITHUB_REQUEST_JITTER_SECONDS) REPO_SHARD_COUNT=$(REPO_SHARD_COUNT) REPO_SHARD_INDEX=$(REPO_SHARD_INDEX) MONTH_SHARD_COUNT=$(MONTH_SHARD_COUNT) MONTH_SHARD_INDEX=$(MONTH_SHARD_INDEX) REPO_MONTH_PER_PAGE=$(REPO_MONTH_PER_PAGE) REPO_MONTH_MAX_PAGES=$(REPO_MONTH_MAX_PAGES) REPO_WINDOW_PER_PAGE=$(REPO_WINDOW_PER_PAGE) REPO_WINDOW_MAX_PAGES=$(REPO_WINDOW_MAX_PAGES) REPO_WINDOW_SPLIT_THRESHOLD=$(REPO_WINDOW_SPLIT_THRESHOLD) ACTIVE_REPO_SEED=$(ACTIVE_REPO_SEED) ACTIVE_REPO_SEED_MAX_PAGES=$(ACTIVE_REPO_SEED_MAX_PAGES) ACTIVE_REPO_SEED_PER_PAGE=$(ACTIVE_REPO_SEED_PER_PAGE) ISSUE_MIN_BODY_CHARS=$(ISSUE_MIN_BODY_CHARS) EXCLUDE_DOCS_SCOPE_ONLY=$(EXCLUDE_DOCS_SCOPE_ONLY)

.PHONY: help install install-cluster-tools tools init-db ensure-db verify-github collect scan run live mine evaluate evaluate-cheap evaluate-codeql ui export status cache clean reset-db self-test test-dependency-downgrade overnight

help:
	@echo "Malicious Issue Miner"
	@echo ""
	@echo "Primary commands:"
	@echo "  make install"
	@echo "  make install-cluster-tools  # identify, GitHub Linguist, Trivy in user-space"
	@echo "  make init-db  # optional; collect/scan/ui auto-initialize if needed"
	@echo "  make collect GH_TOKEN=... SCOPE=all|ai MAX_CASES=100"
	@echo "  make scan    GH_TOKEN=... MODE=full|fast SCOPE=all|ai MAX_CASES=100"
	@echo "  make run     GH_TOKEN=... MODE=full|fast SCOPE=all|ai MAX_CASES=100"
	@echo "  make live    GH_TOKEN=... Continuous mine + evaluate until stopped"
	@echo "  make mine    GH_TOKEN=... GitHub mining only"
	@echo "  make evaluate  Local evaluation only, no GitHub mining"
	@echo "  make ui"
	@echo "  make export"
	@echo "  make self-test"
	@echo ""
	@echo "Controls:"
	@echo "  MODE=full     Default smart scan: cheap scanners across DB first, then gradual CodeQL"
	@echo "  MODE=fast     Fast scan only: Gitleaks + dependency downgrade + OSV"
	@echo "  SCOPE=all     All eligible candidates"
	@echo "  SCOPE=ai      Narrow marker-positive candidates only; use SCOPE=all for main methodology"
	@echo "  MAX_REPOS=    Repo limit"
	@echo "  MAX_PRS=50    PRs per repo"
	@echo "  MAX_CASES=100 Case limit"
	@echo "  MAX_CASES_PER_REPO=3 Prevents one repo dominating the sample"
	@echo "  MAX_SECONDS=1800 Time limit"
	@echo "  REPO_SAMPLE_STRATEGY=active_first Prefer repos already known to have structural issue-linked PR activity, then randomize the rest"
	@echo "  CASE_SAMPLE_STRATEGY=random Randomize PR/case candidates within each repo"
	@echo "  RANDOM_SEED=42 Reproducible sampling seed"
	@echo "  CODEQL_MAX_PER_RUN=3 Expensive CodeQL cases per scan run after cheap pass"
	@echo "  CODEQL_TIMEOUT_SECONDS=600 Timeout per CodeQL create/analyze step"
	@echo "  CODEQL_TMPDIR=/tmp/miner-codeql-tmp Linux-local temp path for CodeQL DBs"
	@echo "  CODEQL_TRIGGER=all_codeql Run CodeQL on changed CodeQL-supported languages by default"
	@echo "  CODEQL_LANGUAGE=auto Auto-detect CodeQL language from changed files"
	@echo "  GITHUB_LANGUAGES=Python,JavaScript,TypeScript Structural repo discovery languages"
	@echo "  REQUIRE_PRIMARY_WORKER=true Require CodeQL/dependency/CI applicability; secret scan alone does not qualify"
	@echo "  REPO_WINDOW_EXHAUSTIVE_SPLIT=false Do not split saturated repos by month in discovery mode"
	@echo "  SCAN_DEPENDENCY_DOWNGRADE=true Enable dependency downgrade worker"
	@echo "  REPO_SHARD_COUNT/INDEX Split repo universe across cluster nodes"
	@echo "  MONTH_SHARD_COUNT/INDEX Split target months across cluster nodes"
	@echo "  make overnight  Long run preset: 7h cap, downstream-first workers"
	@echo "  FORCE_REFRESH=true Re-query GitHub instead of using API cache"
	@echo "  FORCE_RESCAN=true Re-run scanners instead of using scanner cache"
	@echo "  AI_PROFILE=high|balanced|broad AI marker breadth; default balanced"
	@echo "  AI_DISCOVERY=search|walk|hybrid Agentic-marker discovery mode; default hybrid"
	@echo "  SEARCH_PAUSE_SECONDS=25 GitHub search pacing to avoid secondary limits"
	@echo "  GITHUB_MIN_REMAINING=100 Core API reserve; does not apply to search bucket"
	@echo "  GITHUB_SEARCH_MIN_REMAINING=0 Search API reserve; 0 means use requests until GitHub says reset"
	@echo "  RETRIEVAL_MODE=repo_window_pr_search Use downstream-first repo/window structural PR search; saturated repos are skipped, not split, by default"
	@echo "  ACTIVE_REPO_SEED=true Use one structural global PR search to seed repos that actually have issue-linked PRs"
	@echo "  ISSUE_MIN_BODY_CHARS=200 Exclude one-line/underdescribed issues from the study frame"
	@echo "  REQUIRE_HIGH_YIELD_SURFACE=true Require dependency/CI/security-sensitive source surface for evidence-mode cases"
	@echo "  MAX_CHANGED_FILES_FOR_EVIDENCE=75 Exclude broad batch PRs that weaken causal issue→PR evidence"
	@echo "  MAX_LINKED_ISSUES_PER_PR_FOR_EVIDENCE=1 Exclude ambiguous PRs closing many issues"
	@echo "  EXCLUDE_DOCS_SCOPE_ONLY=true Exclude PRs where all changed files are docs-scoped"
	@echo ""
	@echo "Cache:"
	@echo "  make cache ACTION=stats"
	@echo "  make cache ACTION=clear"

install:
	@$(PYTHON) -m pip install -r requirements.txt

install-cluster-tools:
	@bash scripts/install_cluster_tools.sh

tools:
	@$(TOKEN_ENV) $(ENV_VARS) $(PYTHON) scripts/check_tools.py

init-db:
	@$(TOKEN_ENV) $(ENV_VARS) $(PYTHON) scripts/init_db.py

ensure-db:
	@$(TOKEN_ENV) $(ENV_VARS) $(PYTHON) scripts/ensure_db.py

verify-github:
	@$(TOKEN_ENV) $(PYTHON) scripts/check_github_auth.py

collect: ensure-db verify-github
	@echo "Collecting candidates | scope=$(SCOPE) | token hidden | cache=$(GITHUB_CACHE) | force_refresh=$(FORCE_REFRESH)"
	@$(TOKEN_ENV) $(ENV_VARS) $(PYTHON) scripts/collect.py

scan: ensure-db
	@echo "Scanning candidates | mode=$(MODE) | scope=$(SCOPE) | cheap-first=true | CodeQL=$(SCAN_CODEQL) | codeql_max=$(CODEQL_MAX_PER_RUN) | Gitleaks=$(SCAN_GITLEAKS) | OSV=$(SCAN_OSV) | force_rescan=$(FORCE_RESCAN)"
	@$(TOKEN_ENV) $(ENV_VARS) $(PYTHON) scripts/scan.py

run: collect scan


live: ensure-db verify-github
	@echo "Starting continuous live pipeline | retrieval=$(RETRIEVAL_MODE) | GitHub=$(GITHUB_WORKERS) codeql-src=$(SOURCE_WORKERS) dep=$(DEP_WORKERS) secret=$(SECRET_WORKERS) codeql=$(CODEQL_WORKERS) | core reserve=$(GITHUB_MIN_REMAINING) search reserve=$(GITHUB_SEARCH_MIN_REMAINING) | continuous polling; WORKER_MAX_LOOPS ignored in live"
	@$(TOKEN_ENV) $(ENV_VARS) $(PYTHON) scripts/workers.py --mode live --github-workers $(GITHUB_WORKERS) --source-workers $(SOURCE_WORKERS) --dependency-workers $(DEP_WORKERS) --secret-workers $(SECRET_WORKERS) --codeql-workers $(CODEQL_WORKERS) --max-loops $(WORKER_MAX_LOOPS) --idle-seconds $(WORKER_IDLE_SECONDS)

mine: ensure-db verify-github
	@echo "Starting GitHub mining only | retrieval=$(RETRIEVAL_MODE) | core reserve=$(GITHUB_MIN_REMAINING) search reserve=$(GITHUB_SEARCH_MIN_REMAINING) | continuous polling; WORKER_MAX_LOOPS ignored in live"
	@$(TOKEN_ENV) $(ENV_VARS) $(PYTHON) scripts/workers.py --mode mine --github-workers $(GITHUB_WORKERS) --max-loops $(WORKER_MAX_LOOPS) --idle-seconds $(WORKER_IDLE_SECONDS)

evaluate: ensure-db
	@echo "Starting evaluation only | codeql-src=$(SOURCE_WORKERS) dep=$(DEP_WORKERS) secret=$(SECRET_WORKERS) codeql=$(CODEQL_WORKERS) | no GitHub mining"
	@$(TOKEN_ENV) $(ENV_VARS) $(PYTHON) scripts/workers.py --mode evaluate --github-workers 0 --source-workers $(SOURCE_WORKERS) --dependency-workers $(DEP_WORKERS) --secret-workers $(SECRET_WORKERS) --codeql-workers $(CODEQL_WORKERS) --max-loops $(WORKER_MAX_LOOPS) --idle-seconds $(WORKER_IDLE_SECONDS) --exit-when-drained

evaluate-cheap: ensure-db
	@echo "Starting cheap evaluation only | secrets + dependency downgrade + OSV | no CodeQL"
	@$(TOKEN_ENV) $(ENV_VARS) $(PYTHON) scripts/workers.py --mode evaluate-cheap --github-workers 0 --source-workers $(SOURCE_WORKERS) --dependency-workers $(DEP_WORKERS) --secret-workers $(SECRET_WORKERS) --codeql-workers 0 --max-loops $(WORKER_MAX_LOOPS) --idle-seconds $(WORKER_IDLE_SECONDS) --exit-when-drained

evaluate-codeql: ensure-db
	@echo "Starting CodeQL evaluation only"
	@$(TOKEN_ENV) $(ENV_VARS) $(PYTHON) scripts/workers.py --mode evaluate-codeql --github-workers 0 --source-workers 0 --dependency-workers 0 --secret-workers 0 --codeql-workers 1 --max-loops $(WORKER_MAX_LOOPS) --idle-seconds $(WORKER_IDLE_SECONDS) --exit-when-drained

methodology-profile: ensure-db
	@$(TOKEN_ENV) $(ENV_VARS) $(PYTHON) scripts/profile_artifacts.py

methodology-status: ensure-db
	@$(TOKEN_ENV) $(ENV_VARS) $(PYTHON) scripts/sync_case_statuses.py

region-yield: ensure-db methodology-profile methodology-status
	@$(TOKEN_ENV) $(ENV_VARS) $(PYTHON) scripts/region_yield.py

collect-pr-first: ensure-db
	@echo "PR-first collection: merged linked PRs -> artifacts -> scanner routes; issue text is analysis material, not gate"
	@$(TOKEN_ENV) $(ENV_VARS) RETRIEVAL_MODE=downstream_first REQUIRE_HIGH_YIELD_SURFACE=false ISSUE_MIN_BODY_CHARS=0 EXCLUDE_DOCS_SCOPE_ONLY=true $(PYTHON) scripts/collect.py
	@$(TOKEN_ENV) $(ENV_VARS) $(PYTHON) scripts/profile_artifacts.py

slurm-pr-first:
	@$(PYTHON) scripts/cluster_run.py collect-pr-first --submit

slurm-evaluate-cheap:
	@$(PYTHON) scripts/cluster_run.py evaluate-cheap --submit

slurm-evaluate-codeql:
	@$(PYTHON) scripts/cluster_run.py evaluate-codeql --submit

slurm-status:
	@$(PYTHON) scripts/cluster_run.py status --submit

ui: ensure-db
	@$(TOKEN_ENV) $(ENV_VARS) streamlit run ui/app.py

export: ensure-db
	@$(TOKEN_ENV) $(ENV_VARS) $(PYTHON) scripts/export.py

status: ensure-db
	@$(TOKEN_ENV) $(ENV_VARS) $(PYTHON) scripts/status.py

cache:
	@if [ "$(ACTION)" = "clear" ]; then \
		rm -rf data/cache/github_api/*; \
		echo "Cleared GitHub API cache."; \
	else \
		echo "GitHub API cached responses:"; \
		find data/cache/github_api -type f -name "*.json" 2>/dev/null | wc -l; \
	fi

self-test: test-dependency-downgrade
	@$(PYTHON) -m pytest -q

test-dependency-downgrade:
	@$(TOKEN_ENV) $(ENV_VARS) $(PYTHON) scripts/test_dependency_downgrade.py

clean:
	@rm -rf data/tmp/* data/raw/* .streamlit-cache __pycache__ .pytest_cache
	@find . -type d -name __pycache__ -prune -exec rm -rf {} +

reset-db:
	@rm -f $(DB_PATH) $(DB_PATH)-wal $(DB_PATH)-shm
	@$(TOKEN_ENV) $(ENV_VARS) $(PYTHON) scripts/init_db.py


overnight: ensure-db verify-github
	@echo "Starting overnight run | cap=$(OVERNIGHT_MAX_SECONDS)s | repos=$(OVERNIGHT_MAX_REPOS) | cases=$(OVERNIGHT_MAX_CASES) | downstream-first | CodeQL trigger=$(CODEQL_TRIGGER)"
	@$(TOKEN_ENV) $(ENV_VARS) MAX_SECONDS=$(OVERNIGHT_MAX_SECONDS) MAX_REPOS=$(OVERNIGHT_MAX_REPOS) MAX_PRS=$(OVERNIGHT_MAX_PRS) MAX_CASES=$(OVERNIGHT_MAX_CASES) LOOKBACK_MONTHS=12 SCOPE=all MODE=full $(PYTHON) scripts/collect.py
	@$(TOKEN_ENV) $(ENV_VARS) MAX_SECONDS=$(OVERNIGHT_MAX_SECONDS) MAX_CASES=$(OVERNIGHT_MAX_CASES) SCOPE=all MODE=full SCAN_CODEQL=true SCAN_GITLEAKS=true SCAN_OSV=true SCAN_SEMGREP=false SCAN_DEPENDENCY_DOWNGRADE=true CODEQL_TRIGGER=$(CODEQL_TRIGGER) CODEQL_LANGUAGE=$(CODEQL_LANGUAGE) CODEQL_MAX_PER_RUN=$(CODEQL_MAX_PER_RUN) CODEQL_TIMEOUT_SECONDS=$(CODEQL_TIMEOUT_SECONDS) $(PYTHON) scripts/scan.py
