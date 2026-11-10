#!/bin/bash
#SBATCH --job-name=find_cf_out
#SBATCH --partition=batch
#SBATCH --time=00:10:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/find_calibration_outputs/result.txt
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/find_calibration_outputs/error.txt

python3 - <<'PY'
import os
import re
import zipfile
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
RUN = re.compile(r'C(?:00[1-9]|01[0-6])', re.I)

prune = {
    ".git", ".cache", ".codeql", ".local",
    "node_modules", "__pycache__", ".venv",
    "venv", "site-packages"
}

candidates = []

for root, dirs, files in os.walk(HOME):
    rp = Path(root)

    dirs[:] = [
        d for d in dirs
        if d not in prune
    ]

    # Avoid unrelated giant corpus/cache trees.
    s = str(rp)
    if "/data/cache/" in s or "/distributed_spool/" in s:
        dirs[:] = []
        continue

    for fn in files:
        p = rp / fn

        try:
            st = p.stat()
        except Exception:
            continue

        # Calibration was produced recently; avoid old unrelated files.
        dt = datetime.fromtimestamp(st.st_mtime, timezone.utc)
        recent = dt.date() >= datetime(2026, 9, 17, tzinfo=timezone.utc).date()

        name_hit = bool(RUN.search(fn))
        interesting_ext = (
            fn.endswith(".zip")
            or fn.endswith(".patch")
            or fn.endswith(".diff")
            or fn.endswith(".tar.gz")
            or fn.endswith(".tgz")
        )

        if not (name_hit or (recent and interesting_ext)):
            continue

        info = {
            "path": str(p),
            "size": st.st_size,
            "mtime": dt.isoformat(),
            "run_ids": sorted(set(x.upper() for x in RUN.findall(str(p)))),
            "members": [],
        }

        if p.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(p) as z:
                    names = z.namelist()
                useful = [
                    n for n in names
                    if RUN.search(n)
                    or "submission.patch" in n.lower()
                    or n.lower().endswith(".patch")
                    or n.lower().endswith(".diff")
                ]
                info["members"] = useful[:100]
                info["run_ids"] = sorted(set(
                    info["run_ids"] +
                    [x.upper() for n in useful for x in RUN.findall(n)]
                ))
            except Exception as e:
                info["zip_error"] = str(e)

        candidates.append(info)

print("=== CALIBRATION OUTPUT DISCOVERY ===")
print("candidate_files =", len(candidates))

for x in sorted(candidates, key=lambda z: z["mtime"], reverse=True):
    print()
    print("PATH =", x["path"])
    print("SIZE =", x["size"])
    print("MTIME =", x["mtime"])
    print("RUN_IDS =", ",".join(x["run_ids"]) if x["run_ids"] else "-")
    if x.get("members"):
        print("RELEVANT_MEMBERS:")
        for m in x["members"]:
            print(" ", m)
    if x.get("zip_error"):
        print("ZIP_ERROR =", x["zip_error"])

found = set()
for x in candidates:
    found.update(x["run_ids"])

print()
print("=== RUN COVERAGE FOUND ===")
for i in range(1,17):
    r=f"C{i:03d}"
    print(r, "FOUND" if r in found else "NOT_FOUND")

print()
print("FOUND_COUNT =", len(found))
print("STATUS=DONE")
PY
