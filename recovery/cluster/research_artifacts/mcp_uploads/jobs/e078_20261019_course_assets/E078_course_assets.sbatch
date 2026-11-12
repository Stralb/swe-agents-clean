#!/bin/bash
#SBATCH --job-name=E078_course_assets
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:06:00
set -euo pipefail
P=/home-mscluster/astrauss/RL-ARC-AGI-3-Project
echo '=== ROOT ==='
ls -la "$P" | head -n 75
echo '=== PPO / DQN code ==='
find "$P/src" "$P/scripts" "$P/configs" "$P/kaggle" -maxdepth 5 -type f \( -iname '*ppo*' -o -iname '*dqn*' -o -iname '*submission*' -o -iname '*agent*' -o -iname '*algorithm*' \) -print 2>/dev/null | head -n 150
echo '=== SECOND RL METHOD ==='
grep -R -n -m 1 -E '^class .*PPO|PPO\(|from stable_baselines3 import PPO|PPOTrainer' "$P/src" "$P/scripts" "$P/kaggle" --include='*.py' 2>/dev/null | head -n 65 || true
echo '=== KAGGLE / PAPER ==='
find "$P" -maxdepth 4 -type f \( -name 'submission.csv' -o -name '*kaggle*.py' -o -name '*.tex' -o -name '*report*.pdf' -o -name 'paper.pdf' -o -name 'my_agent.py' \) -print | head -n 100
echo '=== E071 PPO SOURCE CHECK ==='
for p in /home-mscluster/astrauss/e074_human_training/E074_TRAINING_COMPLETE_FREEZE.json /home-mscluster/astrauss/E074_HUMAN_TO_POLICY_20261019/vendor/e071/code /home-mscluster/astrauss/arc26/.venv/bin/python;do if [ -e "$p" ];then stat -c '%n EXISTS' "$p";fi;done
echo E078_READONLY_SUBMISSION_AUDIT_END