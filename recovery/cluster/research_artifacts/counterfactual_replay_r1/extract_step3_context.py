from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

OUT = Path(sys.argv[1]).resolve()
PROJECT = Path(sys.argv[2]).resolve()

MAP = OUT / "STEP3_selected_cases.csv"
OUTCSV = OUT / "STEP3_selected_case_context_10.csv"
OUTQC = OUT / "STEP3_CONTEXT_QC.txt"
DBREPORT = OUT / "STEP3_DB_DISCOVERY.txt"

with open(MAP, newline="", encoding="utf-8") as f:
    selected = list(csv.DictReader(f))

target_ids = [str(r["case_id"]).strip() for r in selected]


def norm(x):
    return re.sub(r"[^a-z0-9]+", "", str(x or "").lower())


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def tables(conn):
    return [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    ]


def columns(conn, table):
    return [
        r[1]
        for r in conn.execute(
            f'PRAGMA table_info("{table}")'
        )
    ]


def choose_col(cols, aliases):
    nmap = {norm(c): c for c in cols}
    for a in aliases:
        if norm(a) in nmap:
            return nmap[norm(a)]
    return None


def first(d, aliases):
    if not d:
        return ""
    nmap = {norm(k): k for k in d.keys()}
    for a in aliases:
        k = nmap.get(norm(a))
        if k is not None:
            v = d.get(k)
            if v is not None and str(v).strip() != "":
                return str(v)
    return ""


def fetch_one(conn, table, aliases, value):
    if not table or value in ("", None):
        return {}

    cols = columns(conn, table)
    idcol = choose_col(cols, aliases)

    if not idcol:
        return {}

    vals = [value]
    try:
        vals.append(int(value))
    except Exception:
        pass

    for v in vals:
        try:
            row = conn.execute(
                f'SELECT * FROM "{table}" WHERE "{idcol}" = ? LIMIT 1',
                (v,),
            ).fetchone()
            if row:
                return dict(row)
        except Exception:
            pass

    return {}


def related_table(schema, preferred, contains):
    for p in preferred:
        if p in schema:
            return p

    for table, cols in schema.items():
        nt = norm(table)
        if any(norm(x) in nt for x in contains):
            return table

    return None


def count_ids(conn, table, idcol):
    placeholders = ",".join("?" for _ in target_ids)
    try:
        q = (
            f'SELECT COUNT(*) FROM "{table}" '
            f'WHERE CAST("{idcol}" AS TEXT) IN ({placeholders})'
        )
        return int(conn.execute(q, target_ids).fetchone()[0])
    except Exception:
        return 0


# Prefer the previously expected snapshot, but do not rely on it.
exact_candidates = [
    PROJECT
    / "data"
    / "final-study-snapshot-20260829"
    / "full3809-scanner-complete-20260829.db",

    PROJECT
    / "miner.agentic-js.eval.20260720_224159.db",
]

db_candidates = []

for p in exact_candidates:
    if p.exists():
        db_candidates.append(p)

# Bounded search only inside the project data tree.
data_root = PROJECT / "data"

if data_root.exists():
    for root, dirs, files in os.walk(data_root):
        try:
            depth = len(Path(root).relative_to(data_root).parts)
        except Exception:
            depth = 0

        if depth > 6:
            dirs[:] = []
            continue

        dirs[:] = [
            d for d in dirs
            if d not in {
                ".git",
                ".venv",
                "__pycache__",
                "node_modules",
            }
        ]

        for fn in files:
            if fn.endswith((".db", ".sqlite", ".sqlite3")):
                p = Path(root) / fn
                if p not in db_candidates:
                    db_candidates.append(p)

discovery = []
best = None

for db in db_candidates:
    try:
        conn = sqlite3.connect(
            f"file:{db}?mode=ro",
            uri=True,
        )
        conn.row_factory = sqlite3.Row

        for table in tables(conn):
            cols = columns(conn, table)

            idcols = [
                c for c in cols
                if norm(c) in {
                    "caseid",
                    "id",
                    "sourceid",
                    "workflowid",
                }
            ]

            for idcol in idcols:
                score = count_ids(
                    conn,
                    table,
                    idcol,
                )

                if score:
                    record = {
                        "db": str(db),
                        "table": table,
                        "idcol": idcol,
                        "matches": score,
                    }
                    discovery.append(record)

                    if (
                        best is None
                        or score > best["matches"]
                    ):
                        best = record

        conn.close()

    except Exception as e:
        discovery.append({
            "db": str(db),
            "error": repr(e),
        })

DBREPORT.write_text(
    json.dumps(discovery, indent=2),
    encoding="utf-8",
)

if best is None:
    raise SystemExit(
        "ERROR: No project database contained any of "
        "the 10 selected case IDs.\n"
        f"See {DBREPORT}"
    )

if best["matches"] < len(target_ids):
    raise SystemExit(
        f"ERROR: Best DB/table matched only "
        f"{best['matches']}/{len(target_ids)} selected cases.\n"
        f"Best candidate: {best}\n"
        f"See {DBREPORT}"
    )

DB = Path(best["db"])
CASE_TABLE = best["table"]
CASE_ID_COL = best["idcol"]

conn = sqlite3.connect(
    f"file:{DB}?mode=ro",
    uri=True,
)
conn.row_factory = sqlite3.Row

schema = {
    t: columns(conn, t)
    for t in tables(conn)
}

ISSUE_TABLE = related_table(
    schema,
    ["issues", "issue"],
    ["issue"],
)

PR_TABLE = related_table(
    schema,
    [
        "pull_requests",
        "pull_request",
        "prs",
        "pr",
    ],
    ["pullrequest", "prs"],
)

REPO_TABLE = related_table(
    schema,
    [
        "repositories",
        "repository",
        "repos",
        "repo",
    ],
    ["repo"],
)


def get_case(case_id):
    row = conn.execute(
        f'SELECT * FROM "{CASE_TABLE}" '
        f'WHERE CAST("{CASE_ID_COL}" AS TEXT) = ? LIMIT 1',
        (str(case_id),),
    ).fetchone()

    return dict(row) if row else {}


def resolve_related(case):
    issue_fk = first(
        case,
        [
            "issue_id",
            "github_issue_id",
            "issue_db_id",
        ],
    )

    pr_fk = first(
        case,
        [
            "pr_id",
            "pull_request_id",
            "github_pr_id",
            "pr_db_id",
        ],
    )

    repo_fk = first(
        case,
        [
            "repo_id",
            "repository_id",
            "repo_db_id",
        ],
    )

    issue = fetch_one(
        conn,
        ISSUE_TABLE,
        ["id", "issue_id", "github_issue_id"],
        issue_fk,
    ) if ISSUE_TABLE else {}

    pr = fetch_one(
        conn,
        PR_TABLE,
        [
            "id",
            "pr_id",
            "pull_request_id",
            "github_pr_id",
        ],
        pr_fk,
    ) if PR_TABLE else {}

    repo = fetch_one(
        conn,
        REPO_TABLE,
        ["id", "repo_id", "repository_id"],
        repo_fk,
    ) if REPO_TABLE else {}

    return issue, pr, repo


rows = []

for sel in selected:
    case_id = sel["case_id"].strip()
    case = get_case(case_id)

    if not case:
        rows.append({
            **sel,
            "found": "NO",
        })
        continue

    issue, pr, repo = resolve_related(case)

    repository = (
        first(
            repo,
            [
                "full_name",
                "name_with_owner",
                "repo_full_name",
                "repository",
                "name",
            ],
        )
        or first(
            case,
            [
                "repo_full_name",
                "repository",
                "repo",
                "repo_name",
            ],
        )
    )

    issue_title = (
        first(
            issue,
            ["title", "issue_title"],
        )
        or first(
            case,
            ["issue_title", "title"],
        )
    )

    issue_body = (
        first(
            issue,
            ["body", "issue_body", "description"],
        )
        or first(
            case,
            [
                "issue_body",
                "issue_description",
            ],
        )
    )

    issue_number = (
        first(
            issue,
            ["number", "issue_number"],
        )
        or first(
            case,
            ["issue_number"],
        )
    )

    issue_url = (
        first(
            issue,
            [
                "html_url",
                "issue_url",
                "url",
            ],
        )
        or first(
            case,
            ["issue_url"],
        )
    )

    pr_number = (
        first(
            pr,
            ["number", "pr_number"],
        )
        or first(
            case,
            ["pr_number"],
        )
    )

    pr_url = (
        first(
            pr,
            [
                "html_url",
                "pr_url",
                "url",
            ],
        )
        or first(
            case,
            ["pr_url"],
        )
    )

    base_commit = (
        first(
            pr,
            [
                "base_sha",
                "base_commit",
                "base_oid",
                "base_ref_oid",
                "merge_base_sha",
            ],
        )
        or first(
            case,
            [
                "base_sha",
                "base_commit",
                "base_oid",
                "base_ref_oid",
            ],
        )
    )

    head_commit = (
        first(
            pr,
            [
                "head_sha",
                "head_commit",
                "head_oid",
                "head_ref_oid",
                "merge_commit_sha",
            ],
        )
        or first(
            case,
            [
                "head_sha",
                "head_commit",
                "head_oid",
                "head_ref_oid",
            ],
        )
    )

    rows.append({
        **sel,
        "found": "YES",
        "repository": repository,
        "repository_matches_expected":
            "YES"
            if norm(repository) == norm(sel["expected_repository"])
            else "NO",
        "issue_number": issue_number,
        "issue_url": issue_url,
        "issue_title": issue_title,
        "issue_body": issue_body,
        "pr_number": pr_number,
        "pr_url": pr_url,
        "base_commit": base_commit,
        "head_commit": head_commit,
        "source_db": str(DB),
        "case_table": CASE_TABLE,
        "issue_table": ISSUE_TABLE or "",
        "pr_table": PR_TABLE or "",
        "repo_table": REPO_TABLE or "",
        "raw_case_json": json.dumps(
            case,
            ensure_ascii=False,
            default=str,
        ),
        "raw_issue_json": json.dumps(
            issue,
            ensure_ascii=False,
            default=str,
        ),
        "raw_pr_json": json.dumps(
            pr,
            ensure_ascii=False,
            default=str,
        ),
        "raw_repo_json": json.dumps(
            repo,
            ensure_ascii=False,
            default=str,
        ),
    })


conn.close()

fields = [
    "pair_id",
    "role",
    "case_id",
    "expected_repository",
    "found",
    "repository",
    "repository_matches_expected",
    "issue_number",
    "issue_url",
    "issue_title",
    "issue_body",
    "pr_number",
    "pr_url",
    "base_commit",
    "head_commit",
    "source_db",
    "case_table",
    "issue_table",
    "pr_table",
    "repo_table",
    "raw_case_json",
    "raw_issue_json",
    "raw_pr_json",
    "raw_repo_json",
]

with open(
    OUTCSV,
    "w",
    newline="",
    encoding="utf-8",
) as f:
    w = csv.DictWriter(
        f,
        fieldnames=fields,
        extrasaction="ignore",
    )
    w.writeheader()
    w.writerows(rows)

found = sum(
    r.get("found") == "YES"
    for r in rows
)

missing_text = sum(
    r.get("found") == "YES"
    and not (
        str(r.get("issue_title", "")).strip()
        or str(r.get("issue_body", "")).strip()
    )
    for r in rows
)

missing_title = sum(
    r.get("found") == "YES"
    and not str(r.get("issue_title", "")).strip()
    for r in rows
)

missing_body = sum(
    r.get("found") == "YES"
    and not str(r.get("issue_body", "")).strip()
    for r in rows
)

repo_mismatch = sum(
    r.get("found") == "YES"
    and r.get("repository_matches_expected") != "YES"
    for r in rows
)

missing_base = sum(
    r.get("found") == "YES"
    and not str(r.get("base_commit", "")).strip()
    for r in rows
)

missing_head = sum(
    r.get("found") == "YES"
    and not str(r.get("head_commit", "")).strip()
    for r in rows
)

status = (
    "PASS"
    if (
        found == 10
        and missing_text == 0
        and repo_mismatch == 0
    )
    else "CHECK_REQUIRED"
)

qc = [
    "COUNTERFACTUAL REPLAY STEP 3 CONTEXT QC",
    "=======================================",
    f"Selected cases expected: 10",
    f"Selected cases found: {found}",
    f"Selected database: {DB}",
    f"Case table: {CASE_TABLE}",
    f"Case ID column: {CASE_ID_COL}",
    "",
    f"Missing all issue text: {missing_text}",
    f"Missing issue titles: {missing_title}",
    f"Empty issue bodies: {missing_body}",
    f"Repository mismatches: {repo_mismatch}",
    f"Missing base commits: {missing_base}",
    f"Missing head commits: {missing_head}",
    "",
    f"Output: {OUTCSV}",
    f"Output SHA256: {sha256(OUTCSV)}",
    "",
    f"STEP 3 STATUS: {status}",
]

OUTQC.write_text(
    "\n".join(qc) + "\n",
    encoding="utf-8",
)

print("\n".join(qc))

print()
print("PAIR PREVIEW")
print("============")

for r in rows:
    print()
    print(
        r.get("pair_id"),
        r.get("role"),
        "case=" + r.get("case_id", ""),
    )
    print(
        "repo:",
        r.get("repository", ""),
    )
    print(
        "title:",
        str(r.get("issue_title", ""))[:250],
    )
    print(
        "base:",
        r.get("base_commit", ""),
    )
