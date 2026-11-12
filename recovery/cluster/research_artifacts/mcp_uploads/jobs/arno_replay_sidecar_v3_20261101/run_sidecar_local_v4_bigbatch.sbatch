#!/bin/bash
#SBATCH --job-name=arno_sidecar_local
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --output=arno_sidecar_local_%j.log
set -euo pipefail
BASE="$HOME/research_artifacts/mcp_uploads/jobs/arno_replay_sidecar_v3_20261101"
cd "$BASE"
python3 -B fix_local_v4.py
export ARNO_SIDECAR_LOCAL_OUTPUT="${SLURM_TMPDIR:-/tmp}/arno_sidecar_v4_${SLURM_JOB_ID}"
mkdir -p "$ARNO_SIDECAR_LOCAL_OUTPUT"
echo "SQLite scratch output: $ARNO_SIDECAR_LOCAL_OUTPUT"
python3 -B sidecar_build_local_v4.py
python3 -B sidecar_build_local_v4.py --execute
export DESTINATION="$BASE/output_local_v4_${SLURM_JOB_ID}"
python3 - <<'PY'
import hashlib,json,os,shutil,sqlite3
from pathlib import Path
src=Path(os.environ["ARNO_SIDECAR_LOCAL_OUTPUT"])
dst=Path(os.environ["DESTINATION"])
assert not dst.exists(), "Refusing to overwrite a previous sidecar"
dbsrc=src/"ARNO_REPLAY_EVIDENCE_SIDECAR_v3.sqlite"
qsrc=src/"ARNO_REPLAY_SIDECAR_v3_QA.json"
report=json.loads(qsrc.read_text())
assert report["status"]=="PASS_WITH_DOCUMENTED_GAPS"
assert report["combined_normalized_runs"]==94
assert report["embedded_assets_SHA_verified"]==207
with sqlite3.connect("file:"+str(dbsrc)+"?mode=ro",uri=True) as c:
 assert c.execute("PRAGMA quick_check").fetchone()[0]=="ok"
 assert c.execute("SELECT COUNT(*) FROM arno_v3_asset_bytes").fetchone()[0]==207
def digest(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(8*1024*1024),b""):h.update(b)
 return h.hexdigest()
src_hash=digest(dbsrc)
dst.mkdir(parents=True)
tmp=dst/"ARNO_REPLAY_EVIDENCE_SIDECAR_v3.sqlite.partial"
final=dst/"ARNO_REPLAY_EVIDENCE_SIDECAR_v3.sqlite"
with dbsrc.open("rb") as f, tmp.open("xb") as g:
 shutil.copyfileobj(f,g,8*1024*1024)
assert digest(tmp)==src_hash,"Remote copy SHA-256 mismatch"
os.replace(tmp,final)
report["sidecar_database"]=str(final)
report["final_copy_sha256"]=src_hash
report["copy_verified"]=True
(dst/"ARNO_REPLAY_SIDECAR_v3_QA.json").write_text(json.dumps(report,indent=2))
print(json.dumps({"SIDE_CAR":"PASS","file":str(final),"sha256":src_hash,"bytes":final.stat().st_size,"runs":94,"assets":207}),flush=True)
PY
echo "ARNO_V4_LOCAL_SCRATCH_AND_REMOTE_COPY_COMPLETE"
