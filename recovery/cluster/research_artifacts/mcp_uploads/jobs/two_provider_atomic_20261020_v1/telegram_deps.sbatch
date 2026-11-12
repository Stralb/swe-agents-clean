#!/bin/bash
#SBATCH --job-name=telegram_dep_check
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:20:00
set -euo pipefail
export PATH="$HOME/tools/node/bin:$HOME/.bun/bin:$PATH"
repo="$HOME/research_artifacts/prevention_pilot_phase2/provider_variants_20261020/08152/baseline/REPO"
cd "$repo"
command -v bun
bun --version
timeout 180s bun install --lockfile-only
