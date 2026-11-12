#!/bin/bash
#SBATCH --job-name=p2chronology6
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/candidate_chronology_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/candidate_chronology_%j.err

set -euo pipefail
ROOT="$HOME/research_artifacts/prevention_pilot_phase2"
SOURCE="$ROOT/case_screen_issue_recovery_v1_job69671/RESEARCHER_CORPUS_ISSUES_24.json"
OUT="$ROOT/candidate_chronology_job${SLURM_JOB_ID}"
mkdir "$OUT"

python3 - "$SOURCE" "$OUT" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

source, out = map(Path, sys.argv[1:])
if not source.is_file():
    raise SystemExit(f"MISSING SOURCE: {source}")
records = json.loads(source.read_text(encoding="utf-8"))["records"]
ranks = (16, 17, 18, 19, 21, 22)
selected = []
for rank in ranks:
    candidates = [r for r in records if r.get("source_index") == 2 and r.get("queue_rank") == rank]
    if len(candidates) != 1:
        raise SystemExit(f"INVALID SOURCE: rank {rank} has {len(candidates)} snapshot records")
    r = candidates[0]
    row = {k: r.get(k) for k in (
        "queue_rank", "root_id", "repository", "case_id", "case_found",
        "issue_number", "pr_number", "pr_base_sha", "pr_head_sha",
        "issue_created_at", "issue_updated_at", "pr_created_at",
        "body_temporal_verdict", "pre_pr_issue_body_chronology_supported",
        "issue_number_matches_frozen", "pr_number_matches_frozen",
        "base_matches_live_pr")}
    body = r.get("issue_body")
    row["issue_body_sha256"] = hashlib.sha256(body.encode("utf-8")).hexdigest() if isinstance(body, str) else None
    selected.append(row)
    print("=" * 60)
    for key, value in row.items():
        print(f"{key}: {value}")

output = out / "CANDIDATE_CHRONOLOGY.json"
with output.open("x", encoding="utf-8") as handle:
    json.dump({"source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
               "source": str(source), "records": selected}, handle, indent=2)
print("=" * 60)
print(f"COMPLETE: {len(selected)} cases")
print(f"RESULT: {output}")
PY
