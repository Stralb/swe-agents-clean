#!/bin/bash
#SBATCH --job-name=arno_v2_import
#SBATCH --partition=batch
#SBATCH --time=12:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --output=arno_v2_import_%j.log
set -euo pipefail
ZIP="$HOME/research_artifacts/mcp_uploads/jobs/arno_unified_evidence_20261031_v1/output/ARNO_EVIDENCE_V2_INTEGRATION_KIT_20261101.zip"
DIR="$SLURM_SUBMIT_DIR/extracted"
KIT="$DIR/ARNO_EVIDENCE_V2_INTEGRATION_KIT_20261101"
if [ -e "$KIT/wits_integrate_v2.py" ]; then
  echo "Refusing to overwrite preexisting extracted integration script" >&2
  exit 2
fi
test -f "$ZIP"
mkdir -p "$DIR"
python3 -m zipfile -e "$ZIP" "$DIR"
python3 -B "$KIT/wits_integrate_v2.py" --execute
DB="$HOME/research_artifacts/mcp_uploads/jobs/arno_evidence_v2_20261101_corrective/ARNO_UNIFIED_FULL_EVIDENCE_DB_v2.sqlite"
python3 -B "$KIT/verify_v2.py" "$DB"
echo "INTEGRATION_AND_INDEPENDENT_QA_COMPLETE"
