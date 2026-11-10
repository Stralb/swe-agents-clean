#!/bin/bash
#SBATCH --job-name=prev_p2_eval
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --output=phase2_eval_%j.out
#SBATCH --error=phase2_eval_%j.err

ROOT="/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2"
export PHASE2_ROOT="$ROOT"

cd "$ROOT" || exit 1
mkdir -p generated phase2_eval_results
python3 evaluate_phase2.py
