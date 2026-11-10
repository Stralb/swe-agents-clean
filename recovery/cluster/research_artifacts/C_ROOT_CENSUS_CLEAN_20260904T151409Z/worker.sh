#!/bin/bash
set -euo pipefail

OUT="$1"
TMP="${SLURM_TMPDIR:-/tmp}/c_root_$SLURM_JOB_ID"

mkdir -p "$TMP" "$OUT"

cp \
  /home-mscluster/astrauss/c_root_census_v1_0/prepare_c_root_census.py \
  "$TMP/prepare_c_root_census.py"

cp \
  /home-mscluster/astrauss/c_root_census_v1_0/CODER_PROMPT.md \
  "$TMP/CODER_PROMPT.md"

cp \
  /home-mscluster/astrauss/c_root_census_v1_0/C0_ROOT_CODEBOOK_FROZEN.md \
  "$TMP/C0_ROOT_CODEBOOK_FROZEN.md"

python3 - "$TMP/prepare_c_root_census.py" <<'PY'
from pathlib import Path
import sys

p = Path(sys.argv[1])
s = p.read_text()

old = """def parse_locations(s: str):
    out = []
    for raw in (s or '').split(';'):
        raw = raw.strip()
        if not raw:
            continue
        m = re.match(r'^(.*?):(\\\\d+)$', raw)
        if m:
            out.append((m.group(1).strip(), int(m.group(2))))
        else:
            out.append((raw, None))
    return out
"""

new = """def parse_locations(s: str):
    out = []
    for raw in (s or '').split(';'):
        raw = raw.strip()
        if not raw:
            continue

        # Dependency locations may be encoded as:
        # package-lock.json::packages/node_modules/foo
        # The actual changed Git file is package-lock.json.
        if '::' in raw:
            raw = raw.split('::', 1)[0].strip()

        m = re.match(r'^(.*?):(\\\\d+)$', raw)
        if m:
            out.append((m.group(1).strip(), int(m.group(2))))
        else:
            out.append((raw, None))
    return out
"""

if old not in s:
    raise SystemExit("FAIL: parse_locations block not found")

p.write_text(s.replace(old, new, 1))
print("PATCH_LOCATION_NORMALIZATION=PASS")
PY

echo "HOST=$(hostname)"
echo "START=$(date -u +%FT%TZ)"

gh auth status

python3 \
  "$TMP/prepare_c_root_census.py" \
  --audit /home-mscluster/astrauss/PROVENANCE_CLOSURE_STEP2_v1.0/STEP2_EVIDENCE_AUDIT_455.csv \
  --out "$OUT"

python3 - "$OUT/C_CONTEXT_QC.json" "$OUT/NEEDS_SUPPLEMENT.csv" <<'PY'
import csv
import json
import sys
from pathlib import Path

qc = json.loads(Path(sys.argv[1]).read_text())

assert qc["status"] == "PASS"
assert qc["pcs"] == 455
assert qc["cases"] == 191
assert qc["single_pc_workflows"] == 112
assert qc["multi_pc_workflows"] == 79
assert qc["pcs_requiring_llm_partitioning"] == 343
assert qc["pr_fetch_failures"] == []

assert qc["multi_workflows_needing_target_evidence_supplement"] == 0, qc
assert qc["multi_workflows_needing_patch_supplement"] == 0, qc

with open(sys.argv[2], newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

assert rows == [], rows

for name in [
    "AUTO_SINGLETON_ROOTS.csv",
    "C_CODER_A_BLIND.tar.gz",
    "C_CODER_B_BLIND.tar.gz",
    "C_PRIVATE_MAPPING_DO_NOT_GIVE_CODERS.tar.gz",
]:
    assert (Path(sys.argv[1]).parent / name).exists(), name

print("C_CLEAN_WORKER=PASS")
PY

touch "$OUT/JOB_COMPLETE.ok"

echo "END=$(date -u +%FT%TZ)"
