#!/bin/bash
set -euo pipefail

OUT="$1"
SRC="/home-mscluster/astrauss/PROVENANCE_CLOSURE_STEP2_v1.0/STEP2_EVIDENCE_AUDIT_455.csv"
NORM="$OUT/STEP2_EVIDENCE_AUDIT_455_NORMALIZED.csv"

mkdir -p "$OUT"

echo "HOST=$(hostname)"
echo "START=$(date -u +%FT%TZ)"

python3 - "$SRC" "$NORM" <<'PY'
import csv
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])

with src.open(newline="", encoding="utf-8-sig") as f:
    r = csv.DictReader(f)
    fields = list(r.fieldnames or [])
    rows = list(r)

location_cols = [
    c for c in fields
    if "location" in c.lower()
]

print("LOCATION_COLUMNS=", location_cols)

changed_cells = 0

for row in rows:
    for col in location_cols:
        value = row.get(col) or ""
        if "::" not in value:
            continue

        parts = []

        for item in value.split(";"):
            item = item.strip()

            if not item:
                continue

            if "::" in item:
                left, right = item.split("::", 1)

                # Root-census patch evidence needs the actual changed Git file.
                # Dependency subpaths such as
                # package-lock.json::packages/node_modules/foo
                # therefore become package-lock.json.
                item = left.strip()
                changed_cells += 1

            parts.append(item)

        row[col] = "; ".join(parts)

with dst.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)

print("ROWS=", len(rows))
print("NORMALIZED_LOCATION_CELLS=", changed_cells)
print("OUTPUT=", dst)

assert len(rows) == 455
PY

echo
echo "=== GITHUB AUTH ==="
gh auth status

echo
echo "=== ROOT-CENSUS EXTRACTION ==="

python3 \
  /home-mscluster/astrauss/c_root_census_v1_0/prepare_c_root_census.py \
  --audit "$NORM" \
  --out "$OUT" \
  > "$OUT/prepare.stdout.log" \
  2> "$OUT/prepare.stderr.log"

echo
echo "=== QC ==="
cat "$OUT/C_CONTEXT_QC.json"

echo
echo "=== SUPPLEMENTS ==="
cat "$OUT/NEEDS_SUPPLEMENT.csv"

python3 - "$OUT" <<'PY'
import csv
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])

qc = json.loads(
    (out / "C_CONTEXT_QC.json").read_text()
)

assert qc["status"] == "PASS"
assert qc["pcs"] == 455
assert qc["cases"] == 191
assert qc["single_pc_workflows"] == 112
assert qc["multi_pc_workflows"] == 79
assert qc["pcs_requiring_llm_partitioning"] == 343
assert qc["pr_fetch_failures"] == []

assert (
    qc["multi_workflows_needing_target_evidence_supplement"]
    == 0
), qc

assert (
    qc["multi_workflows_needing_patch_supplement"]
    == 0
), qc

with (out / "NEEDS_SUPPLEMENT.csv").open(
    newline="",
    encoding="utf-8"
) as f:
    rows = list(csv.DictReader(f))

assert len(rows) == 0, rows

required = [
    "AUTO_SINGLETON_ROOTS.csv",
    "C_CODER_A_BLIND.tar.gz",
    "C_CODER_B_BLIND.tar.gz",
    "C_PRIVATE_MAPPING_DO_NOT_GIVE_CODERS.tar.gz",
]

for name in required:
    assert (out / name).exists(), name

print("C_FIX2_WORKER=PASS")
PY

touch "$OUT/JOB_COMPLETE.ok"

echo
echo "END=$(date -u +%FT%TZ)"
