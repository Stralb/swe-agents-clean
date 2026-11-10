#!/bin/bash
#SBATCH --job-name=E074_team_inventory
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:08:00
set -euo pipefail
HOMEBASE=/home-mscluster/astrauss
PROJECT="$HOMEBASE/RL-ARC-AGI-3-Project"
E074="$HOMEBASE/e074_human_training"
ROOT="$HOMEBASE/E074_HUMAN_TO_POLICY_20261019"
echo "=== E074 VERIFIED ARTIFACT INVENTORY ==="
for p in "$E074/E074_TRAINING_COMPLETE_FREEZE.json" "$E074/E074_OFFLINE_POLICY_PROBE.json" "$E074/E074_VALIDATED_HUMAN_GATE.json" "$E074/human_five_training/E068_HUMAN_TRAINING_MANIFEST.json" "$E074/trained_human/HUMAN_PRETRAIN_VERIFIED.json" "$E074/trained_human/E069_PRE_HOLDOUT_FREEZE.json";do
 if test -f "$p";then sha256sum "$p";stat -c "FILE %n %s %y" "$p";else echo "ABSENT $p";fi
done
echo "=== E074 CKPT HASHES ==="
for mode in bc ddqn shuffled no_history;do p="$E074/trained_human/history_${mode}.pt";test ! -f "$p" || sha256sum "$p";done
echo "=== RESEARCH STAGE NAMES ==="
find "$PROJECT/results" -mindepth 1 -maxdepth 2 -type d -printf "%P\n" | head -n 100
echo "=== MOST RECENT SOURCE STAGES ==="
find "$PROJECT/scripts" "$PROJECT/src" -mindepth 1 -maxdepth 2 -type d -printf "%P\n" | grep -E '(^|/)e0[0-9]+' | tail -n 110
echo "=== SOURCES AND CONFIGS ==="
for p in "$PROJECT/configs/e034_systems.json" "$PROJECT/E035_NOTES.md" "$ROOT/README.md";do if test -f "$p";then stat -c "FILE %n %s" "$p";fi;done
echo "=== END READ ONLY ==="