#!/bin/bash
set -euo pipefail

RUNROOT="$1"

python3 - "$RUNROOT" <<'PY'
import json
import shutil
import sys
from pathlib import Path

root = Path(sys.argv[1])

valid = []

for name in ["biggpu", "bigbatch"]:
    d = root / name
    q = d / "C_CONTEXT_QC.json"

    if not q.exists() or not (d / "JOB_COMPLETE.ok").exists():
        continue

    qc = json.loads(q.read_text())

    ok = (
        qc.get("status") == "PASS"
        and qc.get("pcs") == 455
        and qc.get("cases") == 191
        and qc.get("single_pc_workflows") == 112
        and qc.get("multi_pc_workflows") == 79
        and qc.get("pcs_requiring_llm_partitioning") == 343
        and qc.get("pr_fetch_failures") == []
        and qc.get("multi_workflows_needing_target_evidence_supplement") == 0
        and qc.get("multi_workflows_needing_patch_supplement") == 0
    )

    if ok:
        valid.append((name, d, qc))

if not valid:
    raise SystemExit("FAIL: no clean extraction available")

valid.sort(key=lambda x: 0 if x[0] == "biggpu" else 1)

name, src, qc = valid[0]
dst = root / "final_selected"

if dst.exists():
    shutil.rmtree(dst)

shutil.copytree(src, dst)

selection = {
    "status": "PASS",
    "selected": name,
    "clean_workers": [x[0] for x in valid],
    "qc": qc,
}

(root / "C_SELECTION.json").write_text(
    json.dumps(selection, indent=2)
)

print(json.dumps(selection, indent=2))
PY

cd "$RUNROOT"

tar -czf C_STAGE1_CLEAN_READY.tar.gz \
  C_SELECTION.json \
  final_selected

sha256sum C_STAGE1_CLEAN_READY.tar.gz \
  > C_STAGE1_CLEAN_READY.tar.gz.sha256

cp -f \
  C_STAGE1_CLEAN_READY.tar.gz \
  /home-mscluster/astrauss/C_STAGE1_CLEAN_READY_LATEST.tar.gz

cp -f \
  C_STAGE1_CLEAN_READY.tar.gz.sha256 \
  /home-mscluster/astrauss/C_STAGE1_CLEAN_READY_LATEST.tar.gz.sha256

echo "C_SELECTION_AND_PACKAGE=PASS"
