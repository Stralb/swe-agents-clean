#!/bin/bash
#SBATCH --job-name=arno_rpl7_patch_preflight
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/preflight_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/preflight_%j.err
set -euo pipefail
source "$HOME/new/malicious-issue-miner-rate-smart/.venv/bin/activate"
python3 -m py_compile "$HOME/research_artifacts/mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/scan_case.py"
python3 - <<'PY'
import json,hashlib
from pathlib import Path
R=Path.home()/"research_artifacts"
m=R/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2/MANIFEST.json"
j=json.loads(m.read_text())
assert j["status"]=="21_BLINDED_OPAQUE_INPUT_ZIPS_FINAL_VERIFIED"
rows=j["runs"]
assert len(rows)==21 and len({x["run_id"] for x in rows})==21
for x in rows:
 p=m.parent/"run_zips"/(x["run_id"]+".zip")
 assert p.is_file()
 cases={}
for x in rows:cases.setdefault(x["case_id"],set()).add(x["condition"])
assert len(cases)==7 and all(v=={"P1","P2","P3"} for v in cases.values())
q=R/"mcp_uploads/arno_rpl7_patch_upload_20261030/RECEIPT_RPL7_RUN_04B827A1E668.zip"
print(json.dumps({"scan_script_compiles":True,"verified_research_inputs":21,"source_cases":7,
"incoming_binary_uploaded":q.exists(),"codeql_bin":str(Path.home()/"tools/codeql/codeql")}))
PY
