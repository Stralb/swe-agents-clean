#!/bin/bash
set -euo pipefail

RUNROOT="$1"

python3 - "$RUNROOT" <<'PY'
import json
import shutil
import sys
from pathlib import Path

root = Path(sys.argv[1])

candidates = [
    ("biggpu", root / "biggpu"),
    ("bigbatch", root / "bigbatch"),
]

rows = []

for name, path in candidates:
    qc_path = path / "C_CONTEXT_QC.json"

    if not qc_path.exists():
        rows.append({
            "name": name,
            "path": str(path),
            "usable": False,
            "reason": "missing C_CONTEXT_QC.json",
            "score": 10**9,
        })
        continue

    try:
        qc = json.loads(qc_path.read_text())
    except Exception as e:
        rows.append({
            "name": name,
            "path": str(path),
            "usable": False,
            "reason": f"invalid QC JSON: {e}",
            "score": 10**9,
        })
        continue

    structural_ok = (
        qc.get("status") == "PASS"
        and qc.get("pcs") == 455
        and qc.get("cases") == 191
        and qc.get("single_pc_workflows") == 112
        and qc.get("multi_pc_workflows") == 79
        and qc.get("pcs_requiring_llm_partitioning") == 343
    )

    supplement_score = (
        int(qc.get("multi_workflows_needing_target_evidence_supplement", 999999))
        + int(qc.get("multi_workflows_needing_patch_supplement", 999999))
    )

    fetch_failures = len(qc.get("pr_fetch_failures") or [])

    rows.append({
        "name": name,
        "path": str(path),
        "usable": structural_ok,
        "supplement_score": supplement_score,
        "fetch_failures": fetch_failures,
        "score": supplement_score * 1000 + fetch_failures,
        "qc": qc,
    })

usable = [x for x in rows if x["usable"]]

if not usable:
    print(json.dumps({"status": "FAIL", "candidates": rows}, indent=2))
    raise SystemExit("No structurally valid extraction completed")

usable.sort(
    key=lambda x: (
        x["score"],
        0 if x["name"] == "biggpu" else 1,
    )
)

best = usable[0]
src = Path(best["path"])
dst = root / "final_selected"

if dst.exists():
    shutil.rmtree(dst)
dst.mkdir(parents=True)

wanted = [
    "C_CONTEXT_QC.json",
    "NEEDS_SUPPLEMENT.csv",
    "AUTO_SINGLETON_ROOTS.csv",
    "C_CODER_A_BLIND.tar.gz",
    "C_CODER_B_BLIND.tar.gz",
    "C_PRIVATE_MAPPING_DO_NOT_GIVE_CODERS.tar.gz",
    "prepare.stdout.log",
    "prepare.stderr.log",
]

missing = []

for name in wanted:
    p = src / name
    if p.exists():
        shutil.copy2(p, dst / name)
    else:
        missing.append(name)

selection = {
    "status": "PASS",
    "selected": best["name"],
    "selected_path": str(src),
    "selected_score": best["score"],
    "missing_selected_artifacts": missing,
    "all_candidates": rows,
}

(root / "C_SELECTION.json").write_text(
    json.dumps(selection, indent=2)
)

print(json.dumps(selection, indent=2))

critical = [
    "C_CONTEXT_QC.json",
    "AUTO_SINGLETON_ROOTS.csv",
    "C_CODER_A_BLIND.tar.gz",
    "C_CODER_B_BLIND.tar.gz",
    "C_PRIVATE_MAPPING_DO_NOT_GIVE_CODERS.tar.gz",
]

for name in critical:
    if not (dst / name).exists():
        raise SystemExit(f"Missing critical selected artifact: {name}")
PY

cd "$RUNROOT"

tar -czf C_STAGE1_READY.tar.gz \
  C_SELECTION.json \
  final_selected

sha256sum C_STAGE1_READY.tar.gz > C_STAGE1_READY.tar.gz.sha256

cp -f \
  C_STAGE1_READY.tar.gz \
  /home-mscluster/astrauss/C_STAGE1_READY_LATEST.tar.gz

cp -f \
  C_STAGE1_READY.tar.gz.sha256 \
  /home-mscluster/astrauss/C_STAGE1_READY_LATEST.tar.gz.sha256

echo
echo "=== SELECTED QC ==="
cat "$RUNROOT/final_selected/C_CONTEXT_QC.json"

echo
echo "=== SUPPLEMENT REQUIREMENTS ==="
cat "$RUNROOT/final_selected/NEEDS_SUPPLEMENT.csv"

echo
echo "=== PACKAGE ==="
ls -lh \
  "$RUNROOT/C_STAGE1_READY.tar.gz" \
  /home-mscluster/astrauss/C_STAGE1_READY_LATEST.tar.gz

echo
cat "$RUNROOT/C_STAGE1_READY.tar.gz.sha256"
