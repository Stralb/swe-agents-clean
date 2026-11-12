#!/bin/bash
#SBATCH --job-name=cf_cal_ctx
#SBATCH --partition=biggpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/logs/%x_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/logs/%x_%j.err

set -euo pipefail

OUT="$HOME/research_artifacts/counterfactual_replay_r1"
DB="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/data/final-study-snapshot-20260829/full3809-scanner-complete-20260829.db"
CSV="$OUT/CALIBRATION_CANDIDATES_CONTEXT.csv"
QC="$OUT/CALIBRATION_CANDIDATES_QC.txt"
mkdir -p "$OUT/logs"

python3 - "$DB" "$CSV" "$QC" <<'PY'
from __future__ import annotations
import csv, hashlib, sqlite3, sys
from pathlib import Path

DB = Path(sys.argv[1])
CSV_OUT = Path(sys.argv[2])
QC_OUT = Path(sys.argv[3])

selected = [
    ("S5PAIR-044", "positive", 21682, "remotion-dev/remotion"),
    ("S5PAIR-044", "negative", 21678, "remotion-dev/remotion"),
    ("S5PAIR-025", "positive", 3581, "breaking-brake/cc-wf-studio"),
    ("S5PAIR-025", "negative", 3587, "breaking-brake/cc-wf-studio"),
    ("S5PAIR-050", "positive", 16439, "mksglu/context-mode"),
    ("S5PAIR-050", "negative", 16437, "mksglu/context-mode"),
]
ids = [x[2] for x in selected]
meta = {x[2]: x for x in selected}

if not DB.is_file():
    raise SystemExit(f"PRECHECK_FAIL: DB missing: {DB}")

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
marks = ",".join("?" for _ in ids)

rows = con.execute(
    f"""
    SELECT
        c.id AS case_id,
        r.full_name AS repository,
        r.html_url AS repository_url,
        i.number AS issue_number,
        i.url AS issue_url,
        i.title AS issue_title,
        i.body AS issue_body,
        p.number AS pr_number,
        p.url AS pr_url,
        p.title AS pr_title,
        p.body AS pr_body,
        p.base_sha,
        p.head_sha
    FROM cases c
    JOIN repos r ON r.id = c.repo_id
    JOIN issues i ON i.id = c.issue_id
    JOIN pull_requests p ON p.id = c.pr_id
    WHERE c.id IN ({marks})
    ORDER BY c.id
    """,
    ids,
).fetchall()

if len(rows) != 6:
    present = {int(r["case_id"]) for r in rows}
    missing = sorted(set(ids) - present)
    raise SystemExit(f"PRECHECK_FAIL: expected 6 rows, got {len(rows)}; missing={missing}")

out = []
for r in rows:
    cid = int(r["case_id"])
    pair_id, role, _, expected_repo = meta[cid]
    if r["repository"] != expected_repo:
        raise SystemExit(f"PRECHECK_FAIL: repo mismatch case {cid}: {r['repository']} != {expected_repo}")
    if not (r["issue_title"] or "").strip():
        raise SystemExit(f"PRECHECK_FAIL: empty issue title case {cid}")
    if not (r["issue_body"] or "").strip():
        raise SystemExit(f"PRECHECK_FAIL: empty issue body case {cid}")
    if not (r["base_sha"] or "").strip():
        raise SystemExit(f"PRECHECK_FAIL: missing base SHA case {cid}")

    out.append({
        "pair_id": pair_id,
        "role": role,
        "case_id": cid,
        "expected_repository": expected_repo,
        "repository": r["repository"],
        "repository_url": r["repository_url"],
        "issue_number": r["issue_number"],
        "issue_url": r["issue_url"],
        "issue_title": r["issue_title"],
        "issue_body": r["issue_body"],
        "pr_number": r["pr_number"],
        "pr_url": r["pr_url"],
        "pr_title": r["pr_title"],
        "pr_body": r["pr_body"],
        "base_sha": r["base_sha"],
        "head_sha": r["head_sha"],
    })

out.sort(key=lambda x: (x["pair_id"], x["role"]))
fields = list(out[0].keys())
with CSV_OUT.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader(); w.writerows(out)

h = hashlib.sha256(CSV_OUT.read_bytes()).hexdigest()
qc = [
    "CALIBRATION CANDIDATE CONTEXT QC",
    "================================",
    f"Rows extracted: {len(out)}",
    f"Pairs extracted: {len(set(x['pair_id'] for x in out))}",
    "Missing issue titles: 0",
    "Empty issue bodies: 0",
    "Missing base SHA: 0",
    f"Output SHA256: {h}",
    "STATUS: PASS",
]
QC_OUT.write_text("\n".join(qc) + "\n", encoding="utf-8")
print("\n".join(qc))
for x in out:
    print(x["pair_id"], x["role"], x["case_id"], x["repository"], x["base_sha"])
con.close()
PY

ls -lh "$CSV" "$QC"
sha256sum "$CSV"
