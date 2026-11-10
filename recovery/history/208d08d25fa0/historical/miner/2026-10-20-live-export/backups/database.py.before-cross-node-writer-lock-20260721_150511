from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar

T = TypeVar("T")


class Database:
    """Small SQLite wrapper tuned for long-running collector/scanner/UI workflows.

    SQLite is fine for this project, but the collector, scanner, and Streamlit UI can
    briefly overlap. WAL mode + busy timeouts + small retry loop prevent transient
    `database is locked` crashes.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        last_exc = None

        for attempt in range(20):
            try:
                path = Path(self.path).expanduser()
                path.parent.mkdir(parents=True, exist_ok=True)

                conn = sqlite3.connect(str(path), timeout=120.0, check_same_thread=False)
                conn.row_factory = sqlite3.Row

                # Do NOT set journal_mode here. Evaluator opens many connections;
                # changing journal mode repeatedly causes open/I/O failures.
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute("PRAGMA busy_timeout = 120000")
                return conn

            except sqlite3.OperationalError as exc:
                last_exc = exc
                msg = str(exc).lower()

                if (
                    "unable to open database file" not in msg
                    and "disk i/o error" not in msg
                    and "locking protocol" not in msg
                    and "database is locked" not in msg
                ):
                    raise

                sleep_s = min(60, 2 ** min(attempt, 6))
                print(f"[sqlite-connect-retry] attempt={attempt+1}/20 error={exc} sleep={sleep_s}s path={self.path}", flush=True)
                time.sleep(sleep_s)

        raise last_exc


    def _retry(self, fn: Callable[[], T], attempts: int = 5, base_sleep: float = 0.25) -> T:
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                return fn()
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower():
                    raise
                last_exc = exc
                time.sleep(base_sleep * (2 ** attempt))
        raise last_exc or RuntimeError("SQLite operation failed")

    def init_schema(self, schema_path: str | Path) -> None:
        def op() -> None:
            with self.connect() as conn, open(schema_path, "r", encoding="utf-8") as f:
                conn.executescript(f.read())
        self._retry(op)
        self.apply_migrations()
        self.seed_default_tags()

    def apply_migrations(self) -> None:
        """Apply small additive schema migrations for existing SQLite DBs."""
        def add_column_if_missing(table: str, column: str, ddl: str) -> None:
            with self.connect() as conn:
                cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
                if column not in cols:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")

        def op() -> None:
            add_column_if_missing("retrieval_queries", "raw_count", "raw_count INTEGER DEFAULT 0")
            add_column_if_missing("retrieval_queries", "unique_count", "unique_count INTEGER DEFAULT 0")
            add_column_if_missing("retrieval_queries", "eligible_count", "eligible_count INTEGER DEFAULT 0")
            add_column_if_missing("retrieval_queries", "candidate_count", "candidate_count INTEGER DEFAULT 0")
            add_column_if_missing("retrieval_queries", "duplicate_count", "duplicate_count INTEGER DEFAULT 0")
            add_column_if_missing("retrieval_queries", "repo_filter_count", "repo_filter_count INTEGER DEFAULT 0")
            add_column_if_missing("retrieval_queries", "processed_count", "processed_count INTEGER DEFAULT 0")
            add_column_if_missing("retrieval_queries", "excluded_count", "excluded_count INTEGER DEFAULT 0")
            add_column_if_missing("retrieval_queries", "search_window_count", "search_window_count INTEGER DEFAULT 0")
            add_column_if_missing("retrieval_queries", "split_window_count", "split_window_count INTEGER DEFAULT 0")
            add_column_if_missing("retrieval_queries", "probe_count", "probe_count INTEGER DEFAULT 0")
            add_column_if_missing("retrieval_queries", "reported_total_count", "reported_total_count INTEGER DEFAULT 0")
            add_column_if_missing("retrieval_queries", "next_page", "next_page INTEGER DEFAULT 1")
            add_column_if_missing("retrieval_queries", "exhausted", "exhausted INTEGER DEFAULT 0")
            add_column_if_missing("retrieval_queries", "last_error", "last_error TEXT")
            add_column_if_missing("scanner_jobs", "route_reason", "route_reason TEXT")
            add_column_if_missing("artifact_regions", "mapping_version", "mapping_version TEXT NOT NULL DEFAULT '1.0'")
            add_column_if_missing("pr_region_profiles", "mapping_version", "mapping_version TEXT NOT NULL DEFAULT '1.0'")
            # Repair DBs produced by the broken pagination build. Those rows have
            # recorded results but still claim the next page is 1, which causes
            # the miner to revisit the first page forever. Move them to page 2 so
            # the next pass resumes instead of repeating page 1.
            with self.connect() as conn:
                conn.execute(
                    """
                    UPDATE retrieval_queries
                    SET next_page=2,
                        status=CASE WHEN status IN ('pending','running','ok') THEN 'ok' ELSE status END,
                        last_error=COALESCE(last_error,'') || CASE WHEN COALESCE(last_error,'')='' THEN '' ELSE '\n' END || 'auto_repaired_stuck_page_1'
                    WHERE COALESCE(raw_count,0) > 0
                      AND COALESCE(next_page,1) <= 1
                      AND COALESCE(exhausted,0) = 0
                    """
                )
                # Backfill missing scanner jobs for existing DBs. Missing jobs
                # kept valid cases stuck or let old builds misrepresent clean.
                for job_type in ("secret_ci", "dependency_downgrade", "osv_dependency", "trivy_dependency", "codeql"):
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO scanner_jobs(case_id, job_type, status, priority, attempts, created_at)
                        SELECT c.id, ?, 'pending', 0, 0, CURRENT_TIMESTAMP
                        FROM cases c
                        WHERE c.status NOT IN ('reviewed','excluded')
                        """,
                        (job_type,),
                    )
                conn.execute(
                    """
                    UPDATE cases
                    SET status='scanner_running', updated_at=CURRENT_TIMESTAMP
                    WHERE status NOT IN ('reviewed','excluded','error','needs_review')
                      AND EXISTS (SELECT 1 FROM scanner_jobs sj WHERE sj.case_id=cases.id AND sj.status IN ('pending','retry','running'))
                    """
                )
                # Reset legacy retrieval rows that have old raw/unique counts but
                # no accounting columns populated. These rows came from builds
                # that could not explain where raw hits went. Replaying them with
                # the current accounting code is safer than presenting impossible
                # raw_total >> processed_total totals.
                conn.execute(
                    """
                    UPDATE retrieval_queries
                    SET raw_count=0,
                        unique_count=0,
                        eligible_count=0,
                        candidate_count=0,
                        duplicate_count=0,
                        repo_filter_count=0,
                        processed_count=0,
                        excluded_count=0,
                        next_page=1,
                        exhausted=0,
                        status='pending',
                        last_error=COALESCE(last_error,'') || CASE WHEN COALESCE(last_error,'')='' THEN '' ELSE '\n' END || 'reset_legacy_unaccounted_retrieval_for_replay'
                    WHERE COALESCE(raw_count,0) > 0
                      AND COALESCE(processed_count,0)=0
                      AND COALESCE(duplicate_count,0)=0
                      AND COALESCE(repo_filter_count,0)=0
                      AND COALESCE(excluded_count,0)=0
                      AND COALESCE(candidate_count,0)=0
                    """
                )
                # Wide-first v2 changed repo caps from hard early drops to
                # softer/high defaults. Rows exhausted mainly by repo caps should
                # be replayed so existing DBs are not stuck with zero valid cases.
                conn.execute(
                    """
                    UPDATE retrieval_queries
                    SET raw_count=0,
                        unique_count=0,
                        eligible_count=0,
                        candidate_count=0,
                        duplicate_count=0,
                        repo_filter_count=0,
                        processed_count=0,
                        excluded_count=0,
                        next_page=1,
                        exhausted=0,
                        status='pending',
                        last_error=COALESCE(last_error,'') || CASE WHEN COALESCE(last_error,'')='' THEN '' ELSE '\n' END || 'reset_after_wide_first_v2_cap_policy'
                    WHERE COALESCE(candidate_count,0)=0
                      AND (COALESCE(repo_filter_count,0)>0 OR final_query LIKE '%stars:>=100%' OR final_query LIKE '%stars:>=200%')
                    """
                )

                # Normalize old scanner wording. New code writes not_applicable;
                # old rows should not keep displaying as skipped.
                conn.execute("UPDATE scanner_runs SET status='not_applicable' WHERE status='skipped'")
                conn.execute("UPDATE scanner_jobs SET status='not_applicable' WHERE status='skipped'")
                conn.execute("DELETE FROM scanner_jobs WHERE job_type IN ('source_code','dependency')")

                # Artifact-region methodology tables. Kept here as additive
                # migrations so existing cluster DBs can be upgraded in-place.
                conn.executescript("""
                CREATE TABLE IF NOT EXISTS artifact_regions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id INTEGER NOT NULL,
                    pr_id INTEGER NOT NULL,
                    pr_file_id INTEGER,
                    path TEXT NOT NULL,
                    region TEXT NOT NULL,
                    language TEXT,
                    generated INTEGER DEFAULT 0,
                    vendor INTEGER DEFAULT 0,
                    scanner_routes TEXT,
                    confidence TEXT,
                    evidence TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_artifact_regions_case ON artifact_regions(case_id);
                CREATE INDEX IF NOT EXISTS idx_artifact_regions_region ON artifact_regions(region);
                CREATE TABLE IF NOT EXISTS pr_region_profiles (
                    case_id INTEGER PRIMARY KEY,
                    pr_id INTEGER NOT NULL,
                    primary_region TEXT NOT NULL,
                    region_counts_json TEXT NOT NULL,
                    scanner_routes_json TEXT NOT NULL,
                    language_json TEXT,
                    file_count INTEGER DEFAULT 0,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_pr_region_profiles_region ON pr_region_profiles(primary_region);
                """)
        self._retry(op)

    def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        def op() -> None:
            conn = self.connect()
            try:
                with conn:
                    conn.execute(sql, tuple(params))
            finally:
                conn.close()
        self._retry(op)

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        def op() -> list[dict[str, Any]]:
            conn = self.connect()
            try:
                with conn:
                    rows = conn.execute(sql, tuple(params)).fetchall()
                    return [dict(r) for r in rows]
            finally:
                conn.close()
        return self._retry(op)

    def one(self, sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def insert_or_get_repo(self, repo: dict[str, Any]) -> int:
        def op() -> int:
            with self.connect() as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO repos(full_name, html_url, stars, language, archived)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (repo["full_name"], repo.get("html_url"), repo.get("stargazers_count", 0), repo.get("language"), int(repo.get("archived", False))),
                )
                row = conn.execute("SELECT id FROM repos WHERE full_name=?", (repo["full_name"],)).fetchone()
                return int(row["id"])
        return self._retry(op)

    def upsert_issue(self, repo_id: int, issue: dict[str, Any], wc: int, is_english: bool) -> int:
        labels = json.dumps([l.get("name") if isinstance(l, dict) else str(l) for l in issue.get("labels", [])])

        def op() -> int:
            with self.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO issues(repo_id, github_id, number, url, title, body, author, state, labels, comments_count, created_at, updated_at, closed_at, word_count, is_english)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(repo_id, number) DO UPDATE SET
                        title=excluded.title, body=excluded.body, state=excluded.state, labels=excluded.labels,
                        comments_count=excluded.comments_count, updated_at=excluded.updated_at, closed_at=excluded.closed_at,
                        word_count=excluded.word_count, is_english=excluded.is_english
                    """,
                    (
                        repo_id,
                        issue.get("id"),
                        issue.get("number"),
                        issue.get("html_url"),
                        issue.get("title"),
                        issue.get("body") or "",
                        (issue.get("user") or {}).get("login"),
                        issue.get("state"),
                        labels,
                        issue.get("comments", 0),
                        issue.get("created_at"),
                        issue.get("updated_at"),
                        issue.get("closed_at"),
                        wc,
                        int(is_english),
                    ),
                )
                row = conn.execute("SELECT id FROM issues WHERE repo_id=? AND number=?", (repo_id, issue.get("number"))).fetchone()
                return int(row["id"])
        return self._retry(op)

    def upsert_pr(self, repo_id: int, pr: dict[str, Any]) -> int:
        def op() -> int:
            with self.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO pull_requests(repo_id, number, url, title, body, author, state, merged, head_ref, base_ref, head_sha, base_sha,
                        additions, deletions, changed_files_count, commits_count, review_comments_count, created_at, updated_at, closed_at, merged_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(repo_id, number) DO UPDATE SET
                        title=excluded.title, body=excluded.body, state=excluded.state, merged=excluded.merged,
                        head_ref=excluded.head_ref, base_ref=excluded.base_ref, head_sha=excluded.head_sha, base_sha=excluded.base_sha,
                        additions=excluded.additions, deletions=excluded.deletions, changed_files_count=excluded.changed_files_count,
                        commits_count=excluded.commits_count, review_comments_count=excluded.review_comments_count,
                        updated_at=excluded.updated_at, closed_at=excluded.closed_at, merged_at=excluded.merged_at
                    """,
                    (
                        repo_id,
                        pr.get("number"),
                        pr.get("html_url"),
                        pr.get("title"),
                        pr.get("body") or "",
                        (pr.get("user") or {}).get("login"),
                        pr.get("state"),
                        int(pr.get("merged_at") is not None or pr.get("merged", False)),
                        (pr.get("head") or {}).get("ref"),
                        (pr.get("base") or {}).get("ref"),
                        (pr.get("head") or {}).get("sha"),
                        (pr.get("base") or {}).get("sha"),
                        pr.get("additions", 0),
                        pr.get("deletions", 0),
                        pr.get("changed_files", 0),
                        pr.get("commits", 0),
                        pr.get("review_comments", 0),
                        pr.get("created_at"),
                        pr.get("updated_at"),
                        pr.get("closed_at"),
                        pr.get("merged_at"),
                    ),
                )
                row = conn.execute("SELECT id FROM pull_requests WHERE repo_id=? AND number=?", (repo_id, pr.get("number"))).fetchone()
                return int(row["id"])
        return self._retry(op)

    def replace_pr_files(self, pr_id: int, files: list[dict[str, Any]]) -> None:
        def op() -> None:
            with self.connect() as conn:
                conn.execute("DELETE FROM pr_files WHERE pr_id=?", (pr_id,))
                for f in files:
                    conn.execute(
                        "INSERT INTO pr_files(pr_id, filename, status, additions, deletions, patch, category) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (pr_id, f.get("filename"), f.get("status"), f.get("additions", 0), f.get("deletions", 0), f.get("patch"), f.get("category")),
                    )
        self._retry(op)

    def link_issue_pr(self, issue_id: int, pr_id: int, method: str) -> None:
        self.execute("INSERT OR IGNORE INTO issue_pr_links(issue_id, pr_id, method) VALUES (?, ?, ?)", (issue_id, pr_id, method))

    def create_or_get_case(self, repo_id: int, issue_id: int, pr_id: int, ai_cohort: str, auto_tags: list[str]) -> int:
        def op() -> int:
            with self.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO cases(repo_id, issue_id, pr_id, ai_cohort, auto_tags, status)
                    VALUES (?, ?, ?, ?, ?, 'metadata_collected')
                    ON CONFLICT(issue_id, pr_id) DO UPDATE SET ai_cohort=excluded.ai_cohort, auto_tags=excluded.auto_tags, updated_at=CURRENT_TIMESTAMP
                    """,
                    (repo_id, issue_id, pr_id, ai_cohort, json.dumps(auto_tags)),
                )
                row = conn.execute("SELECT id FROM cases WHERE issue_id=? AND pr_id=?", (issue_id, pr_id)).fetchone()
                return int(row["id"])
        return self._retry(op)


    def log_excluded_case(self, repo: str, issue_number: int | None, pr_number: int | None, reason: str, details: str = "", changed_files: list[dict[str, Any]] | None = None) -> None:
        payload = json.dumps(changed_files or [])
        self.execute(
            "INSERT INTO excluded_cases(repo, issue_number, pr_number, reason, details, changed_files_json) VALUES (?, ?, ?, ?, ?, ?)",
            (repo, issue_number, pr_number, reason, details[:2000], payload[:10000]),
        )

    def seed_default_tags(self) -> None:
        defaults = [
            "Issue has suggested fix",
            "Issue has code/reproduction artifact",
            "Issue mentions file/function",
            "Issue mentions dependency/version",
            "Issue mentions CI/secrets",
            "Possible steering",
            "Strong steering",
            "Looks benign",
            "Likely incompetence",
            "Suspicious mismatch",
            "Needs second review",
            "Exclude from dataset",
        ]

        def op() -> None:
            with self.connect() as conn:
                for name in defaults:
                    conn.execute("INSERT OR IGNORE INTO tags(name, type) VALUES (?, 'manual')", (name,))
        self._retry(op)
