#!/bin/bash
#SBATCH --job-name=t1resolve2
#SBATCH --partition=bigbatch
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T1_RESOLVE2_CONTROLS_v1.out

python3 -u <<'PY'
from pathlib import Path
import json
import re
import sqlite3

DB = Path("/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/data/miner.agentic-js.eval.20260720_224159.hf-snapshot-20260817.db")

CASES = {
    "S5PAIR-033_CONTROL": {
        "candidate_case_ids": [7679, 7681],
        "target_file": "src/lib/copilot.ts",
        "mechanism_hint": "readFileSync",
    },
    "S5PAIR-047_CONTROL": {
        "candidate_case_ids": [34278, 34279, 34280, 34281],
        "target_file": "e2e/ide/github-issues.runtime.issue705.test.ts",
        "mechanism_hint": "regex_text_parse",
    },
}

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

pf_cols = [r[1] for r in con.execute('PRAGMA table_info("pr_files")')]
print("DB:", DB)
print("PR_FILES_COLUMNS:", pf_cols)
print()

base_sql = """
SELECT
    c.id AS case_id,
    r.full_name AS repository,
    i.number AS issue_number,
    i.title AS issue_title,
    p.id AS pr_db_id,
    p.number AS pr_number,
    p.url AS pr_url,
    p.base_sha AS base_sha,
    p.head_sha AS head_sha
FROM cases c
JOIN repos r ON r.id = c.repo_id
JOIN issues i ON i.id = c.issue_id
JOIN pull_requests p ON p.id = c.pr_id
WHERE c.id = ?
"""

for label, cfg in CASES.items():
    print("=" * 120)
    print(label)
    print("TARGET_FILE:", cfg["target_file"])
    print("MECHANISM_HINT:", cfg["mechanism_hint"])
    print()

    for cid in cfg["candidate_case_ids"]:
        row = con.execute(base_sql, (cid,)).fetchone()
        if row is None:
            print("CASE", cid, "NOT_FOUND")
            continue

        d = dict(row)
        print("-" * 100)
        print("CASE_ID:", cid)
        for k in [
            "repository","issue_number","issue_title","pr_number",
            "pr_url","base_sha","head_sha"
        ]:
            print(f"{k}: {d.get(k)}")

        # Exact target-file row(s).
        if "previous_filename" in pf_cols:
            q = """
            SELECT *
            FROM pr_files
            WHERE pr_id = ?
              AND (filename = ? OR previous_filename = ?)
            """
            rows = con.execute(q, (d["pr_db_id"], cfg["target_file"], cfg["target_file"])).fetchall()
        else:
            q = """
            SELECT *
            FROM pr_files
            WHERE pr_id = ?
              AND filename = ?
            """
            rows = con.execute(q, (d["pr_db_id"], cfg["target_file"])).fetchall()

        print("TARGET_FILE_ROWS:", len(rows))
        if not rows:
            continue

        for j, pf in enumerate(rows, 1):
            pfd = dict(pf)
            print(f"TARGET_ROW_{j}_META:")
            for key in ["filename","previous_filename","status","additions","deletions","changes"]:
                if key in pfd:
                    print(f"  {key}: {pfd.get(key)}")

            patch = str(pfd.get("patch") or "")
            print("PATCH_PRESENT:", bool(patch), "PATCH_LEN:", len(patch))

            if patch:
                added = [
                    line[1:] for line in patch.splitlines()
                    if line.startswith("+") and not line.startswith("+++")
                ]
                deleted = [
                    line[1:] for line in patch.splitlines()
                    if line.startswith("-") and not line.startswith("---")
                ]

                if cfg["mechanism_hint"] == "readFileSync":
                    rel = [
                        x for x in added + deleted
                        if "readFileSync" in x or "readFile" in x or "copilot" in x.lower()
                    ]
                else:
                    regexish = re.compile(
                        r"RegExp|\.match\(|\.test\(|\.replace\(|\.split\(|regex|regexp|"
                        r"/[^/\n]{2,}/[gimsuy]*|template|script|style",
                        re.I,
                    )
                    rel = [x for x in added + deleted if regexish.search(x)]

                print("MECHANISM_RELEVANT_LINES:")
                if rel:
                    for x in rel[:80]:
                        print("   ", x)
                else:
                    print("    <none>")

                print("PATCH_HEAD:")
                for line in patch.splitlines()[:180]:
                    print(line)
            else:
                print("MECHANISM_RELEVANT_LINES: <patch unavailable in DB>")

        print()

print("=" * 120)
print("STATUS=DONE")
PY
