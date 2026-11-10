#!/bin/bash
#SBATCH --job-name=mim-revalidate-agg
#SBATCH --time=00:20:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --output=/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/logs/mim-revalidate-agg-%j.out
#SBATCH --error=/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/logs/mim-revalidate-agg-%j.err

ROOT="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"

cd "$ROOT" || true

source .venv/bin/activate

export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

python scripts/aggregate_scanner_revalidation_17.py
