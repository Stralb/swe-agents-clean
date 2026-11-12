#!/bin/bash
#SBATCH --job-name=t1eval2bb
#SBATCH --partition=bigbatch
#SBATCH --time=02:30:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T1_PRIMARY_PILOT_EVAL_TWO_BIGBATCH_%j.out

set -euo pipefail

ROOT="$HOME/research_artifacts"
BASE_TMP="${SLURM_TMPDIR:-/tmp}/t1eval_${SLURM_JOB_ID}"

mkdir -p "$BASE_TMP"

pids=()

for local_i in 0 1; do
    i=$((OFFSET + local_i))

    mkdir -p "$BASE_TMP/worker_$i"

    (
        export SLURM_ARRAY_TASK_ID="$i"
        export SLURM_CPUS_PER_TASK=2
        export SLURM_TMPDIR="$BASE_TMP/worker_$i"

        bash "$ROOT/T1_PRIMARY_PILOT_EVAL4_v1.sbatch" \
          > "$ROOT/T1_PRIMARY_PILOT_EVAL_WORKER_${SLURM_JOB_ID}_${i}.out" \
          2>&1
    ) &

    pids+=("$!")
done

failed=0

for pid in "${pids[@]}"; do
    if ! wait "$pid"; then
        failed=1
    fi
done

if [ "$failed" -ne 0 ]; then
    echo "STATUS=WORKER_FAILURE"
    exit 1
fi

echo "STATUS=BOTH_WORKERS_DONE"
