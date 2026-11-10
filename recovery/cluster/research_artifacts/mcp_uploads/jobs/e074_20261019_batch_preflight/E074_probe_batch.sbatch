#!/bin/bash
#SBATCH --job-name=E074_batch
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/E074_probe_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/E074_probe_%j.err
set -u
echo "E074_READONLY_PREFLIGHT_BEGIN"
date -u
hostname
printf "USER=%s HOME=%s\n" "$USER" "$HOME"
ROOT="/home-mscluster/astrauss/E074_HUMAN_TO_POLICY_20261019"
WORK="/home-mscluster/astrauss/e074_human_training"
ARCHIVE="/home-mscluster/astrauss/E074_CONTINUATION_READY_20261019.zip"
PY="/home-mscluster/astrauss/arc26/.venv/bin/python"
for path in "$ROOT" "$WORK" "$ARCHIVE" "$PY" "$ROOT/code/e074_pipeline.py" "$ROOT/slurm/e074_resume_safe.sh" "$WORK/human_snapshot/E068_HUMAN_DATA_LOCK.json" "$WORK/human_five_training/E068_HUMAN_TRAINING_MANIFEST.json" "$WORK/E074_VALIDATED_HUMAN_GATE.json" "$WORK/E074_TRAINING_COMPLETE_FREEZE.json" "$WORK/trained_human/history_bc.pt" "$WORK/trained_human/history_ddqn.pt" "$WORK/trained_human/history_shuffled.pt" "$WORK/trained_human/history_no_history.pt"; do
 if [ -e "$path" ]; then stat -c "PRESENT %n %s bytes %y" "$path"; else printf "MISSING %s\n" "$path"; fi
done
echo "WORK_TOP_LEVEL_IF_PRESENT"
if [ -d "$WORK" ]; then ls -la "$WORK" | head -n 55; fi
echo "ROOT_TOP_LEVEL_IF_PRESENT"
if [ -d "$ROOT" ]; then ls -la "$ROOT" | head -n 35; fi
echo "ENV_PACKAGE_CHECK"
if [ -x "$PY" ]; then "$PY" -c 'import importlib.util,sys; print("PYTHON",sys.executable); print({k: bool(importlib.util.find_spec(k)) for k in ("numpy","torch","pyarrow","huggingface_hub","pytest")})' 2>&1; fi
echo "NETWORK_DNS_HF"
getent hosts huggingface.co | head -n 2 || true
echo "NETWORK_HTTP_HF"
curl -sSL -I --max-time 15 "https://huggingface.co" 2>&1 | head -n 15 || true
echo "E074_READONLY_PREFLIGHT_END"
