#!/bin/bash
#SBATCH --job-name=cf_replay_s1
#SBATCH --partition=biggpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/logs/%x_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/logs/%x_%j.err

set -euo pipefail

OUT="$HOME/research_artifacts/counterfactual_replay_r1"
DB="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/data/final-study-snapshot-20260829/full3809-scanner-complete-20260829.db"

echo "============================================================"
echo "COUNTERFACTUAL REPLAY STEP 1"
echo "HOST=$(hostname)"
echo "START=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "PARTITION=biggpu"
echo "============================================================"

python3 - "$OUT" "$DB" <<'PY'
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import tarfile
import zipfile
from pathlib import Path

OUT = Path(sys.argv[1]).resolve()
DB = Path(sys.argv[2]).resolve()
HOME = Path.home()
EXPECTED_ROWS = 51
EXPECTED_D1 = 22

OUT.mkdir(parents=True, exist_ok=True)


def norm(x):
    return re.sub(r"[^a-z0-9]+", "", str(x or "").lower())


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def decode_bytes(data):
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", errors="replace")


def find_col(headers, exact=(), contains=()):
    by_norm = {norm(h): h for h in headers}

    for candidate in exact:
        c = norm(candidate)
        if c in by_norm:
            return by_norm[c]

    if contains:
        wanted = [norm(x) for x in contains]
        for h in headers:
            nh = norm(h)
            if all(x in nh for x in wanted):
                return h

    return None


def parse_csv_text(text):
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    headers = reader.fieldnames or []
    return headers, rows


def validate_step6(headers, rows):
    if not headers or not rows:
        return None

    tier_col = find_col(
        headers,
        exact=[
            "Match Tier",
            "match_tier",
            "Decision Match Tier",
            "Tier",
        ],
        contains=["tier"],
    )

    if not tier_col:
        return None

    d1_count = sum(
        1
        for r in rows
        if str(r.get(tier_col, "") or "").strip().upper() == "D1"
    )

    if len(rows) == EXPECTED_ROWS and d1_count == EXPECTED_D1:
        return {
            "tier_col": tier_col,
            "rows": rows,
            "headers": headers,
        }

    return None


def candidate_paths():
    seen = set()

    roots = [
        HOME / "research_artifacts",
        HOME,
    ]

    for root in roots:
        if not root.exists():
            continue

        for current, dirs, files in os.walk(root):
            current_p = Path(current)

            # Avoid enormous irrelevant trees during the fallback HOME scan.
            dirs[:] = [
                d for d in dirs
                if d not in {
                    ".cache",
                    ".local",
                    ".npm",
                    ".conda",
                    "__pycache__",
                    "node_modules",
                    ".git",
                    ".venv",
                    "venv",
                }
            ]

            try:
                rel_depth = len(current_p.relative_to(root).parts)
            except Exception:
                rel_depth = 0

            if root == HOME and rel_depth > 7:
                dirs[:] = []
                continue

            for fn in files:
                low = fn.lower()

                interesting = (
                    "step6" in low
                    or (
                        "decision" in low
                        and "control" in low
                    )
                    or (
                        "unblind" in low
                        and "pair" in low
                    )
                )

                if not interesting:
                    continue

                p = current_p / fn
                sp = str(p)

                if sp in seen:
                    continue

                seen.add(sp)
                yield p


search_log = []
valid_sources = []

for path in candidate_paths():
    low = path.name.lower()

    try:
        if low.endswith(".csv"):
            text = path.read_text(
                encoding="utf-8-sig",
                errors="replace",
            )
            headers, rows = parse_csv_text(text)
            result = validate_step6(headers, rows)

            search_log.append({
                "path": str(path),
                "type": "csv",
                "rows": len(rows),
                "valid": bool(result),
            })

            if result:
                valid_sources.append({
                    "display": str(path),
                    "mtime": path.stat().st_mtime,
                    "text": text,
                    "result": result,
                    "source_file": path,
                    "archive": None,
                })

        elif low.endswith((".tar.gz", ".tgz", ".tar")):
            mode = "r:*"
            with tarfile.open(path, mode) as tf:
                for member in tf.getmembers():
                    if not member.isfile():
                        continue
                    if not member.name.lower().endswith(".csv"):
                        continue

                    f = tf.extractfile(member)
                    if f is None:
                        continue

                    text = decode_bytes(f.read())
                    headers, rows = parse_csv_text(text)
                    result = validate_step6(headers, rows)

                    if result:
                        valid_sources.append({
                            "display": f"{path}::{member.name}",
                            "mtime": path.stat().st_mtime,
                            "text": text,
                            "result": result,
                            "source_file": None,
                            "archive": path,
                        })

        elif low.endswith(".zip"):
            with zipfile.ZipFile(path) as zf:
                for member in zf.namelist():
                    if not member.lower().endswith(".csv"):
                        continue

                    text = decode_bytes(zf.read(member))
                    headers, rows = parse_csv_text(text)
                    result = validate_step6(headers, rows)

                    if result:
                        valid_sources.append({
                            "display": f"{path}::{member}",
                            "mtime": path.stat().st_mtime,
                            "text": text,
                            "result": result,
                            "source_file": None,
                            "archive": path,
                        })

    except Exception as e:
        search_log.append({
            "path": str(path),
            "type": "error",
            "error": repr(e),
        })


(OUT / "STEP1_SOURCE_SEARCH.json").write_text(
    json.dumps(search_log, indent=2),
    encoding="utf-8",
)

if not valid_sources:
    raise SystemExit(
        "\nERROR: Could not locate a frozen Step-6 CSV with exactly "
        "51 rows and 22 D1 rows.\n"
        f"Search diagnostics written to:\n"
        f"{OUT / 'STEP1_SOURCE_SEARCH.json'}\n"
    )

valid_sources.sort(
    key=lambda x: x["mtime"],
    reverse=True,
)

source = valid_sources[0]
headers = source["result"]["headers"]
rows = source["result"]["rows"]
tier_col = source["result"]["tier_col"]

(OUT / "STEP6_SOURCE_SELECTED.txt").write_text(
    source["display"] + "\n",
    encoding="utf-8",
)

frozen_copy = OUT / "STEP6_UNBLINDED_PAIRS_51_FROZEN_COPY.csv"
frozen_copy.write_text(
    source["text"],
    encoding="utf-8",
)

d1 = [
    r
    for r in rows
    if str(r.get(tier_col, "") or "").strip().upper() == "D1"
]

if len(d1) != EXPECTED_D1:
    raise SystemExit(
        f"ERROR: expected {EXPECTED_D1} D1 rows, found {len(d1)}"
    )


def pick_case_col(headers, side):
    tests = []

    if side == "positive":
        tests = [
            ([
                "Positive Case ID",
                "Scanner-Producing Case ID",
                "Producing Case ID",
            ], None),
            (None, ["positive", "case"]),
            (None, ["scannerproducing", "case"]),
        ]
    else:
        tests = [
            ([
                "Control Case ID",
                "Negative Case ID",
                "Scanner-Negative Case ID",
            ], None),
            (None, ["control", "case"]),
            (None, ["negative", "case"]),
            (None, ["scannernegative", "case"]),
        ]

    for exact, contains in tests:
        if exact:
            c = find_col(headers, exact=exact)
        else:
            c = find_col(headers, contains=contains)
        if c:
            return c

    return None


pos_case_col = pick_case_col(headers, "positive")
neg_case_col = pick_case_col(headers, "negative")

if not pos_case_col or not neg_case_col:
    raise SystemExit(
        "\nERROR: Could not identify positive/control Case ID columns.\n"
        f"Positive={pos_case_col}\n"
        f"Negative={neg_case_col}\n"
        "HEADERS:\n"
        + "\n".join(headers)
    )

pair_col = find_col(
    headers,
    exact=["Pair ID", "pair_id", "Match ID"],
    contains=["pair"],
)

family_col = find_col(
    headers,
    exact=[
        "Functional Decision Family",
        "Decision Family",
        "functional_family",
    ],
    contains=["family"],
)

root_col = find_col(
    headers,
    exact=[
        "Positive Root ID",
        "Root ID",
        "root_id",
    ],
    contains=["root"],
)

if not DB.exists():
    raise SystemExit(f"ERROR: frozen DB not found: {DB}")


conn = sqlite3.connect(
    f"file:{DB}?mode=ro",
    uri=True,
)
conn.row_factory = sqlite3.Row


def table_names():
    return [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    ]


TABLES = table_names()


def columns(table):
    return [
        r[1]
        for r in conn.execute(
            f'PRAGMA table_info("{table}")'
        )
    ]


SCHEMA = {
    table: columns(table)
    for table in TABLES
}


def choose_table(preferred, required=()):
    for name in preferred:
        if name in SCHEMA:
            return name

    wanted = [norm(x) for x in required]

    for table, cols in SCHEMA.items():
        ncols = [norm(c) for c in cols]
        if wanted and all(
            any(w in c for c in ncols)
            for w in wanted
        ):
            return table

    return None


def choose_col(cols, aliases):
    nmap = {norm(c): c for c in cols}

    for alias in aliases:
        if norm(alias) in nmap:
            return nmap[norm(alias)]

    return None


def first_value(d, aliases):
    if not d:
        return ""

    nmap = {
        norm(k): k
        for k in d.keys()
    }

    for alias in aliases:
        k = nmap.get(norm(alias))
        if k is None:
            continue

        v = d.get(k)
        if v not in (None, ""):
            return str(v)

    return ""


def fetch_by_id(table, id_value, aliases):
    if not table or id_value in ("", None):
        return {}

    id_col = choose_col(
        SCHEMA[table],
        aliases,
    )

    if not id_col:
        return {}

    vals = [id_value]

    try:
        vals.append(int(id_value))
    except Exception:
        pass

    for v in vals:
        try:
            row = conn.execute(
                f'SELECT * FROM "{table}" '
                f'WHERE "{id_col}" = ? LIMIT 1',
                (v,),
            ).fetchone()

            if row:
                return dict(row)
        except Exception:
            pass

    return {}


CASE_TABLE = choose_table(
    ["cases", "case"],
    ["case"],
)

ISSUE_TABLE = choose_table(
    ["issues", "issue"],
    ["issue"],
)

PR_TABLE = choose_table(
    ["pull_requests", "prs", "pull_request"],
    ["pr"],
)

REPO_TABLE = choose_table(
    ["repos", "repositories", "repo"],
    ["repo"],
)


def context_for_case(case_id):
    if not CASE_TABLE:
        return {}

    crow = fetch_by_id(
        CASE_TABLE,
        case_id,
        ["case_id", "id"],
    )

    if not crow:
        return {}

    issue_fk = first_value(
        crow,
        ["issue_id", "github_issue_id"],
    )

    pr_fk = first_value(
        crow,
        [
            "pr_id",
            "pull_request_id",
            "github_pr_id",
        ],
    )

    repo_fk = first_value(
        crow,
        ["repo_id", "repository_id"],
    )

    irow = fetch_by_id(
        ISSUE_TABLE,
        issue_fk,
        ["id", "issue_id"],
    ) if ISSUE_TABLE else {}

    prow = fetch_by_id(
        PR_TABLE,
        pr_fk,
        [
            "id",
            "pr_id",
            "pull_request_id",
        ],
    ) if PR_TABLE else {}

    rrow = fetch_by_id(
        REPO_TABLE,
        repo_fk,
        [
            "id",
            "repo_id",
            "repository_id",
        ],
    ) if REPO_TABLE else {}

    repo = (
        first_value(
            rrow,
            [
                "full_name",
                "name_with_owner",
                "repo_full_name",
                "repository",
            ],
        )
        or first_value(
            crow,
            [
                "repo_full_name",
                "repository",
                "repo_name",
            ],
        )
    )

    issue_title = (
        first_value(
            irow,
            ["title", "issue_title"],
        )
        or first_value(
            crow,
            ["issue_title"],
        )
    )

    issue_body = (
        first_value(
            irow,
            ["body", "issue_body"],
        )
        or first_value(
            crow,
            ["issue_body"],
        )
    )

    issue_number = (
        first_value(
            irow,
            ["number", "issue_number"],
        )
        or first_value(
            crow,
            ["issue_number"],
        )
    )

    issue_url = (
        first_value(
            irow,
            ["html_url", "url", "issue_url"],
        )
        or first_value(
            crow,
            ["issue_url"],
        )
    )

    pr_number = (
        first_value(
            prow,
            ["number", "pr_number"],
        )
        or first_value(
            crow,
            ["pr_number"],
        )
    )

    pr_url = (
        first_value(
            prow,
            ["html_url", "url", "pr_url"],
        )
        or first_value(
            crow,
            ["pr_url"],
        )
    )

    base_commit = (
        first_value(
            prow,
            [
                "base_sha",
                "base_commit",
                "base_oid",
                "base_ref_oid",
                "merge_base_sha",
            ],
        )
        or first_value(
            crow,
            [
                "base_sha",
                "base_commit",
                "base_oid",
            ],
        )
    )

    head_commit = (
        first_value(
            prow,
            [
                "head_sha",
                "head_commit",
                "head_oid",
                "head_ref_oid",
            ],
        )
        or first_value(
            crow,
            [
                "head_sha",
                "head_commit",
                "head_oid",
            ],
        )
    )

    return {
        "repository": repo,
        "issue_number": issue_number,
        "issue_url": issue_url,
        "issue_title": issue_title,
        "issue_body": issue_body,
        "pr_number": pr_number,
        "pr_url": pr_url,
        "base_commit": base_commit,
        "head_commit": head_commit,
    }


def source_value(row, prefixes, concepts):
    for h in headers:
        nh = norm(h)

        if not any(
            norm(p) in nh
            for p in prefixes
        ):
            continue

        if all(
            norm(c) in nh
            for c in concepts
        ):
            value = str(
                row.get(h, "") or ""
            ).strip()

            if value:
                return value

    return ""


out_rows = []

for i, row in enumerate(d1, 1):
    pos_id = str(
        row.get(pos_case_col, "") or ""
    ).strip()

    neg_id = str(
        row.get(neg_case_col, "") or ""
    ).strip()

    p = context_for_case(pos_id)
    n = context_for_case(neg_id)

    pair_id = (
        str(row.get(pair_col, "") or "").strip()
        if pair_col
        else f"D1_{i:02d}"
    )

    decision_family = (
        str(row.get(family_col, "") or "").strip()
        if family_col
        else ""
    )

    positive_root = (
        str(row.get(root_col, "") or "").strip()
        if root_col
        else ""
    )

    def get_side(side, concepts, fallback):
        if side == "positive":
            prefixes = [
                "positive",
                "scannerproducing",
                "producing",
            ]
        else:
            prefixes = [
                "control",
                "negative",
                "scannernegative",
            ]

        return (
            source_value(
                row,
                prefixes,
                concepts,
            )
            or fallback
            or ""
        )

    out = {
        "pair_id": pair_id,
        "match_tier": "D1",
        "decision_family": decision_family,
        "positive_root_id": positive_root,

        "positive_case_id": pos_id,
        "positive_repository": get_side(
            "positive",
            ["repository"],
            p.get("repository", ""),
        ),
        "positive_issue_number": get_side(
            "positive",
            ["issue", "number"],
            p.get("issue_number", ""),
        ),
        "positive_issue_url": get_side(
            "positive",
            ["issue", "url"],
            p.get("issue_url", ""),
        ),
        "positive_issue_title": get_side(
            "positive",
            ["issue", "title"],
            p.get("issue_title", ""),
        ),
        "positive_issue_body": get_side(
            "positive",
            ["issue", "body"],
            p.get("issue_body", ""),
        ),
        "positive_pr_number": get_side(
            "positive",
            ["pr", "number"],
            p.get("pr_number", ""),
        ),
        "positive_pr_url": get_side(
            "positive",
            ["pr", "url"],
            p.get("pr_url", ""),
        ),
        "positive_base_commit": get_side(
            "positive",
            ["base", "commit"],
            p.get("base_commit", ""),
        ),
        "positive_head_commit": get_side(
            "positive",
            ["head", "commit"],
            p.get("head_commit", ""),
        ),

        "negative_case_id": neg_id,
        "negative_repository": get_side(
            "negative",
            ["repository"],
            n.get("repository", ""),
        ),
        "negative_issue_number": get_side(
            "negative",
            ["issue", "number"],
            n.get("issue_number", ""),
        ),
        "negative_issue_url": get_side(
            "negative",
            ["issue", "url"],
            n.get("issue_url", ""),
        ),
        "negative_issue_title": get_side(
            "negative",
            ["issue", "title"],
            n.get("issue_title", ""),
        ),
        "negative_issue_body": get_side(
            "negative",
            ["issue", "body"],
            n.get("issue_body", ""),
        ),
        "negative_pr_number": get_side(
            "negative",
            ["pr", "number"],
            n.get("pr_number", ""),
        ),
        "negative_pr_url": get_side(
            "negative",
            ["pr", "url"],
            n.get("pr_url", ""),
        ),
        "negative_base_commit": get_side(
            "negative",
            ["base", "commit"],
            n.get("base_commit", ""),
        ),
        "negative_head_commit": get_side(
            "negative",
            ["head", "commit"],
            n.get("head_commit", ""),
        ),
    }

    # Preserve every frozen Step-6 field.
    for h in headers:
        out[f"step6__{h}"] = str(
            row.get(h, "") or ""
        )

    out_rows.append(out)


conn.close()

standard = [
    "pair_id",
    "match_tier",
    "decision_family",
    "positive_root_id",

    "positive_case_id",
    "positive_repository",
    "positive_issue_number",
    "positive_issue_url",
    "positive_issue_title",
    "positive_issue_body",
    "positive_pr_number",
    "positive_pr_url",
    "positive_base_commit",
    "positive_head_commit",

    "negative_case_id",
    "negative_repository",
    "negative_issue_number",
    "negative_issue_url",
    "negative_issue_title",
    "negative_issue_body",
    "negative_pr_number",
    "negative_pr_url",
    "negative_base_commit",
    "negative_head_commit",
]

extra = sorted(
    set().union(
        *(r.keys() for r in out_rows)
    ) - set(standard)
)

out_csv = OUT / "replay_candidates_D1_22.csv"

with open(
    out_csv,
    "w",
    newline="",
    encoding="utf-8",
) as f:
    writer = csv.DictWriter(
        f,
        fieldnames=standard + extra,
        extrasaction="ignore",
    )
    writer.writeheader()
    writer.writerows(out_rows)


missing_pos_text = sum(
    1
    for r in out_rows
    if not (
        r["positive_issue_title"].strip()
        or r["positive_issue_body"].strip()
    )
)

missing_neg_text = sum(
    1
    for r in out_rows
    if not (
        r["negative_issue_title"].strip()
        or r["negative_issue_body"].strip()
    )
)

repo_mismatches = [
    (
        r["pair_id"],
        r["positive_repository"],
        r["negative_repository"],
    )
    for r in out_rows
    if (
        r["positive_repository"].strip()
        and r["negative_repository"].strip()
        and (
            r["positive_repository"].strip()
            != r["negative_repository"].strip()
        )
    )
]

missing_pos_base = sum(
    1
    for r in out_rows
    if not r["positive_base_commit"].strip()
)

missing_neg_base = sum(
    1
    for r in out_rows
    if not r["negative_base_commit"].strip()
)

duplicate_pair_ids = (
    len(out_rows)
    - len({
        r["pair_id"]
        for r in out_rows
    })
)

status = "PASS"

if (
    len(out_rows) != EXPECTED_D1
    or missing_pos_text
    or missing_neg_text
    or repo_mismatches
    or duplicate_pair_ids
):
    status = "CHECK_REQUIRED"

qc = OUT / "STEP1_QC.txt"

qc.write_text(
    "\n".join([
        "COUNTERFACTUAL REPLAY STEP 1 QC",
        "================================",
        f"Host: {os.uname().nodename}",
        f"Selected Step-6 source: {source['display']}",
        f"Frozen Step-6 copy SHA256: {sha256_file(frozen_copy)}",
        f"Frozen DB: {DB}",
        "",
        f"Frozen Step-6 rows: {len(rows)}",
        f"D1 rows extracted: {len(out_rows)}",
        f"Expected D1 rows: {EXPECTED_D1}",
        f"Missing positive issue text: {missing_pos_text}",
        f"Missing negative issue text: {missing_neg_text}",
        f"Same-repository mismatches: {len(repo_mismatches)}",
        f"Missing positive base commits: {missing_pos_base}",
        f"Missing negative base commits: {missing_neg_base}",
        f"Duplicate pair IDs: {duplicate_pair_ids}",
        "",
        "Repository mismatches:",
        json.dumps(
            repo_mismatches,
            indent=2,
        ),
        "",
        f"Output CSV: {out_csv}",
        f"Output SHA256: {sha256_file(out_csv)}",
        "",
        f"STEP 1 STATUS: {status}",
    ]) + "\n",
    encoding="utf-8",
)

print(qc.read_text())

if status != "PASS":
    raise SystemExit(3)

PY

echo
echo "============================================================"
echo "OUTPUT FILES"
echo "============================================================"

ls -lh \
  "$OUT/replay_candidates_D1_22.csv" \
  "$OUT/STEP1_QC.txt" \
  "$OUT/STEP6_SOURCE_SELECTED.txt" \
  "$OUT/STEP6_UNBLINDED_PAIRS_51_FROZEN_COPY.csv"

echo
echo "============================================================"
echo "FINISHED"
echo "END=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "============================================================"
