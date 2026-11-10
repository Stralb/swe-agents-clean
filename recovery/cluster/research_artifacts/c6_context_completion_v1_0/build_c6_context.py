from __future__ import annotations

import csv
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


HOME = Path.home()

REPO = HOME / "new/malicious-issue-miner-rate-smart"

DB_CANDIDATES = [
    REPO / "data/final-study-snapshot-20260829/full3809-scanner-complete-20260829.db",
    REPO / "data/miner.agentic-js.eval.20260720_224159.full3809-continuation.db",
]

C2_CANDIDATES = [
    HOME / "research_artifacts/matched_control_c2_v1_0/C2_MATCHED_PAIRS_FROZEN.csv",
    HOME / "research_artifacts/matched_control_c2_v1_0/C2_MATCHED_PAIRS_FROZEN.csv",
]

OUT = HOME / "research_artifacts/c6_context_completion_v1_0"
OUT.mkdir(parents=True, exist_ok=True)


def choose_existing(candidates, label):
    for p in candidates:
        if p.exists():
            print(f"{label}={p}")
            return p
    raise RuntimeError(
        f"Could not find {label}. Checked: "
        + ", ".join(str(x) for x in candidates)
    )


def iso_dt(value):
    if value in (None, ""):
        return None
    try:
        d = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except Exception:
        return None


def gh(args, retries=4):
    cmd = ["gh"] + list(args)

    last_error = ""

    for attempt in range(retries):
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        if p.returncode == 0:
            return p.stdout, ""

        last_error = p.stderr.decode(
            "utf-8",
            errors="replace",
        ).strip()

        wait = 3 + attempt * 5

        if (
            "rate limit" in last_error.lower()
            or "secondary rate" in last_error.lower()
            or p.returncode != 0
        ):
            time.sleep(wait)

    return b"", last_error


def gh_json(args):
    raw, err = gh(args)

    if not raw:
        return None, err

    try:
        return json.loads(
            raw.decode("utf-8", errors="replace")
        ), err
    except Exception as e:
        return None, f"{err}; JSON decode: {e}".strip("; ")


def gh_paginated(endpoint):
    all_rows = []
    page = 1

    while True:
        sep = "&" if "?" in endpoint else "?"
        obj, err = gh_json([
            "api",
            f"{endpoint}{sep}per_page=100&page={page}",
        ])

        if obj is None:
            return None, err

        if not isinstance(obj, list):
            return None, "Expected list response"

        all_rows.extend(obj)

        if len(obj) < 100:
            return all_rows, ""

        page += 1


def write_csv(path, rows):
    rows = list(rows)

    fields = []
    seen = set()

    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)

    with path.open(
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


DB = choose_existing(DB_CANDIDATES, "DB")
C2 = choose_existing(C2_CANDIDATES, "C2")

import sqlite3

pairs = list(
    csv.DictReader(
        C2.open(encoding="utf-8-sig")
    )
)

if len(pairs) != 190:
    raise RuntimeError(
        f"Expected 190 C2 pairs, got {len(pairs)}"
    )

control_ids = []

for r in pairs:
    value = (
        r.get("control_case_id")
        or r.get("Control Case ID")
        or r.get("control_id")
    )
    if value in (None, ""):
        raise RuntimeError(
            "Could not identify control case ID column"
        )
    control_ids.append(int(value))

if len(set(control_ids)) != 190:
    raise RuntimeError(
        "Control IDs are not 190 unique IDs"
    )

marks = ",".join("?" for _ in control_ids)

con = sqlite3.connect(
    f"file:{DB}?mode=ro",
    uri=True,
    timeout=120,
)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")

base = [
    dict(r)
    for r in con.execute(
        f"""
        SELECT
            c.id AS case_id,
            r.full_name AS repository,

            i.number AS issue_number,
            i.author AS issue_author,
            i.created_at AS issue_created_at,

            p.number AS pr_number,
            p.author AS pr_author,
            p.created_at AS pr_created_at,
            p.merged_at AS pr_merged_at

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
        control_ids,
    )
]

con.close()

if len(base) != 190:
    raise RuntimeError(
        f"Expected 190 DB control rows, got {len(base)}"
    )


# ---------------------------------------------------------
# Frozen context definitions
# ---------------------------------------------------------
#
# Account age:
# issue_created_at - public account created_at
#
# Association:
# GitHub issue author_association
#
# Prior repo interactions:
# repository issues + PRs by the same issue author
# strictly before issue_created_at
#
# Human review:
# >=1 submitted review at/before merge
# from a non-bot actor other than the PR author
#
# Same author:
# case-insensitive issue-author == PR-author
#
# ---------------------------------------------------------

user_cache = {}
output = []
review_audit = []

for idx, row in enumerate(base, start=1):
    case_id = row["case_id"]
    repo = row["repository"]
    issue_number = row["issue_number"]
    pr_number = row["pr_number"]
    issue_author = row["issue_author"] or ""
    pr_author = row["pr_author"] or ""

    issue_created = iso_dt(
        row["issue_created_at"]
    )
    pr_created = iso_dt(
        row["pr_created_at"]
    )
    merged_at = iso_dt(
        row["pr_merged_at"]
    )

    errors = []

    print(
        f"[{idx:03d}/190] "
        f"case={case_id} "
        f"{repo} "
        f"issue={issue_number} "
        f"pr={pr_number}",
        flush=True,
    )

    # -----------------------------
    # Account creation / account age
    # -----------------------------
    user_created_raw = ""

    if issue_author:
        if issue_author not in user_cache:
            obj, err = gh_json([
                "api",
                f"users/{issue_author}",
            ])

            if isinstance(obj, dict):
                user_cache[issue_author] = {
                    "created_at":
                        obj.get("created_at") or "",
                    "error": err or "",
                }
            else:
                user_cache[issue_author] = {
                    "created_at": "",
                    "error": err or "User lookup failed",
                }

        user_created_raw = (
            user_cache[issue_author]["created_at"]
        )

        if user_cache[issue_author]["error"]:
            errors.append(
                "user:"
                + user_cache[issue_author]["error"]
            )

    account_age_days = ""

    user_created_dt = iso_dt(user_created_raw)

    if user_created_dt and issue_created:
        account_age_days = round(
            (
                issue_created - user_created_dt
            ).total_seconds() / 86400,
            3,
        )

    # -----------------------------
    # Issue author association
    # -----------------------------
    association = ""

    issue_obj, issue_err = gh_json([
        "api",
        f"repos/{repo}/issues/{issue_number}",
    ])

    if isinstance(issue_obj, dict):
        association = (
            issue_obj.get("author_association")
            or ""
        )
    elif issue_err:
        errors.append(
            "issue_association:" + issue_err
        )

    # -----------------------------
    # Prior same-repo issues + PRs
    # -----------------------------
    prior_count = ""

    if issue_author and row["issue_created_at"]:
        query = (
            f"repo:{repo} "
            f"author:{issue_author} "
            f"created:<{row['issue_created_at']}"
        )

        prior_obj, prior_err = gh_json([
            "api",
            "-X",
            "GET",
            "search/issues",
            "-f",
            f"q={query}",
            "-f",
            "per_page=1",
        ])

        if isinstance(prior_obj, dict):
            prior_count = (
                prior_obj.get("total_count", "")
            )
        elif prior_err:
            errors.append(
                "prior_history:" + prior_err
            )

        # Search API has its own tighter rate limit.
        time.sleep(2.2)

    # -----------------------------
    # Formal reviews
    # -----------------------------
    reviews, review_err = gh_paginated(
        f"repos/{repo}/pulls/{pr_number}/reviews"
    )

    if reviews is None:
        reviews = []
        if review_err:
            errors.append(
                "reviews:" + review_err
            )

    qualifying = 0

    for rv in reviews:
        user = rv.get("user") or {}
        reviewer = str(
            user.get("login") or ""
        )
        reviewer_type = str(
            user.get("type") or ""
        )

        submitted = iso_dt(
            rv.get("submitted_at")
        )

        before_merge = bool(
            submitted is not None
            and merged_at is not None
            and submitted <= merged_at
        )

        is_bot = bool(
            reviewer_type.lower() == "bot"
            or reviewer.lower().endswith("[bot]")
        )

        is_self = bool(
            reviewer
            and pr_author
            and reviewer.lower()
            == pr_author.lower()
        )

        qualifies = bool(
            before_merge
            and not is_bot
            and not is_self
        )

        if qualifies:
            qualifying += 1

        review_audit.append({
            "case_id": case_id,
            "repository": repo,
            "pr_number": pr_number,
            "pr_author": pr_author,
            "review_id": rv.get("id"),
            "reviewer_login": reviewer,
            "reviewer_type": reviewer_type,
            "state": rv.get("state"),
            "submitted_at": rv.get("submitted_at"),
            "before_merge": int(before_merge),
            "is_bot": int(is_bot),
            "is_self_review": int(is_self),
            "qualifies_frozen_definition":
                int(qualifies),
        })

    same_author = int(
        bool(
            issue_author
            and pr_author
            and issue_author.lower()
            == pr_author.lower()
        )
    )

    issue_to_pr_hours = ""

    if issue_created and pr_created:
        issue_to_pr_hours = round(
            (
                pr_created - issue_created
            ).total_seconds() / 3600,
            3,
        )

    pr_to_merge_hours = ""

    if pr_created and merged_at:
        pr_to_merge_hours = round(
            (
                merged_at - pr_created
            ).total_seconds() / 3600,
            3,
        )

    output.append({
        "control_case_id": case_id,
        "repository": repo,
        "issue_number": issue_number,
        "issue_author": issue_author,
        "pr_number": pr_number,
        "pr_author": pr_author,
        "issue_created_at":
            row["issue_created_at"],
        "pr_created_at":
            row["pr_created_at"],
        "pr_merged_at":
            row["pr_merged_at"],
        "issue_author_account_created_utc":
            user_created_raw,
        "account_age_at_issue_days":
            account_age_days,
        "issue_author_association":
            association,
        "prior_repo_issues_prs_before_issue":
            prior_count,
        "same_issue_pr_author":
            same_author,
        "issue_to_pr_creation_delay_hours":
            issue_to_pr_hours,
        "pr_time_to_merge_hours":
            pr_to_merge_hours,
        "qualifying_human_review_count_before_merge":
            qualifying,
        "human_review_present_before_merge":
            "Yes" if qualifying > 0 else "No",
        "context_errors_json":
            json.dumps(
                errors,
                ensure_ascii=False,
            ),
    })


write_csv(
    OUT / "C6_CONTROL_CONTEXT_190.csv",
    output,
)

write_csv(
    OUT / "C6_CONTROL_REVIEW_AUDIT.csv",
    review_audit,
)

missing_age = sum(
    r["account_age_at_issue_days"] == ""
    for r in output
)
missing_assoc = sum(
    r["issue_author_association"] == ""
    for r in output
)
missing_prior = sum(
    r["prior_repo_issues_prs_before_issue"] == ""
    for r in output
)

qc = {
    "controls": len(output),
    "unique_control_case_ids":
        len({r["control_case_id"] for r in output}),
    "missing_account_age": missing_age,
    "missing_association": missing_assoc,
    "missing_prior_repo_activity": missing_prior,
    "review_rows": len(review_audit),
    "human_review_resolved":
        sum(
            r["human_review_present_before_merge"]
            in ("Yes", "No")
            for r in output
        ),
    "semantic_labels_changed": False,
    "scanner_results_used": False,
}

(OUT / "C6_CONTEXT_QC.json").write_text(
    json.dumps(
        qc,
        indent=2,
        ensure_ascii=False,
    )
    + "\n",
    encoding="utf-8",
)

print()
print(json.dumps(qc, indent=2))
print()
print("C6_CONTROL_CONTEXT_STATUS="
      + (
          "PASS"
          if (
              len(output) == 190
              and len(
                  {
                      r["control_case_id"]
                      for r in output
                  }
              ) == 190
              and sum(
                  r[
                      "human_review_present_before_merge"
                  ]
                  in ("Yes", "No")
                  for r in output
              ) == 190
          )
          else "NEEDS_QC"
      ))
