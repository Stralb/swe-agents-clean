#!/bin/bash
#SBATCH --job-name=rl-index-historical
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:06:00
set -euo pipefail
ROOT=/home-mscluster/astrauss/RL-ARC-AGI-3-Project
echo "ROOT_DIRS"
find "$ROOT" -maxdepth 2 -type d | grep -Ei '/(results|experiments|papers|archive|reports|v[0-9]+|e0[1-9]|e[123][0-9]|synthetic|ppo|dqn)' | head -160
echo "V8_PPO_SYNTHETIC_FILES"
find "$ROOT" -maxdepth 6 -type f | grep -Ei '(v8|relational|backplay|reverse.curric|ppo.*(result|summary|report)|e021|e02[012]|synthetic.*(result|report))' | head -130
echo "E004_E017_SUMMARIES"
find "$ROOT" -maxdepth 5 -type f | grep -Ei '(E00[4-9]|E01[0-7]|e00[4-9]|e01[0-7]).*(REPORT|SUMMARY|DECISION|FINDING|csv|json)' | head -130
echo "INDEX_DONE"
