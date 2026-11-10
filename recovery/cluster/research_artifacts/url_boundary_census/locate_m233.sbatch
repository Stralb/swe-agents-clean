#!/bin/bash
#SBATCH --job-name=find_m233
#SBATCH --partition=batch
#SBATCH --time=00:10:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/url_boundary_census/m233_sources.txt
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/url_boundary_census/m233_sources.err

set -euo pipefail

python3 - <<'PY'
from pathlib import Path
import csv, json

ROOTS = [
    Path.home()/"research_artifacts/D_COMPLETE_ROOT_PROVENANCE_v1_0",
    Path.home()/"research_artifacts/C_ROOT_CENSUS_FIX2_20260904T151622Z",
]

print("=== CSV/JSONL FILES WITH 233 OR 342 ROWS ===")

for root in ROOTS:
    if not root.exists():
        continue

    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".csv", ".jsonl"}:
            continue
        if p.stat().st_size > 100_000_000:
            continue

        try:
            if p.suffix.lower() == ".csv":
                with p.open(newline="", encoding="utf-8-sig", errors="ignore") as f:
                    r = csv.reader(f)
                    header = next(r, [])
                    n = sum(1 for _ in r)
            else:
                with p.open(encoding="utf-8", errors="ignore") as f:
                    lines = [x for x in f if x.strip()]
                n = len(lines)
                if lines:
                    try:
                        obj = json.loads(lines[0])
                        header = list(obj) if isinstance(obj, dict) else []
                    except Exception:
                        header = []
                else:
                    header = []

            if n in {233, 342}:
                print("\nFILE =", p)
                print("ROWS =", n)
                print("HEADER =", " | ".join(header[:80]))
        except Exception:
            pass

print("\n=== FILES WITH ROUTING/M/H/T/Cohort-LIKE HEADERS ===")

for root in ROOTS:
    if not root.exists():
        continue

    for p in root.rglob("*.csv"):
        if p.stat().st_size > 100_000_000:
            continue
        try:
            with p.open(newline="", encoding="utf-8-sig", errors="ignore") as f:
                r = csv.reader(f)
                header = next(r, [])
            h = " ".join(header).lower()
            if any(x in h for x in [
                "route", "routing", "cohort",
                "mechanism-selection", "final class",
                "root class", "decision class"
            ]):
                print("\nFILE =", p)
                print("HEADER =", " | ".join(header[:100]))
        except Exception:
            pass

print("\n=== SMALL TEXT FILES MENTIONING 233 / MECHANISM-SELECTION ===")

for root in ROOTS:
    if not root.exists():
        continue

    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".md", ".txt", ".json"}:
            continue
        if p.stat().st_size > 5_000_000:
            continue

        try:
            txt = p.read_text(errors="ignore")
        except Exception:
            continue

        low = txt.lower()
        if "233" in txt or "mechanism-selection" in low:
            print("\nFILE =", p)
            for line in txt.splitlines():
                if "233" in line or "mechanism-selection" in line.lower():
                    print(line[:1000])

print("\nSTATUS=DONE")
PY
