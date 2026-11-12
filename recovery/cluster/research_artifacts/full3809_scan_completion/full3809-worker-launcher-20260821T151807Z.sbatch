#!/bin/bash
#SBATCH --job-name=full3809-launch
#SBATCH --partition=batch
#SBATCH --time=01:30:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/full3809_scan_completion/full3809-launch-20260821T151807Z-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/full3809_scan_completion/full3809-launch-20260821T151807Z-%j.err

ROOT="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"
SPOOL="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/data/distributed_spool"
COORD_JOB="44886"

cd "$ROOT" || true
source .venv/bin/activate 2>/dev/null || true

echo "launcher_start=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "coordinator=$COORD_JOB"

READY=0

for attempt in $(seq 1 180); do

    CHEAP_PENDING="$(
      find "$SPOOL/cheap_analysis/pending"         -maxdepth 1         -type f         -name '*.json'         2>/dev/null |
      wc -l
    )"

    CODEQL_PENDING="$(
      find "$SPOOL/codeql_security/pending"         -maxdepth 1         -type f         -name '*.json'         2>/dev/null |
      wc -l
    )"

    STATE="$(
      squeue         -h         -j "$COORD_JOB"         -o "%T"         2>/dev/null |
      head -n 1
    )"

    echo "attempt=$attempt coordinator=${STATE:-gone} cheap=$CHEAP_PENDING codeql=$CODEQL_PENDING"

    if [ "$CHEAP_PENDING" -gt 0 ] &&
       [ "$CODEQL_PENDING" -gt 0 ]; then
        READY=1
        break
    fi

    if [ -z "$STATE" ]; then
        break
    fi

    sleep 30
done

CHEAP_JOB=""
CODEQL_JOB=""

if [ "$READY" = "1" ]; then

    CHEAP_JOB="$(
      sbatch         --parsable         --array=0-1%2         --job-name=full3809-cheap         --partition=stampede         --time=2-23:50:00         --cpus-per-task=4         --mem=32G         --signal=B:TERM@300         --output="$ROOT/logs/full3809-cheap-%A_%a.out"         --error="$ROOT/logs/full3809-cheap-%A_%a.err"         --export=ALL,DISTRIBUTED_SPOOL_ROOT="$SPOOL",CONFIG="$ROOT/config.agentic_js.yml"         "$ROOT/run_distributed_cheap.slurm"
    )" || true

    CODEQL_JOB="$(
      sbatch         --parsable         --array=0-1%2         --job-name=full3809-codeql         --partition=bigbatch         --time=2-23:50:00         --cpus-per-task=4         --mem=64G         --signal=B:TERM@300         --output="$ROOT/logs/full3809-codeql-%A_%a.out"         --error="$ROOT/logs/full3809-codeql-%A_%a.err"         --export=ALL,DISTRIBUTED_SPOOL_ROOT="$SPOOL",CONFIG="$ROOT/config.agentic_js.yml"         "$ROOT/run_distributed_codeql.slurm"
    )" || true

    echo "cheap_array_job=$CHEAP_JOB"
    echo "codeql_array_job=$CODEQL_JOB"

else

    echo "WORKERS_NOT_SUBMITTED"

fi

echo
echo "===== FINAL SQUEUE ====="

squeue -u "$USER"   -o "%.18i %.12P %.30j %.10T %.10M %.6D %R"   2>/dev/null || true
