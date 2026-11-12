#!/bin/bash
#SBATCH --job-name=arc3-src-audit
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:04:00
set -euo pipefail
umask 077
cd /home-mscluster/astrauss/RL-ARC-AGI-3-Project
echo '=== GIT ROOT, BRANCH, COMMIT, DIRTY ==='
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git status --porcelain | head -15
echo '=== NETWORK SOURCE (READ ONLY) ==='
sed -n '1,240p' src/model.py
echo '=== STRUCTURED EXPLORER SOURCE (READ ONLY) ==='
sed -n '1,180p' src/dqn_v1/exploration.py
echo '=== CLICK ACTION BANK (READ ONLY) ==='
sed -n '1,130p' src/dqn_v1/action_bank.py
echo 'SOURCE_ARCH_AUDIT_DONE'
