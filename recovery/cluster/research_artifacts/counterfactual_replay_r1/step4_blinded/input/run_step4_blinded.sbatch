#!/bin/bash
#SBATCH --job-name=cf_p001_cql
#SBATCH --partition=biggpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=01:00:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/step4_blinded/logs/%x_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/step4_blinded/logs/%x_%j.err

ROOT="$HOME/research_artifacts/counterfactual_replay_r1/step4_blinded/input"
OUT="$HOME/research_artifacts/counterfactual_replay_r1/step4_blinded/results"

mkdir -p "$OUT"

export CODEQL_RAM_MB=12000
export CODEQL_THREADS=4

python3 "$ROOT/run_blinded_codeql.py" "$ROOT" "$OUT"
