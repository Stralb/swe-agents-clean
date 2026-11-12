#!/bin/bash
#SBATCH --job-name=urlsrc
#SBATCH --partition=batch
#SBATCH --time=00:05:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/url_boundary_census/sources.txt
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/url_boundary_census/sources.err

set -euo pipefail

echo "=== ROOT / PROVENANCE DATA FILES ==="

for D in \
  "$HOME/research_artifacts/D_COMPLETE_ROOT_PROVENANCE_v1_0" \
  "$HOME/research_artifacts/C_ROOT_CENSUS_FIX2_20260904T151622Z"
do
    echo
    echo "DIR=$D"

    if [ -d "$D" ]; then
        find "$D" -maxdepth 4 -type f \
          \( -name '*.csv' -o -name '*.jsonl' -o -name '*.json' -o -name '*.xlsx' \) \
          -printf '%s %p\n' | sort -n
    fi
done

echo
echo "=== LIKELY URL/HOST CONTENT FILES ==="

python3 - <<'PY'
from pathlib import Path

roots = [
    Path.home() / "research_artifacts/D_COMPLETE_ROOT_PROVENANCE_v1_0",
    Path.home() / "research_artifacts/C_ROOT_CENSUS_FIX2_20260904T151622Z",
]

terms = [
    "url", "hostname", "host", "domain", "origin",
    "redirect", "fetch", "http", "https"
]

for root in roots:
    if not root.exists():
        continue

    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".csv", ".json", ".jsonl", ".md", ".txt"}:
            continue
        if p.stat().st_size > 50_000_000:
            continue

        try:
            txt = p.read_text(errors="ignore").lower()
        except Exception:
            continue

        hits = [t for t in terms if t in txt]
        if hits:
            print(str(p), "TERMS=" + ",".join(hits))

print("STATUS=DONE")
PY
