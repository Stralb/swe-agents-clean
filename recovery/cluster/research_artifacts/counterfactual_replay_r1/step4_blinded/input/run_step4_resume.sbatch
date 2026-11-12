#!/bin/bash
#SBATCH --job-name=cf_p001_resume
#SBATCH --partition=biggpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=00:45:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/step4_blinded/logs/%x_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/step4_blinded/logs/%x_%j.err

set -euo pipefail

ROOT="$HOME/research_artifacts/counterfactual_replay_r1/step4_blinded/input"
OUT="$HOME/research_artifacts/counterfactual_replay_r1/step4_blinded/results"

mkdir -p "$OUT"
export CODEQL_RAM_MB=12000
export CODEQL_THREADS=4

python3 "$ROOT/resume_blinded_codeql.py" "$ROOT" "$OUT"
