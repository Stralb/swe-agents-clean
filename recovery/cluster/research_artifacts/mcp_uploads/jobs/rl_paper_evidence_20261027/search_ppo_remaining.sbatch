#!/bin/bash
#SBATCH --job-name=rlppo-source-audit
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:08:00
set -euo pipefail
ROOT=/home-mscluster/astrauss/RL-ARC-AGI-3-Project
echo 'PPO DIRECTORIES'
find "$ROOT" -maxdepth 5 -type d -iname '*ppo*' | head -80
echo 'PPO RESULTS AND CONFIGS'
find "$ROOT/results" "$ROOT/configs" -maxdepth 6 -type f \( -iname '*ppo*' -o -iname '*policy*' \) | head -150
echo 'PPO EXPERIMENT REFERENCES'
grep -Rli -E 'ppo.*(improv|v1|v2|novelty|curiosity|effect)|(?:improv|novelty).*ppo' "$ROOT/configs" "$ROOT/results" --include='*.md' --include='*.json' --include='*.csv' 2>/dev/null | head -90 || true
echo 'RECORDED PPO JSON'
find "$ROOT/results" -type f -name record.json | grep -i ppo | head -50
echo PPO_SEARCH_DONE
