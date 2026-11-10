from pathlib import Path

from src.db.database import Database
from src.pipeline.case_status import sync_case_statuses


def _db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "miner.db")
    db.init_schema(Path("src/db/schema.sql"))
    return db


def _seed_case(db: Database, case_id: int = 1) -> None:
    with db.connect() as con:
        con.execute("INSERT INTO repos(id, full_name, html_url) VALUES (1, 'o/r', 'https://github.com/o/r')")
        con.execute("INSERT INTO issues(id, repo_id, number, url) VALUES (1, 1, 1, 'https://github.com/o/r/issues/1')")
        con.execute("INSERT INTO pull_requests(id, repo_id, number, url) VALUES (1, 1, 2, 'https://github.com/o/r/pull/2')")
        con.execute("INSERT INTO cases(id, repo_id, issue_id, pr_id, status) VALUES (?, 1, 1, 1, 'scanner_running')", (case_id,))


def test_completed_jobs_no_findings_become_scanned_clean(tmp_path):
    db = _db(tmp_path)
    _seed_case(db)
    for jt, st in [("secret_ci", "ok"), ("dependency_downgrade", "done"), ("osv_dependency", "done"), ("codeql", "ok")]:
        db.execute("INSERT INTO scanner_jobs(case_id, job_type, status) VALUES (1, ?, ?)", (jt, st))
    sync_case_statuses(db)
    row = db.one("SELECT status, downstream_signal FROM cases WHERE id=1")
    assert row == {"status": "scanned_clean", "downstream_signal": "no_introduced_finding"}


def test_introduced_finding_takes_precedence_over_not_applicable(tmp_path):
    db = _db(tmp_path)
    _seed_case(db)
    for jt, st in [("secret_ci", "ok"), ("dependency_downgrade", "done"), ("osv_dependency", "done"), ("codeql", "not_applicable")]:
        db.execute("INSERT INTO scanner_jobs(case_id, job_type, status) VALUES (1, ?, ?)", (jt, st))
    db.execute("INSERT INTO scanner_findings(case_id, pr_id, scanner, finding_type, introduced) VALUES (1, 1, 'codeql', 'vulnerability', 1)")
    sync_case_statuses(db)
    row = db.one("SELECT status, downstream_signal FROM cases WHERE id=1")
    assert row == {"status": "needs_review", "downstream_signal": "vulnerability"}
