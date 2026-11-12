from pathlib import Path

from src.db.database import Database
from src.pipeline.case_builder import update_case_tags_and_status
from src.workers.job_queue import seed_scanner_jobs, sync_jobs_from_scanner_runs, update_case_stages


def init_db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "miner.db")
    db.init_schema(Path("src/db/schema.sql"))
    return db


def make_case(db: Database, files: list[dict]) -> int:
    repo_id = db.insert_or_get_repo({"full_name": "owner/repo", "html_url": "https://github.com/owner/repo", "stargazers_count": 500, "language": "Python", "archived": False})
    issue_id = db.upsert_issue(repo_id, {"id": 1, "number": 1, "html_url": "https://github.com/owner/repo/issues/1", "title": "Bug", "body": "Steps to reproduce " * 10, "user": {"login": "alice"}, "state": "closed", "labels": [], "comments": 0}, 30, True)
    pr_id = db.upsert_pr(repo_id, {"number": 2, "html_url": "https://github.com/owner/repo/pull/2", "title": "Fix", "body": "", "user": {"login": "bob"}, "state": "closed", "merged": True, "merged_at": "2026-01-01T00:00:00Z", "head": {"ref": "fix", "sha": "h"}, "base": {"ref": "main", "sha": "b"}})
    db.replace_pr_files(pr_id, files)
    db.link_issue_pr(issue_id, pr_id, "closingIssuesReferences")
    return db.create_or_get_case(repo_id, issue_id, pr_id, "AI-unknown", ["AI-unknown"])


def test_direct_fast_scan_does_not_mark_python_case_clean_before_codeql(tmp_path):
    db = init_db(tmp_path)
    case_id = make_case(db, [{"filename": "src/app.py", "patch": "+print(1)"}])
    pr_id = db.one("SELECT pr_id FROM cases WHERE id=?", (case_id,))["pr_id"]
    for scanner in ["gitleaks", "dependency-diff", "osv-scanner"]:
        db.execute("INSERT INTO scanner_runs(case_id, pr_id, scanner, status) VALUES (?, ?, ?, 'ok')", (case_id, pr_id, scanner))
    update_case_tags_and_status(db)
    assert db.one("SELECT status FROM cases WHERE id=?", (case_id,))["status"] == "scanner_running"


def test_direct_full_scan_syncs_jobs_and_marks_clean(tmp_path):
    db = init_db(tmp_path)
    case_id = make_case(db, [{"filename": "src/app.py", "patch": "+print(1)"}])
    seed_scanner_jobs(db, include_codeql=True, case_ids=[case_id])
    pr_id = db.one("SELECT pr_id FROM cases WHERE id=?", (case_id,))["pr_id"]
    for scanner in ["gitleaks", "dependency-diff", "osv-scanner", "semgrep", "trivy-scanner", "codeql-base", "codeql-head", "codeql"]:
        db.execute("INSERT INTO scanner_runs(case_id, pr_id, scanner, status) VALUES (?, ?, ?, 'ok')", (case_id, pr_id, scanner))
    sync_jobs_from_scanner_runs(db, case_id)
    update_case_stages(db)
    assert db.one("SELECT status FROM cases WHERE id=?", (case_id,))["status"] == "scanned_clean"
    statuses = {r["job_type"]: r["status"] for r in db.query("SELECT job_type, status FROM scanner_jobs WHERE case_id=?", (case_id,))}
    assert statuses["codeql"] == "ok"
    assert statuses["secret_ci"] == "ok"
