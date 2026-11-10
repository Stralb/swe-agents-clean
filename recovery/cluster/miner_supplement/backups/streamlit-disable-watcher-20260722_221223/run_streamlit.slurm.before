#!/bin/bash
set -euo pipefail
ROOT="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"
cd "$ROOT"
mkdir -p logs
source .venv/bin/activate
if [ -f .env.cluster ]; then
    set -a
    source .env.cluster
    set +a
fi
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1
export CONFIG="${CONFIG:-$ROOT/config.agentic_js.yml}"
export DB_PATH="$(tr -d '[:space:]' < "$ROOT/.current_agentic_js_eval_db")"
export UI_READ_ONLY=1
export UI_COMMAND_SPOOL="$ROOT/data/distributed_spool"
export DISTRIBUTED_SPOOL_ROOT="$ROOT/data/distributed_spool"
PORT="${STREAMLIT_PORT:-8501}"
streamlit run ui/app.py     --server.headless=true     --server.address=0.0.0.0     --server.port="$PORT"     --browser.gatherUsageStats=false
