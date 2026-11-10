#!/bin/bash
#SBATCH --job-name=prev_p2_probe
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --output=phase2_probe_%j.out
#SBATCH --error=phase2_probe_%j.err

set -euo pipefail
export PHASE2_ROOT=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2
cd "$PHASE2_ROOT"
echo '=== CODEQL PATH ==='
command -v codeql || true
for p in "$HOME/codeql/codeql" "$HOME/.local/bin/codeql" "$HOME/bin/codeql" "$HOME/tools/codeql/codeql" "$HOME/opt/codeql/codeql"; do
    if [ -x "$p" ]; then echo "EXECUTABLE: $p"; fi
done
echo '=== QUERY PACK ==='
for p in "$HOME/.codeql/packages/codeql/javascript-queries/2.3.11" "$HOME/codeql/javascript-queries/2.3.11"; do
    if [ -d "$p" ]; then echo "DIRECTORY: $p"; fi
done
echo '=== PATCH PREFLIGHT ==='
for cid in 3504 10819 629; do
    python3 -u phase2_eval_v2.py --case "$cid" --preflight
done
