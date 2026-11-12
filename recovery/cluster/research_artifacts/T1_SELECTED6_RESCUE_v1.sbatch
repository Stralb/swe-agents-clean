#!/bin/bash
#SBATCH --job-name=t1_sel6_rescue
#SBATCH --partition=batch
#SBATCH --time=00:05:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T1_SELECTED6_RESCUE_v1.out

set -euo pipefail

OUT="$HOME/research_artifacts/T1_SELECTED6_EXTRACT_v1"
ARCHIVE="$HOME/research_artifacts/T1_SELECTED6_EXTRACT_v1.tar.gz"

python3 - "$OUT" <<'PY'
from pathlib import Path
import hashlib
import json
import sys

OUT = Path(sys.argv[1]).resolve()

EXPECTED = {
    "R1": "CROOT-00608-03",
    "R2": "CROOT-03429-01",
    "R3": "CROOT-04131-01",
    "R4": "CROOT-05355-01",
    "R5": "CROOT-10339-01",
    "R6": "CROOT-16213-01",
}

if not OUT.exists():
    raise SystemExit(f"MISSING OUT DIRECTORY: {OUT}")

cases = []
problems = []

for slot, root_id in EXPECTED.items():
    case_dir = OUT / f"{slot}__{root_id}"
    meta = case_dir / "METADATA.json"

    if not case_dir.exists():
        problems.append(f"{slot}: missing directory {case_dir.name}")
        continue

    if not meta.exists():
        problems.append(f"{slot}: missing METADATA.json")
        continue

    try:
        obj = json.loads(meta.read_text(errors="strict"))
    except Exception as e:
        problems.append(f"{slot}: bad METADATA.json: {e}")
        continue

    if obj.get("slot") != slot:
        problems.append(
            f"{slot}: metadata slot={obj.get('slot')!r}"
        )

    if obj.get("root_id") != root_id:
        problems.append(
            f"{slot}: metadata root={obj.get('root_id')!r}"
        )

    required = [
        "TASK_ORIGINAL.md",
        "HISTORICAL_DIFF_AUDIT_ONLY.patch",
        "CHANGED_FILES.txt",
    ]

    for name in required:
        if not (case_dir / name).exists():
            problems.append(f"{slot}: missing {name}")

    cases.append(obj)

print("=== EXISTING EXTRACTION QC ===")
print("cases_found =", len(cases))

for obj in cases:
    print(
        obj.get("slot"),
        obj.get("root_id"),
        obj.get("repo"),
        "base=" + str(obj.get("base_sha", ""))[:12],
        "head=" + str(obj.get("head_sha", ""))[:12],
    )

if problems:
    print()
    print("=== QC FAILURES ===")
    for x in problems:
        print(x)
    raise SystemExit("RESCUE ABORTED: extracted material is incomplete")

if len(cases) != 6:
    raise SystemExit(
        f"RESCUE ABORTED: expected 6 cases, found {len(cases)}"
    )

manifest = {
    "schema": "T1_SELECTED6_EXTRACT_v1",
    "selection_frozen_sha256":
        "571a976a6db8f9ed2e170130bde8d1bc791bc3ac2da9a0a835a7aadb87baea4c",
    "rescue_note":
        "Original extraction completed but failed while removing temporary Git worktrees. "
        "Manifest/checksums reconstructed from the six completed per-root METADATA.json files.",
    "cases": cases,
}

(OUT / "MANIFEST.json").write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

checks = []

for p in sorted(OUT.rglob("*")):
    if not p.is_file():
        continue

    rel = p.relative_to(OUT)

    # Temporary Git repositories are not part of the research export.
    if "_work" in rel.parts:
        continue

    if p.name == "SHA256SUMS.txt":
        continue

    h = hashlib.sha256(p.read_bytes()).hexdigest()
    checks.append(f"{h}  {rel}")

(OUT / "SHA256SUMS.txt").write_text(
    "\n".join(checks) + "\n",
    encoding="utf-8",
)

print()
print(json.dumps({
    "status": "PASS",
    "cases": len(cases),
    "roots": [x["root_id"] for x in cases],
    "hashed_files": len(checks),
}, indent=2))

print("STATUS=DONE")
PY

cd "$HOME/research_artifacts"

rm -f "$ARCHIVE"

tar \
  --exclude='T1_SELECTED6_EXTRACT_v1/_work' \
  -czf "$ARCHIVE" \
  T1_SELECTED6_EXTRACT_v1

echo
echo "=== ARCHIVE ==="
ls -lh "$ARCHIVE"
sha256sum "$ARCHIVE"

echo
echo "=== ARCHIVE QC ==="
COUNT=$(tar -tzf "$ARCHIVE" | grep -c '/METADATA.json$' || true)
echo "METADATA_COUNT=$COUNT"

if [ "$COUNT" -ne 6 ]; then
    echo "ERROR: expected 6 METADATA.json files"
    exit 1
fi

if tar -tzf "$ARCHIVE" | grep -q '/_work/'; then
    echo "ERROR: _work leaked into archive"
    exit 1
fi

echo "ARCHIVE_QC=PASS"
