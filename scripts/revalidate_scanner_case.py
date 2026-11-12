from __future__ import annotations

import argparse
import copy
import csv
import json
import os
import sqlite3
import traceback
from pathlib import Path

import yaml

from src.db.database import Database
from src.scanners.scanner_runner import scan_case


# Directory holding the historical database, audit CSV and config used for
# the scanner revalidation. Defaults to the repository root.
ROOT = Path(
    os.getenv("MINER_ROOT", str(Path(__file__).resolve().parents[1]))
)

SOURCE_DB = (
    ROOT
    / "data"
    / "miner.agentic-js.eval.20260720_224159.hf-snapshot-20260817.db"
)

AUDIT_CSV = (
    ROOT
    / "data"
    / "scanner_provenance_audit_138"
    / "case_provenance_audit.csv"
)

CONFIG_PATH = ROOT / "config.agentic_js.yml"

OUT_ROOT = ROOT / "data" / "scanner_revalidation_17"
RESULT_DIR = OUT_ROOT / "results"
WORK_DIR = OUT_ROOT / "work"

CODEQL_CASES = {
    290,
    291,
    299,
    649,
    3882,
    4621,
    5355,
    8461,
    9992,
    10361,
    15151,
    15739,
    16203,
}

DEPENDENCY_CASES = {
    59,
    8038,
    8162,
    10825,
}

EXPECTED_CASES = CODEQL_CASES | DEPENDENCY_CASES


def read_true_merge_base(case_id: int) -> str:
    with AUDIT_CSV.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        for row in reader:
            if int(row["case_id"]) != case_id:
                continue

            merge_base = str(
                row.get("true_merge_base")
                or ""
            ).strip()

            if not merge_base:
                raise RuntimeError(
                    f"Case {case_id}: true_merge_base is missing"
                )

            return merge_base

    raise RuntimeError(
        f"Case {case_id} not found in {AUDIT_CSV}"
    )


def create_validation_db(
    path: Path,
    case_id: int,
    pr_id: int,
    files: list[sqlite3.Row],
) -> None:
    if path.exists():
        path.unlink()

    conn = sqlite3.connect(path)

    conn.executescript(
        """
        CREATE TABLE cases (
            id INTEGER PRIMARY KEY,
            status TEXT,
            updated_at TEXT
        );

        CREATE TABLE pr_files (
            id INTEGER PRIMARY KEY,
            pr_id INTEGER NOT NULL,
            filename TEXT,
            status TEXT,
            additions INTEGER,
            deletions INTEGER,
            patch TEXT,
            category TEXT
        );

        CREATE TABLE scanner_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER,
            pr_id INTEGER,
            scanner TEXT,
            status TEXT,
            started_at TEXT,
            finished_at TEXT,
            stdout TEXT,
            stderr TEXT
        );

        CREATE TABLE scanner_findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER,
            pr_id INTEGER,
            scanner TEXT,
            finding_type TEXT,
            severity TEXT,
            rule_id TEXT,
            cwe TEXT,
            file_path TEXT,
            line INTEGER,
            description TEXT,
            evidence TEXT,
            raw_json TEXT,
            introduced INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    conn.execute(
        """
        INSERT INTO cases(
            id,
            status,
            updated_at
        )
        VALUES (?, 'scanner_pending', CURRENT_TIMESTAMP)
        """,
        (case_id,),
    )

    for row in files:
        conn.execute(
            """
            INSERT INTO pr_files(
                id,
                pr_id,
                filename,
                status,
                additions,
                deletions,
                patch,
                category
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                pr_id,
                row["filename"],
                row["status"],
                row["additions"],
                row["deletions"],
                row["patch"],
                row["category"],
            ),
        )

    conn.commit()
    conn.close()


def finding_row(row: sqlite3.Row | dict) -> dict:
    return {
        "scanner": row["scanner"],
        "finding_type": row["finding_type"],
        "severity": row["severity"],
        "rule_id": row["rule_id"],
        "cwe": row["cwe"],
        "file_path": row["file_path"],
        "line": row["line"],
        "description": row["description"],
        "evidence": row["evidence"],
        "introduced": int(
            row["introduced"]
            if row["introduced"] is not None
            else 1
        ),
    }


def finding_signature(row: dict) -> tuple:
    return (
        str(row.get("scanner") or ""),
        str(row.get("finding_type") or ""),
        str(row.get("rule_id") or ""),
        str(row.get("cwe") or ""),
        str(row.get("file_path") or ""),
        row.get("line"),
        str(row.get("description") or ""),
    )


def make_config(
    case_id: int,
) -> dict:
    with CONFIG_PATH.open(
        "r",
        encoding="utf-8",
    ) as handle:
        config = yaml.safe_load(handle) or {}

    config = copy.deepcopy(config)

    scanners = config.setdefault(
        "scanners",
        {},
    )

    scanners["gitleaks"] = False
    scanners["dependency_downgrade"] = False
    scanners["osv"] = False
    scanners["trivy"] = False
    scanners["semgrep"] = False
    scanners["codeql"] = False

    if case_id in CODEQL_CASES:
        scanners["codeql"] = True
        scanners["codeql_timeout_seconds"] = 7200

    elif case_id in DEPENDENCY_CASES:
        scanners["osv"] = True
        scanners["trivy"] = True

    else:
        raise RuntimeError(
            f"Unexpected case id: {case_id}"
        )

    config.setdefault(
        "cache",
        {},
    )["force_rescan"] = True

    return config


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--case-id",
        type=int,
        required=True,
    )

    args = parser.parse_args()

    case_id = args.case_id

    if case_id not in EXPECTED_CASES:
        raise RuntimeError(
            f"Case {case_id} is not one of the 17 expected cases"
        )

    RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    WORK_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    result_path = (
        RESULT_DIR
        / f"case_{case_id}.json"
    )

    validation_db_path = (
        WORK_DIR
        / f"case_{case_id}.db"
    )

    result = {
        "case_id": case_id,
        "validation_type": (
            "codeql"
            if case_id in CODEQL_CASES
            else "dependency"
        ),
        "status": "RUNNING",
        "error": None,
    }

    try:
        source = sqlite3.connect(
            f"file:{SOURCE_DB.resolve()}?mode=ro",
            uri=True,
        )

        source.row_factory = sqlite3.Row

        case = source.execute(
            """
            SELECT
                c.id AS case_id,
                c.pr_id AS pr_id,
                r.full_name AS repo_full_name,
                r.html_url AS repo_url,
                p.number AS pr_number,
                p.base_sha AS original_base_sha,
                p.head_sha AS head_sha
            FROM cases c
            JOIN repos r
              ON r.id = c.repo_id
            JOIN pull_requests p
              ON p.id = c.pr_id
            WHERE c.id = ?
            """,
            (case_id,),
        ).fetchone()

        if case is None:
            raise RuntimeError(
                f"Case {case_id} not found"
            )

        pr_id = int(
            case["pr_id"]
        )

        files = source.execute(
            """
            SELECT
                id,
                pr_id,
                filename,
                status,
                additions,
                deletions,
                patch,
                category
            FROM pr_files
            WHERE pr_id = ?
            ORDER BY id
            """,
            (pr_id,),
        ).fetchall()

        if case_id in CODEQL_CASES:
            old_scanners = (
                "codeql",
            )
        else:
            old_scanners = (
                "osv-scanner",
                "trivy-scanner",
            )

        placeholders = ",".join(
            "?"
            for _ in old_scanners
        )

        old_rows = source.execute(
            f"""
            SELECT
                scanner,
                finding_type,
                severity,
                rule_id,
                cwe,
                file_path,
                line,
                description,
                evidence,
                introduced
            FROM scanner_findings
            WHERE case_id = ?
              AND introduced = 1
              AND scanner IN ({placeholders})
            ORDER BY
                scanner,
                rule_id,
                file_path,
                line,
                id
            """,
            (
                case_id,
                *old_scanners,
            ),
        ).fetchall()

        old_findings = [
            finding_row(row)
            for row in old_rows
        ]

        source.close()

        true_merge_base = read_true_merge_base(
            case_id
        )

        create_validation_db(
            validation_db_path,
            case_id,
            pr_id,
            files,
        )

        validation_db = Database(
            validation_db_path
        )

        scan_case(
            validation_db,
            {
                "case_id": case_id,
                "pr_id": pr_id,
                "repo_url": case["repo_url"],
                "base_sha": true_merge_base,
                "head_sha": case["head_sha"],
            },
            make_config(case_id),
        )

        validation = sqlite3.connect(
            validation_db_path
        )

        validation.row_factory = sqlite3.Row

        if case_id in CODEQL_CASES:
            new_scanners = (
                "codeql",
            )
        else:
            new_scanners = (
                "osv-scanner",
                "trivy-scanner",
            )

        placeholders = ",".join(
            "?"
            for _ in new_scanners
        )

        new_rows = validation.execute(
            f"""
            SELECT
                scanner,
                finding_type,
                severity,
                rule_id,
                cwe,
                file_path,
                line,
                description,
                evidence,
                introduced
            FROM scanner_findings
            WHERE case_id = ?
              AND introduced = 1
              AND scanner IN ({placeholders})
            ORDER BY
                scanner,
                rule_id,
                file_path,
                line,
                id
            """,
            (
                case_id,
                *new_scanners,
            ),
        ).fetchall()

        new_findings = [
            finding_row(row)
            for row in new_rows
        ]

        run_rows = validation.execute(
            """
            SELECT
                scanner,
                status,
                stdout,
                stderr
            FROM scanner_runs
            WHERE case_id = ?
            ORDER BY id
            """,
            (case_id,),
        ).fetchall()

        runs = [
            {
                "scanner": row["scanner"],
                "status": row["status"],
                "stdout_tail": (
                    str(row["stdout"] or "")[-2000:]
                ),
                "stderr_tail": (
                    str(row["stderr"] or "")[-2000:]
                ),
            }
            for row in run_rows
        ]

        validation.close()

        if case_id in CODEQL_CASES:
            required_run_names = {
                "codeql",
            }
        else:
            old_present = {
                row["scanner"]
                for row in old_findings
            }

            required_run_names = (
                old_present
                & {
                    "osv-scanner",
                    "trivy-scanner",
                }
            )

        aggregate_status = {
            row["scanner"]: row["status"]
            for row in runs
            if row["scanner"]
            in {
                "codeql",
                "osv-scanner",
                "trivy-scanner",
            }
        }

        failed_required_runs = {
            name: aggregate_status.get(name)
            for name in required_run_names
            if aggregate_status.get(name) != "ok"
        }

        old_signatures = {
            finding_signature(row)
            for row in old_findings
        }

        new_signatures = {
            finding_signature(row)
            for row in new_findings
        }

        if failed_required_runs:
            verdict = "SCAN_ERROR"

        elif not new_findings:
            verdict = "NO_LONGER_POSITIVE"

        elif old_signatures == new_signatures:
            verdict = "CONFIRMED_UNCHANGED"

        else:
            verdict = "CONFIRMED_CHANGED"

        old_only_signatures = sorted(
            repr(item)
            for item in (
                old_signatures
                - new_signatures
            )
        )

        new_only_signatures = sorted(
            repr(item)
            for item in (
                new_signatures
                - old_signatures
            )
        )

        result.update(
            {
                "status": "COMPLETE",
                "verdict": verdict,
                "repo_full_name": case[
                    "repo_full_name"
                ],
                "pr_number": int(
                    case["pr_number"]
                ),
                "pr_id": pr_id,
                "original_base_sha": case[
                    "original_base_sha"
                ],
                "true_merge_base": true_merge_base,
                "head_sha": case[
                    "head_sha"
                ],
                "original_base_equals_merge_base": (
                    case["original_base_sha"]
                    == true_merge_base
                ),
                "old_finding_count": len(
                    old_findings
                ),
                "new_finding_count": len(
                    new_findings
                ),
                "old_findings": old_findings,
                "new_findings": new_findings,
                "old_only_signatures":
                    old_only_signatures,
                "new_only_signatures":
                    new_only_signatures,
                "scanner_runs": runs,
                "failed_required_runs":
                    failed_required_runs,
            }
        )

    except Exception as exc:
        result.update(
            {
                "status": "ERROR",
                "verdict": "SCAN_ERROR",
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        )

    result_path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "case_id": result.get(
                    "case_id"
                ),
                "status": result.get(
                    "status"
                ),
                "verdict": result.get(
                    "verdict"
                ),
                "old": result.get(
                    "old_finding_count"
                ),
                "new": result.get(
                    "new_finding_count"
                ),
                "error": result.get(
                    "error"
                ),
            },
            indent=2,
        ),
        flush=True,
    )

    if result["status"] == "ERROR":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
