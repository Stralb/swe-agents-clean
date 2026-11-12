#!/bin/bash
#SBATCH --job-name=t1early3scan
#SBATCH --partition=bigbatch
#SBATCH --time=00:15:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T1_EARLY3_SCANNER_GATE_QUERY_v1.out

python3 -u <<'PY'
import csv
import json
import sqlite3
from pathlib import Path

DB = Path("/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/data/miner.agentic-js.eval.20260720_224159.hf-snapshot-20260817.db")
OUT = Path("/home-mscluster/astrauss/research_artifacts/T1_EARLY3_SCANNER_GATE_QUERY_v1")
OUT.mkdir(parents=True, exist_ok=True)

PAIRS = {
    "S5PAIR-002": {
        "positive": {"case_id": 629, "target": "src/music/spotify/spotify-oauth.ts"},
        "control": {"case_id": 10184, "target": "platform/backend/src/clients/chat-mcp-client.test.ts"},
    },
    "S5PAIR-005": {
        "positive": {"case_id": 3882, "target": "packages/api/src/artifacts/update.ts"},
        "control": {"case_id": 3885, "target": "packages/api/src/agents/initialize.ts"},
    },
    "S5PAIR-022": {
        "positive": {"case_id": 313, "target": "packages/pi-ai/src/utils/repair-tool-json.ts"},
        "control": {"case_id": 332, "target": "src/resources/extensions/gsd/bootstrap/write-gate.ts"},
    },
}

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

def cols(table):
    return [r[1] for r in con.execute(f'PRAGMA table_info("{table}")')]

def rows_as_dicts(sql, args=()):
    return [dict(r) for r in con.execute(sql, args)]

case_sql = """
SELECT
    c.id AS case_id,
    r.full_name AS repository,
    i.number AS issue_number,
    i.title AS issue_title,
    p.id AS pr_id,
    p.number AS pr_number,
    p.base_sha,
    p.head_sha
FROM cases c
JOIN repos r ON r.id = c.repo_id
JOIN issues i ON i.id = c.issue_id
JOIN pull_requests p ON p.id = c.pr_id
WHERE c.id = ?
"""

finding_cols = cols("scanner_findings")
print("DB=", DB)
print("SCANNER_FINDINGS_COLUMNS=", finding_cols)

all_case_ids = sorted({
    x["case_id"]
    for pair in PAIRS.values()
    for x in pair.values()
})

marks = ",".join("?" for _ in all_case_ids)
findings = rows_as_dicts(
    f"""
    SELECT *
    FROM scanner_findings
    WHERE case_id IN ({marks})
    ORDER BY case_id, scanner, rule_id, file_path, line, id
    """,
    all_case_ids,
)

by_case = {}
for cid in all_case_ids:
    by_case[cid] = [r for r in findings if r.get("case_id") == cid]

summary = {}
flat = []

for pair_id, pair in PAIRS.items():
    print("\n" + "=" * 120)
    print("PAIR", pair_id)
    print("=" * 120)

    summary[pair_id] = {}

    for role in ("positive", "control"):
        spec = pair[role]
        cid = spec["case_id"]
        target = spec["target"]
        meta = dict(con.execute(case_sql, (cid,)).fetchone())
        frows = by_case[cid]

        introduced = [
            r for r in frows
            if str(r.get("introduced")).lower() in {"1", "true", "yes"}
        ]
        target_intro = [
            r for r in introduced
            if (r.get("file_path") or "") == target
        ]

        print(f"\nROLE={role.upper()} CASE={cid}")
        for k in ["repository","issue_number","issue_title","pr_number","base_sha","head_sha"]:
            print(f"{k}: {meta.get(k)}")
        print("target:", target)
        print("introduced_findings_total:", len(introduced))
        print("introduced_findings_target:", len(target_intro))

        for r in target_intro:
            print(
                "TARGET_FINDING:",
                json.dumps(
                    {
                        "scanner": r.get("scanner"),
                        "rule_id": r.get("rule_id"),
                        "finding_type": r.get("finding_type"),
                        "severity": r.get("severity"),
                        "file_path": r.get("file_path"),
                        "line": r.get("line"),
                        "description": r.get("description"),
                    },
                    ensure_ascii=False,
                )
            )

        summary[pair_id][role] = {
            "case": meta,
            "target": target,
            "introduced_findings_total": len(introduced),
            "target_findings": [
                {
                    "scanner": r.get("scanner"),
                    "rule_id": r.get("rule_id"),
                    "finding_type": r.get("finding_type"),
                    "severity": r.get("severity"),
                    "file_path": r.get("file_path"),
                    "line": r.get("line"),
                    "description": r.get("description"),
                }
                for r in target_intro
            ],
        }

        for r in frows:
            flat.append({
                "pair_id": pair_id,
                "role": role,
                "target_file": target,
                **r,
            })

    pos_rules = {
        (x.get("scanner"), x.get("rule_id"))
        for x in summary[pair_id]["positive"]["target_findings"]
        if x.get("scanner") and x.get("rule_id")
    }
    ctrl_intro = [
        r for r in by_case[pair["control"]["case_id"]]
        if str(r.get("introduced")).lower() in {"1", "true", "yes"}
    ]
    ctrl_same = [
        r for r in ctrl_intro
        if (r.get("scanner"), r.get("rule_id")) in pos_rules
    ]

    summary[pair_id]["positive_target_rules"] = [
        {"scanner": s, "rule_id": q} for s, q in sorted(pos_rules)
    ]
    summary[pair_id]["control_same_rule_introduced_findings"] = [
        {
            "scanner": r.get("scanner"),
            "rule_id": r.get("rule_id"),
            "file_path": r.get("file_path"),
            "line": r.get("line"),
            "description": r.get("description"),
        }
        for r in ctrl_same
    ]

    print("\nPAIR_RULE_GATE:")
    print("positive_target_rules=", json.dumps(summary[pair_id]["positive_target_rules"], ensure_ascii=False))
    print("control_same_rule_introduced_count=", len(ctrl_same))

# Save all relevant scanner findings.
if flat:
    fields = []
    seen = set()
    for row in flat:
        for k in row:
            if k not in seen:
                seen.add(k)
                fields.append(k)
    with (OUT / "EARLY3_ALL_SCANNER_FINDINGS.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(flat)

# Dump scanner-job/run rows for audit, using whichever linking columns exist.
audit = {}
case_to_pr = {}
for cid in all_case_ids:
    row = dict(con.execute(case_sql, (cid,)).fetchone())
    case_to_pr[cid] = row["pr_id"]

for table in ("scanner_jobs", "scanner_runs"):
    try:
        table_cols = cols(table)
    except Exception as e:
        audit[table] = {"error": str(e)}
        continue

    relevant = []
    if "case_id" in table_cols:
        mm = ",".join("?" for _ in all_case_ids)
        relevant = rows_as_dicts(
            f'SELECT * FROM "{table}" WHERE case_id IN ({mm})',
            all_case_ids,
        )
    elif "pr_id" in table_cols:
        pr_ids = sorted(case_to_pr.values())
        mm = ",".join("?" for _ in pr_ids)
        relevant = rows_as_dicts(
            f'SELECT * FROM "{table}" WHERE pr_id IN ({mm})',
            pr_ids,
        )

    audit[table] = {
        "columns": table_cols,
        "rows": relevant,
    }

    print("\n" + "=" * 120)
    print(table.upper(), "COLUMNS=", table_cols)
    for r in relevant:
        print(json.dumps(r, ensure_ascii=False, default=str))

(OUT / "EARLY3_SCANNER_GATE_SUMMARY.json").write_text(
    json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n",
    encoding="utf-8",
)
(OUT / "EARLY3_SCANNER_EXECUTION_AUDIT.json").write_text(
    json.dumps(audit, indent=2, ensure_ascii=False, default=str) + "\n",
    encoding="utf-8",
)

print("\nOUTPUT_DIR=", OUT)
print("STATUS=DONE")
PY

rc=$?
echo "PYTHON_RC=$rc"
if [ "$rc" -eq 0 ]; then
  tar -czf \
    /home-mscluster/astrauss/research_artifacts/T1_EARLY3_SCANNER_GATE_QUERY_v1.tar.gz \
    -C /home-mscluster/astrauss/research_artifacts \
    T1_EARLY3_SCANNER_GATE_QUERY_v1
  sha256sum /home-mscluster/astrauss/research_artifacts/T1_EARLY3_SCANNER_GATE_QUERY_v1.tar.gz
fi
