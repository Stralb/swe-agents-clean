#!/bin/bash
#SBATCH --job-name=E074_native_semantics
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
ROOT=/home-mscluster/astrauss/RL-ARC-AGI-3-Project
for f in "$ROOT/scripts/probe/action_space.py" "$ROOT/scripts/probe/offline.py" "$ROOT/src/adapter.py" "$ROOT/scripts/probe/level_transition.py" "$ROOT/src/bridge.py"; do
 if [ -f "$f" ];then echo "==== $f ====";sed -n '1,140p' "$f";fi
done
echo E074_NATIVE_SDK_WRAPPER_AUDIT_DONE