#!/bin/bash
#SBATCH --job-name=arno_v6_final_baseline_links
#SBATCH --partition=batch
#SBATCH --dependency=afterok:78027
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:25:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_v6_exact_baseline_registry/apply_postbackup_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_v6_exact_baseline_registry/apply_postbackup_%j.err
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
import json
r=Path.home()/"research_artifacts/ARNO_MASTER_DB/snapshots"
f=r/"ARNO_RESEARCH_MASTER_POST_RECOVERY_20261029.sqlite.json"
s=r/"ARNO_RESEARCH_MASTER_POST_RECOVERY_20261029.sqlite"
if not (f.is_file() and s.is_file()):
    raise SystemExit("Verified final backup or certificate missing")
d=json.loads(f.read_text())
if d.get("status")!="VERIFIED_POST_RECOVERY_BACKUP" or d.get("quick_check")!="ok" or d.get("snapshot")!=str(s) or d.get("snapshot_size")!=s.stat().st_size:
    raise SystemExit("Backup certificate invalid; refusing DB write")
print("Verified post-recovery backup certificate and snapshot presence",flush=True)
PY
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_v6_exact_baseline_registry/register.py --apply
