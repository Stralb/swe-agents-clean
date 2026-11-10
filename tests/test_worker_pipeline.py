from __future__ import annotations

from pathlib import Path

from src.db.database import Database
from src.github.rate_limit import RateLimitManager
from src.workers.job_queue import applicable_job_types, claim_job, finish_job, seed_scanner_jobs, update_case_stages


def init_db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "miner.db")
    db.init_schema(Path("src/db/schema.sql"))
    return db


def make_case(db: Database, files: list[dict]) -> int:
    repo_id = db.insert_or_get_repo({"full_name": "owner/repo", "html_url": "https://github.com/owner/repo", "stargazers_count": 100, "language": "Python", "archived": False})
    issue_id = db.upsert_issue(repo_id, {"id": 1, "number": 1, "html_url": "https://github.com/owner/repo/issues/1", "title": "Bug", "body": "Steps to reproduce with enough words " * 5, "user": {"login": "alice"}, "state": "closed", "labels": [], "comments": 0}, 60, True)
    pr_id = db.upsert_pr(repo_id, {"number": 2, "html_url": "https://github.com/owner/repo/pull/2", "title": "Fix", "body": "", "user": {"login": "bob"}, "state": "closed", "merged": True, "merged_at": "2026-01-01T00:00:00Z", "head": {"ref": "fix", "sha": "h"}, "base": {"ref": "main", "sha": "b"}})
    db.replace_pr_files(pr_id, files)
    db.link_issue_pr(issue_id, pr_id, "body")
    return db.create_or_get_case(repo_id, issue_id, pr_id, "AI-unknown", ["AI-unknown"])


def test_applicable_job_types_are_required_downstream_workers():
    files = [{"filename": "README.md"}]
    expected = ["semgrep_source", "secret_ci", "dependency_downgrade", "osv_dependency", "trivy_dependency", "codeql"]
    assert applicable_job_types(files) == expected
    assert applicable_job_types(files, include_codeql=False) == expected[:-1]


def test_seed_jobs_records_worker_route_reasons(tmp_path):
    db = init_db(tmp_path)
    case_id = make_case(db, [{"filename": "requirements.txt", "patch": "+idna==3.9"}])
    created = seed_scanner_jobs(db, include_codeql=True)
    assert created == 6
    rows = db.query("SELECT job_type, route_reason FROM scanner_jobs WHERE case_id=? ORDER BY job_type", (case_id,))
    reasons = {r["job_type"]: r["route_reason"] for r in rows}
    assert "dependency_config" in reasons["dependency_downgrade"]
    assert "dependency_config" in reasons["osv_dependency"]
    assert "dependency_config" in reasons["trivy_dependency"]
    assert "ci/secret/unknown/patch" in reasons["secret_ci"]
    assert reasons["codeql"] == "not_applicable:no_source_code_region"
    assert reasons["semgrep_source"] == "scheduled by downstream methodology"


def test_seed_and_claim_new_dependency_worker(tmp_path):
    db = init_db(tmp_path)
    case_id = make_case(db, [{"filename": "requirements.txt", "patch": "+idna==3.9"}])
    created = seed_scanner_jobs(db, include_codeql=True)
    assert created == 6
    job = claim_job(db, ["dependency_downgrade"], worker_id="dep-1")
    assert job is not None
    assert job.case_id == case_id
    assert job.job_type == "dependency_downgrade"
    row = db.one("SELECT status, worker_id FROM scanner_jobs WHERE id=?", (job.id,))
    assert row["status"] == "running"
    assert row["worker_id"] == "dep-1"


def test_incomplete_scanner_opportunity_is_not_clean(tmp_path):
    db = init_db(tmp_path)
    case_id = make_case(db, [{"filename": "requirements.txt", "patch": "+idna==3.9"}])
    seed_scanner_jobs(db, include_codeql=True)
    update_case_stages(db)
    assert db.one("SELECT status FROM cases WHERE id=?", (case_id,))["status"] == "scanner_running"
    for group, worker in (
        (["dependency_downgrade"], "dep-1"),
        (["osv_dependency"], "osv-1"),
        (["trivy_dependency"], "trivy-1"),
        (["semgrep_source"], "semgrep-1"),
        (["secret_ci"], "secret-1"),
    ):
        job = claim_job(db, group, worker_id=worker)
        assert job is not None
        finish_job(db, job.id, "ok")
    update_case_stages(db)
    assert db.one("SELECT status FROM cases WHERE id=?", (case_id,))["status"] == "scanner_running"
    job = claim_job(db, ["codeql"], worker_id="codeql-1")
    assert job is not None
    finish_job(db, job.id, "not_applicable", "no Python files changed")
    update_case_stages(db)
    row = db.one("SELECT status, downstream_signal FROM cases WHERE id=?", (case_id,))
    assert row["status"] == "scan_blocked"
    assert row["downstream_signal"] == "not_applicable"


def test_all_successful_scanner_jobs_mark_case_clean(tmp_path):
    db = init_db(tmp_path)
    case_id = make_case(db, [{"filename": "requirements.txt", "patch": "+idna==3.9"}])
    assert seed_scanner_jobs(db, include_codeql=True) == 6

    for worker_type in applicable_job_types([]):
        job = claim_job(db, [worker_type], worker_id=worker_type)
        assert job is not None
        finish_job(db, job.id, "ok")

    update_case_stages(db)
    row = db.one("SELECT status, downstream_signal FROM cases WHERE id=?", (case_id,))
    assert row["status"] == "scanned_clean"
    assert row["downstream_signal"] == "no_introduced_finding"


def test_rate_limit_manager_sleeps_when_below_reserve(tmp_path, monkeypatch):
    db = init_db(tmp_path)
    sleeps: list[int] = []
    monkeypatch.setattr("src.github.rate_limit.cooperative_sleep", lambda seconds: sleeps.append(int(seconds)))
    monkeypatch.setattr("time.time", lambda: 1000)
    mgr = RateLimitManager(db.path, min_remaining=100)
    mgr.update_from_headers({"X-RateLimit-Remaining": "50", "X-RateLimit-Limit": "5000", "X-RateLimit-Reset": "1030", "X-RateLimit-Resource": "core"})
    assert mgr.seconds_until_safe() == 32
    mgr.wait_if_needed()
    assert sleeps == [32]


def test_search_bucket_uses_small_reserve_and_does_not_block_core(tmp_path, monkeypatch):
    db = init_db(tmp_path)
    monkeypatch.setattr("time.time", lambda: 1000)
    mgr = RateLimitManager(db.path, min_remaining=100, search_min_remaining=2)
    mgr.update_from_headers({"X-RateLimit-Remaining": "30", "X-RateLimit-Limit": "30", "X-RateLimit-Reset": "1060", "X-RateLimit-Resource": "search"})
    mgr.update_from_headers({"X-RateLimit-Remaining": "4985", "X-RateLimit-Limit": "5000", "X-RateLimit-Reset": "4600", "X-RateLimit-Resource": "core"})
    assert mgr.seconds_until_safe("core") == 0
    assert mgr.seconds_until_safe("search") == 0


def test_search_bucket_waits_only_when_near_search_reserve(tmp_path, monkeypatch):
    db = init_db(tmp_path)
    monkeypatch.setattr("time.time", lambda: 1000)
    mgr = RateLimitManager(db.path, min_remaining=100, search_min_remaining=2)
    mgr.update_from_headers({"X-RateLimit-Remaining": "1", "X-RateLimit-Limit": "30", "X-RateLimit-Reset": "1030", "X-RateLimit-Resource": "search"})
    mgr.update_from_headers({"X-RateLimit-Remaining": "4985", "X-RateLimit-Limit": "5000", "X-RateLimit-Reset": "4600", "X-RateLimit-Resource": "core"})
    assert mgr.seconds_until_safe("core") == 0
    assert mgr.seconds_until_safe("search") == 32


def test_reset_running_jobs_on_evaluate_restart(tmp_path):
    from src.workers.job_queue import reset_running_jobs_on_start
    db = init_db(tmp_path)
    case_id = make_case(db, [{"filename": "README.md", "patch": "+x"}])
    seed_scanner_jobs(db, include_codeql=True)
    job = claim_job(db, ["codeql"], worker_id="old-codeql")
    assert job is not None
    assert db.one("SELECT status FROM scanner_jobs WHERE id=?", (job.id,))["status"] == "running"
    changed = reset_running_jobs_on_start(db, job_types=["codeql"])
    assert changed == 1
    row = db.one("SELECT status, worker_id, started_at FROM scanner_jobs WHERE id=?", (job.id,))
    assert row["status"] == "pending"
    assert row["worker_id"] is None
    assert row["started_at"] is None
