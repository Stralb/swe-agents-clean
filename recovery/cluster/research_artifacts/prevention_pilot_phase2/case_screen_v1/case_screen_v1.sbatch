#!/usr/bin/env bash
#SBATCH --job-name=p2_case_screen
#SBATCH --partition=bigbatch
#SBATCH --array=0-0
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
#SBATCH --output=case_screen_v1_%j.out
#SBATCH --error=case_screen_v1_%j.err
set -euo pipefail
ROOT="$HOME/research_artifacts"
PILOT="$ROOT/prevention_pilot_phase2"
source "$HOME/new/malicious-issue-miner-rate-smart/.venv/bin/activate"
# This selection stage uses offline frozen CSVs only, and needs no API credentials.
# Deliberately do not source .env.cluster to avoid spreading secrets to subprocesses.
python "$PILOT/case_screen_v1/build_case_screen_v1.py" \
   --artifacts "$ROOT" \
   --output "$PILOT/case_screen_results_v1" \
   --queue-size 24 --wave-size 8

# Package all outputs on the compute node for transfer and review.
tar -czf "$PILOT/case_screen_results_v1.tar.gz" -C "$PILOT" case_screen_results_v1
sha256sum "$PILOT/case_screen_results_v1.tar.gz" > "$PILOT/case_screen_results_v1.tar.gz.sha256"
python - "$PILOT/case_screen_results_v1/RESEARCHER_SCREEN_QUEUE.csv" <<'PYQUEUE'
import csv,sys
with open(sys.argv[1], newline='', encoding='utf-8') as f:
    rows=list(csv.DictReader(f))
print("=== PRE-AUDIT CASE QUEUE (NOT SCREEN-POSITIVE) ===",flush=True)
for r in rows:
    print(f"{r['queue_rank']:>2}. {r['root_id']:<19} {r['repository']:<42} {r['target_rule']:<35} {r['issue_title'][:75]}",flush=True)
print(f"QUEUED {len(rows)}",flush=True)
PYQUEUE
