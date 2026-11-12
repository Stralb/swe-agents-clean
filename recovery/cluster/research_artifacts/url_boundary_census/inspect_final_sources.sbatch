#!/bin/bash
#SBATCH --job-name=url_schema
#SBATCH --partition=batch
#SBATCH --time=00:05:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/url_boundary_census/final_sources.txt
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/url_boundary_census/final_sources.err

set -euo pipefail

C="$HOME/research_artifacts/C_ROOT_CENSUS_FIX2_20260904T151622Z/final_selected"
D="$HOME/research_artifacts/D_COMPLETE_ROOT_PROVENANCE_v1_0"

python3 - <<'PY'
from pathlib import Path
import csv, json

dirs = [
    Path.home()/"research_artifacts/C_ROOT_CENSUS_FIX2_20260904T151622Z/final_selected",
    Path.home()/"research_artifacts/D_COMPLETE_ROOT_PROVENANCE_v1_0",
]

print("=== FINAL CANDIDATE DATA FILES ===")
for d in dirs:
    print("\nDIR =", d)
    if not d.exists():
        print("MISSING")
        continue
    for p in sorted(d.glob("*")):
        if p.is_file() and p.suffix.lower() in {".csv",".json",".jsonl"}:
            print(p.name, p.stat().st_size)

print("\n=== CSV HEADERS ===")
seen = set()
for d in dirs:
    if not d.exists():
        continue
    for p in d.rglob("*.csv"):
        if p.stat().st_size > 100_000_000:
            continue
        key = p.name
        if key in seen:
            continue
        seen.add(key)
        try:
            with p.open(newline="", encoding="utf-8-sig", errors="ignore") as f:
                r = csv.reader(f)
                header = next(r)
            print("\nFILE =", p)
            print("HEADER =", " | ".join(header))
        except Exception as e:
            print("ERROR", p, e)

print("\n=== JSON STRUCTURE FOR FINAL ROOT FILES ===")
for d in dirs:
    if not d.exists():
        continue
    for p in d.glob("*.json"):
        try:
            obj=json.loads(p.read_text(errors="ignore"))
        except Exception:
            continue
        print("\nFILE =", p)
        if isinstance(obj, dict):
            print("TOP_KEYS =", list(obj)[:80])
        elif isinstance(obj, list):
            print("LIST_LEN =", len(obj))
            if obj and isinstance(obj[0], dict):
                print("ROW_KEYS =", list(obj[0])[:80])

print("\nSTATUS=DONE")
PY
