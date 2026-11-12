#!/bin/bash
#SBATCH --job-name=arno_v2_preflight
#SBATCH --partition=batch
#SBATCH --time=00:45:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --output=arno_v2_preflight_%j.log
set -euo pipefail
ZIP="$HOME/research_artifacts/mcp_uploads/jobs/arno_unified_evidence_20261031_v1/output/ARNO_EVIDENCE_V2_INTEGRATION_KIT_20261101.zip"
DIR="$SLURM_SUBMIT_DIR/extracted"
ENTRY="$DIR/ARNO_EVIDENCE_V2_INTEGRATION_KIT_20261101/wits_integrate_v2.py"
test -f "$ZIP"
if [ -e "$ENTRY" ]; then
  echo "Refusing to overwrite previously extracted script" >&2
  exit 2
fi
mkdir -p "$DIR"
python3 -m zipfile -e "$ZIP" "$DIR"
python3 -B "$ENTRY"
echo "PREFLIGHT_ONLY_COMPLETE: original DB unchanged; no v2 DB created"
