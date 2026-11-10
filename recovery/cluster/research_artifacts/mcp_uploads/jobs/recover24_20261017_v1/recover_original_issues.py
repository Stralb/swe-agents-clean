#!/usr/bin/env python3
"""Researcher-only recovery of 24 frozen historical issue records. Input DBs are immutable."""
import csv
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home-mscluster/astrauss/research_artifacts")
QUEUE = ROOT / "prevention_pilot_phase2/case_screen_results_v1/RESEARCHER_SCREEN_QUEUE.csv"
DB_DIR = Path("/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/data")
DATABASES = [
    "miner.agentic-js.eval.20260720_224159.db",
    "miner.agentic-js.eval.20260720_224159.full3809-continuation.db",
]
RUN = Path(__file__).resolve().parent
RESULTS = RUN / "results"

SQL = """
SELECT c.id AS db_case_id, c.repo_id, c.issue_id, c.pr_id,
       i.number AS db_issue_number, i.url AS db_issue_url,
       i.title AS original_issue_title, i.body AS original_issue_body,
       i.author AS issue_author, i.state AS issue_state,
       i.labels AS issue_labels, i.created_at AS issue_created_at,
       i.updated_at AS issue_updated_at, i.closed_at AS issue_closed_at,
       p.number AS db_pr_number, p.url AS db_pr_url,
       p.title AS historical_pr_title, p.created_at AS pr_created_at,
       p.merged_at AS pr_merged_at, p.base_sha AS recorded_pr_base_sha,
       p.head_sha AS historical_pr_head_sha
FROM cases AS c
JOIN issues AS i ON i.id = c.issue_id
JOIN pull_requests AS p ON p.id = c.pr_id
WHERE c.id = ?
"""

def connect_readonly(name):
    path = DB_DIR / name
    if not path.is_file():
        return None
    conn = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn

def timestamp(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None

def source_matches(row, queue):
    def normal(x):
        return str(x or "").rstrip("/").lower()
    return (
        int(row["db_case_id"]) == int(queue["case_id"])
        and int(row["db_issue_number"]) == int(queue["issue_number"])
        and int(row["db_pr_number"]) == int(queue["pr_number"])
        and normal(row["db_issue_url"]) == normal(queue["issue_url"])
        and normal(row["db_pr_url"]) == normal(queue["pr_url"])
    )

def main():
    if not QUEUE.is_file():
        raise RuntimeError("Frozen queue is missing")
    with QUEUE.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 24:
        raise RuntimeError(f"Frozen queue contains {len(rows)} rows, expected exactly 24")
    ranks = [int(q["queue_rank"]) for q in rows]
    if ranks != list(range(1, 25)) or len({q["root_id"] for q in rows}) != 24:
        raise RuntimeError("Frozen queue rank/root IDs are inconsistent")

    connections = {}
    for name in DATABASES:
        connections[name] = connect_readonly(name)
    if not any(connections.values()):
        raise RuntimeError("No permitted historical source database is available")
    try:
        records = []
        for q in rows:
            case_id = int(q["case_id"])
            candidates = []
            chosen = None
            chosen_database = None
            for dbname, conn in connections.items():
                if conn is None:
                    continue
                fetched = conn.execute(SQL, (case_id,)).fetchone()
                if fetched is None:
                    continue
                candidate = dict(fetched)
                candidates.append({"database": dbname, "strict_match": source_matches(candidate, q)})
                if source_matches(candidate, q):
                    chosen, chosen_database = candidate, dbname
                    break
            record = {
                "queue_rank": int(q["queue_rank"]),
                "root_id": q["root_id"],
                "case_id": case_id,
                "repository": q["repository"],
                "queue_issue_number": int(q["issue_number"]),
                "queue_pr_number": int(q["pr_number"]),
                "queue_issue_url": q["issue_url"],
                "queue_pr_url": q["pr_url"],
                "target_rule": q["target_rule"],
                "historical_finding_id": q.get("historical_finding_id", ""),
                "record_status": "MATCHED" if chosen else ("MISMATCH" if candidates else "NOT_FOUND"),
                "source_database": chosen_database,
                "candidate_matches": candidates,
                "historical_source": chosen,
            }
            if chosen:
                issue_created = timestamp(chosen["issue_created_at"])
                issue_updated = timestamp(chosen["issue_updated_at"])
                pr_created = timestamp(chosen["pr_created_at"])
                record.update({
                    "issue_body_present": bool((chosen["original_issue_body"] or "").strip()),
                    "issue_before_pr": (issue_created <= pr_created if issue_created and pr_created else None),
                    "issue_updated_after_pr": (issue_updated > pr_created if issue_updated and pr_created else None),
                    "recorded_pr_base_sha_present": bool(chosen["recorded_pr_base_sha"]),
                    "pre_pr_archive_verified": False,
                    "original_issue_body_is_proven_historical_version": False,
                })
            records.append(record)

        # One newly created output directory, exclusive-create files, no modification of prior work.
        RESULTS.mkdir(exist_ok=False)
        with (RESULTS / "original_issue_records_24.jsonl").open("x", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        fields = ["queue_rank", "root_id", "case_id", "repository", "record_status",
                  "source_database", "issue_body_present", "issue_before_pr",
                  "issue_updated_after_pr", "recorded_pr_base_sha_present",
                  "pre_pr_archive_verified"]
        with (RESULTS / "recovery_manifest_24.csv").open("x", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for record in records:
                writer.writerow({name: record.get(name) for name in fields})
        summary = {
            "run_type": "24-case researcher-only issue-body recovery",
            "run_utc": datetime.now(timezone.utc).isoformat(),
            "queue": str(QUEUE),
            "queue_sha256": hashlib.sha256(QUEUE.read_bytes()).hexdigest(),
            "database_access": "SQLite immutable read-only, query_only=ON",
            "databases": [{"name": name, "exists": connections[name] is not None}
                          for name in DATABASES],
            "total": len(records),
            "matched": sum(x["record_status"] == "MATCHED" for x in records),
            "mismatch": sum(x["record_status"] == "MISMATCH" for x in records),
            "not_found": sum(x["record_status"] == "NOT_FOUND" for x in records),
            "issue_bodies_present": sum(x.get("issue_body_present") is True for x in records),
            "issue_updated_after_pr": sum(x.get("issue_updated_after_pr") is True for x in records),
            "limitations": [
                "Stored issue body may reflect subsequent edits; original issue text at PR time is not independently established.",
                "PR base_sha metadata alone does not prove checkout of frozen pre-PR code.",
                "No historical CodeQL controls or fresh patches were executed."
            ],
        }
        with (RESULTS / "recovery_summary.json").open("x", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    finally:
        for conn in connections.values():
            if conn is not None:
                conn.close()

if __name__ == "__main__":
    main()
