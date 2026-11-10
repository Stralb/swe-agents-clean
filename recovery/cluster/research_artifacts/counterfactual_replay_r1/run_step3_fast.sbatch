#!/bin/bash
#SBATCH --job-name=cf_ctx_fast
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

CSV="$OUT/STEP3_selected_case_context_10.csv"
QC="$OUT/STEP3_CONTEXT_QC.txt"

echo "============================================================"
echo "COUNTERFACTUAL REPLAY STEP 3 - FAST EXACT EXTRACTION"
echo "============================================================"
echo "HOST=$(hostname)"
echo "START=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "DB=$DB"
echo

python3 - "$DB" "$CSV" "$QC" <<'PY'
from __future__ import annotations

import csv
import hashlib
import os
import sqlite3
import sys
from pathlib import Path

DB = Path(sys.argv[1])
CSV_OUT = Path(sys.argv[2])
QC_OUT = Path(sys.argv[3])

selected = [
    ("S5PAIR-019", "positive", 21654, "crafter-station/petdex"),
    ("S5PAIR-019", "negative", 21657, "crafter-station/petdex"),

    ("S5PAIR-016", "positive", 17320, "worldwonderer/oh-story-claudecode"),
    ("S5PAIR-016", "negative", 17321, "worldwonderer/oh-story-claudecode"),

    ("S5PAIR-005", "positive", 3882, "danny-avila/LibreChat"),
    ("S5PAIR-005", "negative", 3885, "danny-avila/LibreChat"),

    ("S5PAIR-012", "positive", 16594, "whyour/qinglong"),
    ("S5PAIR-012", "negative", 16591, "whyour/qinglong"),

    ("S5PAIR-001", "positive", 334, "gsd-build/gsd-2"),
    ("S5PAIR-001", "negative", 314, "gsd-build/gsd-2"),
]

ids = [x[2] for x in selected]
meta = {x[2]: x for x in selected}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


print("============================================================")
print("PREFLIGHT")
print("============================================================")

if not DB.is_file():
    raise SystemExit(
        f"PRECHECK_FAIL: exact frozen DB does not exist:\n{DB}"
    )

print("DB_EXISTS=YES")
print("DB_SIZE_BYTES=", DB.stat().st_size)

con = sqlite3.connect(
    f"file:{DB}?mode=ro",
    uri=True,
)
con.row_factory = sqlite3.Row

required_tables = {
    "cases",
    "repos",
    "issues",
    "pull_requests",
}

present_tables = {
    r[0]
    for r in con.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type='table'
    """)
}

missing_tables = sorted(
    required_tables - present_tables
)

if missing_tables:
    raise SystemExit(
        "PRECHECK_FAIL: missing required tables: "
        + ", ".join(missing_tables)
    )

print("REQUIRED_TABLES=PASS")


required_cols = {
    "cases": {
        "id",
        "repo_id",
        "issue_id",
        "pr_id",
    },
    "repos": {
        "id",
        "full_name",
        "html_url",
    },
    "issues": {
        "id",
        "number",
        "url",
        "title",
        "body",
    },
    "pull_requests": {
        "id",
        "number",
        "url",
        "title",
        "body",
        "base_sha",
        "head_sha",
    },
}

for table, expected in required_cols.items():
    actual = {
        r[1]
        for r in con.execute(
            f'PRAGMA table_info("{table}")'
        )
    }

    missing = sorted(expected - actual)

    if missing:
        raise SystemExit(
            f"PRECHECK_FAIL: {table} missing columns: "
            + ", ".join(missing)
        )

print("REQUIRED_COLUMNS=PASS")


marks = ",".join("?" for _ in ids)

count = con.execute(
    f"""
    SELECT COUNT(*)
    FROM cases
    WHERE id IN ({marks})
    """,
    ids,
).fetchone()[0]

print("SELECTED_CASE_COUNT=", count)

if count != 10:
    present = [
        r[0]
        for r in con.execute(
            f"""
            SELECT id
            FROM cases
            WHERE id IN ({marks})
            ORDER BY id
            """,
            ids,
        )
    ]

    missing = sorted(set(ids) - set(present))

    raise SystemExit(
        "PRECHECK_FAIL: expected 10 selected cases, "
        f"found {count}; missing={missing}"
    )

print("SELECTED_CASES=PASS")


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

    JOIN repos r
      ON r.id = c.repo_id

    JOIN issues i
      ON i.id = c.issue_id

    JOIN pull_requests p
      ON p.id = c.pr_id

    WHERE c.id IN ({marks})

    ORDER BY c.id
    """,
    ids,
).fetchall()

if len(rows) != 10:
    raise SystemExit(
        f"PRECHECK_FAIL: joined query returned {len(rows)} rows, expected 10"
    )

print("JOIN_QUERY=PASS")


repo_errors = []

for r in rows:
    case_id = int(r["case_id"])
    expected_repo = meta[case_id][3]

    if r["repository"] != expected_repo:
        repo_errors.append(
            (
                case_id,
                expected_repo,
                r["repository"],
            )
        )

if repo_errors:
    raise SystemExit(
        f"PRECHECK_FAIL: repository mismatch: {repo_errors}"
    )

print("REPOSITORY_MATCH=PASS")
print("PREFLIGHT_STATUS=PASS")
print()


print("============================================================")
print("EXTRACTING")
print("============================================================")

output = []

for r in rows:
    case_id = int(r["case_id"])

    pair_id, role, _, expected_repo = meta[case_id]

    output.append({
        "pair_id": pair_id,
        "role": role,
        "case_id": case_id,
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


fields = [
    "pair_id",
    "role",
    "case_id",
    "expected_repository",

    "repository",
    "repository_url",

    "issue_number",
    "issue_url",
    "issue_title",
    "issue_body",

    "pr_number",
    "pr_url",
    "pr_title",
    "pr_body",

    "base_sha",
    "head_sha",
]

with open(
    CSV_OUT,
    "w",
    newline="",
    encoding="utf-8-sig",
) as f:
    writer = csv.DictWriter(
        f,
        fieldnames=fields,
    )

    writer.writeheader()
    writer.writerows(output)


missing_titles = sum(
    not str(x["issue_title"] or "").strip()
    for x in output
)

empty_bodies = sum(
    not str(x["issue_body"] or "").strip()
    for x in output
)

missing_base = sum(
    not str(x["base_sha"] or "").strip()
    for x in output
)

missing_head = sum(
    not str(x["head_sha"] or "").strip()
    for x in output
)

pair_counts = {}

for x in output:
    pair_counts.setdefault(
        x["pair_id"],
        set(),
    ).add(x["role"])

bad_pairs = {
    k: sorted(v)
    for k, v in pair_counts.items()
    if v != {"positive", "negative"}
}

if bad_pairs:
    raise SystemExit(
        f"QC_FAIL: incomplete pair roles: {bad_pairs}"
    )


status = (
    "PASS"
    if (
        len(output) == 10
        and missing_titles == 0
        and len(pair_counts) == 5
    )
    else "CHECK_REQUIRED"
)

qc_lines = [
    "COUNTERFACTUAL REPLAY STEP 3 QC",
    "================================",
    "",
    f"Database: {DB}",
    f"Database size bytes: {DB.stat().st_size}",
    "",
    "Preflight DB exists: PASS",
    "Preflight required tables: PASS",
    "Preflight required columns: PASS",
    "Preflight selected cases: PASS",
    "Preflight join query: PASS",
    "Preflight repository identities: PASS",
    "",
    f"Rows extracted: {len(output)}",
    f"Pairs extracted: {len(pair_counts)}",
    f"Missing issue titles: {missing_titles}",
    f"Empty issue bodies: {empty_bodies}",
    f"Missing base SHA: {missing_base}",
    f"Missing head SHA: {missing_head}",
    "",
    f"Output CSV: {CSV_OUT}",
    f"Output SHA256: {sha256(CSV_OUT)}",
    "",
    f"STEP 3 STATUS: {status}",
]

QC_OUT.write_text(
    "\n".join(qc_lines) + "\n",
    encoding="utf-8",
)

print("\n".join(qc_lines))

print()
print("============================================================")
print("PAIR PREVIEW")
print("============================================================")

for x in sorted(
    output,
    key=lambda z: (
        z["pair_id"],
        z["role"],
    ),
):
    print(
        x["pair_id"],
        "|",
        x["role"],
        "| case",
        x["case_id"],
        "|",
        x["repository"],
    )
    print(
        "  issue:",
        x["issue_number"],
        "|",
        str(x["issue_title"])[:160],
    )
    print(
        "  base:",
        x["base_sha"],
    )

con.close()
PY

echo
echo "============================================================"
echo "OUTPUT FILES"
echo "============================================================"

ls -lh \
  "$CSV" \
  "$QC"

echo
echo "============================================================"
echo "SHA256"
echo "============================================================"

sha256sum "$CSV"

echo
echo "END=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
