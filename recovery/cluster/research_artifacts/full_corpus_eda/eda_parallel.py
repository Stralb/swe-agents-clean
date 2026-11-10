from __future__ import annotations

import csv
import sqlite3
import statistics
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


EXPECTED_CASES = 3809


def connect(db):
    con = sqlite3.connect(
        f"file:{db}?mode=ro&immutable=1",
        uri=True,
        timeout=120,
    )
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    return con


def write_csv(path, rows):
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)

    fields = []
    seen = set()

    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fields.append(key)

    with path.open("w", newline="", encoding="utf-8-sig") as f:
        if not fields:
            f.write("")
            return

        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def read_csv(path):
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def iso_dt(value):
    if not value:
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


def diff_hours(start, end):
    a = iso_dt(start)
    b = iso_dt(end)

    if not a or not b:
        return ""

    return round(
        (b - a).total_seconds() / 3600.0,
        4,
    )


def num(value):
    try:
        return float(value)
    except Exception:
        return None


def med(values):
    vals = [
        float(x)
        for x in values
        if num(x) is not None
    ]

    if not vals:
        return ""

    return round(statistics.median(vals), 4)


def mean(values):
    vals = [
        float(x)
        for x in values
        if num(x) is not None
    ]

    if not vals:
        return ""

    return round(statistics.mean(vals), 4)


def pct_true(rows, field):
    vals = []

    for row in rows:
        value = row.get(field)

        if value in (None, ""):
            continue

        try:
            vals.append(int(float(value)) != 0)
        except Exception:
            pass

    if not vals:
        return ""

    return round(100 * sum(vals) / len(vals), 3)


def case_set(path):
    values = set()

    if not path.exists():
        return values

    for line in path.read_text().splitlines():
        line = line.strip()

        if not line:
            continue

        values.add(int(line))

    return values


def classify_file(filename):
    p = str(filename or "").replace("\\", "/").lower()
    base = p.rsplit("/", 1)[-1]

    test_tokens = (
        "/test/",
        "/tests/",
        "/__tests__/",
        "/spec/",
        "/specs/",
        ".test.",
        ".spec.",
        "_test.",
        "_tests.",
    )

    is_test = any(x in "/" + p for x in test_tokens)

    is_ci = (
        p.startswith(".github/workflows/")
        or "/.github/workflows/" in "/" + p
        or "circleci" in p
        or "jenkinsfile" in p
        or ".travis" in p
        or "gitlab-ci" in p
    )

    lock_names = {
        "package-lock.json",
        "npm-shrinkwrap.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "pnpm-lock.yml",
        "poetry.lock",
        "pipfile.lock",
        "composer.lock",
        "cargo.lock",
        "go.sum",
        "gemfile.lock",
    }

    is_lock = (
        base in lock_names
        or base.endswith(".lock")
    )

    dep_names = {
        "package.json",
        "pyproject.toml",
        "pipfile",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "cargo.toml",
        "go.mod",
        "gemfile",
        "composer.json",
        "requirements.txt",
        "environment.yml",
        "environment.yaml",
    }

    is_dependency = (
        is_lock
        or base in dep_names
        or base.startswith("requirements")
        and base.endswith(".txt")
    )

    is_docs = (
        base.startswith("readme")
        or base.startswith("changelog")
        or p.startswith("docs/")
        or "/docs/" in "/" + p
        or p.endswith(".md")
        or p.endswith(".rst")
        or p.endswith(".adoc")
    )

    config_ext = (
        ".yml",
        ".yaml",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
    )

    is_config = (
        p.endswith(config_ext)
        or base.startswith(".env")
        or base in {
            "dockerfile",
            "makefile",
            "tsconfig.json",
            "eslint.config.js",
            "eslint.config.mjs",
            ".eslintrc",
            ".prettierrc",
        }
    )

    source_ext = (
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".ts",
        ".tsx",
        ".py",
        ".java",
        ".go",
        ".rs",
        ".c",
        ".cc",
        ".cpp",
        ".h",
        ".hpp",
        ".cs",
        ".rb",
        ".php",
        ".swift",
        ".kt",
        ".kts",
        ".scala",
        ".sh",
    )

    is_source = (
        p.endswith(source_ext)
        and not is_test
    )

    return {
        "is_test": int(is_test),
        "is_ci": int(is_ci),
        "is_lockfile": int(is_lock),
        "is_dependency": int(is_dependency),
        "is_docs": int(is_docs),
        "is_config": int(is_config),
        "is_source": int(is_source),
    }


def core_worker(db, out):
    con = connect(db)

    count = con.execute(
        "SELECT COUNT(*) FROM cases"
    ).fetchone()[0]

    if count != EXPECTED_CASES:
        raise RuntimeError(
            f"cases={count}, expected={EXPECTED_CASES}"
        )

    query = """
    SELECT
        c.id AS case_id,
        c.status AS case_status,
        c.ai_cohort,
        c.downstream_signal,
        c.auto_tags,

        r.full_name AS repository,
        r.html_url AS repo_url,
        r.stars AS repo_stars,
        r.language AS repo_language,
        r.archived AS repo_archived,

        i.number AS issue_number,
        i.url AS issue_url,
        i.author AS issue_author,
        i.title AS issue_title,
        i.body AS issue_body,
        i.labels AS issue_labels,
        i.comments_count AS issue_comments,
        i.created_at AS issue_created_at,
        i.closed_at AS issue_closed_at,
        i.word_count AS issue_word_count,
        i.is_english AS issue_is_english,

        p.number AS pr_number,
        p.url AS pr_url,
        p.author AS pr_author,
        p.title AS pr_title,
        p.body AS pr_body,
        p.head_ref,
        p.base_ref,
        p.head_sha,
        p.base_sha,
        p.additions AS pr_additions,
        p.deletions AS pr_deletions,
        p.changed_files_count AS pr_changed_files,
        p.commits_count AS pr_commits,
        p.review_comments_count AS pr_review_comments,
        p.created_at AS pr_created_at,
        p.closed_at AS pr_closed_at,
        p.merged_at AS pr_merged_at

    FROM cases c
    JOIN repos r
        ON r.id = c.repo_id
    JOIN issues i
        ON i.id = c.issue_id
    JOIN pull_requests p
        ON p.id = c.pr_id
    ORDER BY c.id
    """

    core = []
    text = []

    for r in con.execute(query):
        row = dict(r)

        issue_body = row.pop("issue_body") or ""
        pr_body = row.pop("pr_body") or ""

        row["issue_title_chars"] = len(
            row.get("issue_title") or ""
        )
        row["issue_body_chars"] = len(issue_body)
        row["issue_body_lines"] = (
            issue_body.count("\n") + 1
            if issue_body
            else 0
        )

        row["pr_title_chars"] = len(
            row.get("pr_title") or ""
        )
        row["pr_body_chars"] = len(pr_body)
        row["pr_body_lines"] = (
            pr_body.count("\n") + 1
            if pr_body
            else 0
        )

        row["issue_duration_hours"] = diff_hours(
            row.get("issue_created_at"),
            row.get("issue_closed_at"),
        )

        row["issue_to_pr_hours"] = diff_hours(
            row.get("issue_created_at"),
            row.get("pr_created_at"),
        )

        row["pr_time_to_merge_hours"] = diff_hours(
            row.get("pr_created_at"),
            row.get("pr_merged_at"),
        )

        row["pr_total_changed_lines"] = (
            int(row.get("pr_additions") or 0)
            + int(row.get("pr_deletions") or 0)
        )

        ia = str(row.get("issue_author") or "")
        pa = str(row.get("pr_author") or "")

        row["same_issue_pr_author"] = int(
            bool(ia)
            and bool(pa)
            and ia.lower() == pa.lower()
        )

        row["pr_review_comments_present"] = int(
            int(row.get("pr_review_comments") or 0) > 0
        )

        core.append(row)

        text.append(
            {
                "case_id": row["case_id"],
                "issue_title": row.get("issue_title"),
                "issue_body": issue_body,
                "pr_title": row.get("pr_title"),
                "pr_body": pr_body,
            }
        )

    write_csv(out / "core_cases.csv", core)
    write_csv(out / "case_text.csv", text)

    con.close()

    (out / "CORE_DONE.txt").write_text(
        f"core_cases={len(core)}\n"
    )

    print(f"CORE DONE: {len(core)} cases")


def files_worker(db, out):
    con = connect(db)

    query = """
    SELECT
        c.id AS case_id,
        pf.id AS pr_file_id,
        pf.pr_id,
        pf.filename,
        pf.status,
        pf.additions,
        pf.deletions,
        pf.category
    FROM cases c
    JOIN pr_files pf
        ON pf.pr_id = c.pr_id
    ORDER BY c.id, pf.id
    """

    outfile = out / "case_files.csv"

    fields = [
        "case_id",
        "pr_file_id",
        "pr_id",
        "filename",
        "status",
        "additions",
        "deletions",
        "category",
        "is_source",
        "is_test",
        "is_dependency",
        "is_lockfile",
        "is_ci",
        "is_config",
        "is_docs",
    ]

    agg = defaultdict(
        lambda: {
            "file_row_count": 0,
            "file_additions": 0,
            "file_deletions": 0,
            "largest_file_change_lines": 0,
            "source_file_count": 0,
            "test_file_count": 0,
            "dependency_file_count": 0,
            "lockfile_count": 0,
            "ci_file_count": 0,
            "config_file_count": 0,
            "docs_file_count": 0,
            "categories": set(),
        }
    )

    with outfile.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        w = csv.DictWriter(
            f,
            fieldnames=fields,
        )
        w.writeheader()

        total = 0

        for r in con.execute(query):
            row = dict(r)
            flags = classify_file(
                row.get("filename")
            )

            row.update(flags)

            w.writerow(
                {
                    key: row.get(key, "")
                    for key in fields
                }
            )

            cid = int(row["case_id"])
            a = agg[cid]

            additions = int(
                row.get("additions") or 0
            )
            deletions = int(
                row.get("deletions") or 0
            )

            a["file_row_count"] += 1
            a["file_additions"] += additions
            a["file_deletions"] += deletions

            a["largest_file_change_lines"] = max(
                a["largest_file_change_lines"],
                additions + deletions,
            )

            for field, key in [
                ("is_source", "source_file_count"),
                ("is_test", "test_file_count"),
                (
                    "is_dependency",
                    "dependency_file_count",
                ),
                ("is_lockfile", "lockfile_count"),
                ("is_ci", "ci_file_count"),
                ("is_config", "config_file_count"),
                ("is_docs", "docs_file_count"),
            ]:
                if flags[field]:
                    a[key] += 1

            category = str(
                row.get("category") or ""
            ).strip()

            if category:
                a["categories"].add(category)

            total += 1

    output = []

    for cid in sorted(agg):
        a = agg[cid]

        output.append(
            {
                "case_id": cid,
                "file_row_count":
                    a["file_row_count"],
                "file_additions":
                    a["file_additions"],
                "file_deletions":
                    a["file_deletions"],
                "largest_file_change_lines":
                    a["largest_file_change_lines"],
                "source_file_count":
                    a["source_file_count"],
                "test_file_count":
                    a["test_file_count"],
                "dependency_file_count":
                    a["dependency_file_count"],
                "lockfile_count":
                    a["lockfile_count"],
                "ci_file_count":
                    a["ci_file_count"],
                "config_file_count":
                    a["config_file_count"],
                "docs_file_count":
                    a["docs_file_count"],
                "source_changed":
                    int(a["source_file_count"] > 0),
                "tests_changed":
                    int(a["test_file_count"] > 0),
                "dependencies_changed":
                    int(
                        a["dependency_file_count"] > 0
                    ),
                "lockfile_changed":
                    int(a["lockfile_count"] > 0),
                "ci_changed":
                    int(a["ci_file_count"] > 0),
                "config_changed":
                    int(a["config_file_count"] > 0),
                "docs_changed":
                    int(a["docs_file_count"] > 0),
                "existing_file_categories":
                    ";".join(
                        sorted(a["categories"])
                    ),
            }
        )

    write_csv(
        out / "case_file_agg.csv",
        output,
    )

    con.close()

    (out / "FILES_DONE.txt").write_text(
        f"case_file_rows={total}\n"
        f"cases_with_files={len(output)}\n"
        "raw_patch_exported=NO\n"
    )

    print(
        f"FILES DONE: {total} file rows, "
        f"{len(output)} cases"
    )


def context_worker(db, out):
    con = connect(db)

    feature_rows = [
        dict(r)
        for r in con.execute(
            """
            SELECT
                c.id AS case_id,
                uf.has_code_block,
                uf.has_inline_code,
                uf.has_traceback_or_log,
                uf.has_file_path,
                uf.has_function_or_class,
                uf.has_dependency_or_version,
                uf.has_suggested_fix,
                uf.has_ai_marker,
                uf.feature_json
            FROM cases c
            LEFT JOIN upstream_features uf
                ON uf.issue_id = c.issue_id
            ORDER BY c.id
            """
        )
    ]

    write_csv(
        out / "issue_features.csv",
        feature_rows,
    )

    marker_file = out / "ai_markers.csv"

    marker_fields = [
        "case_id",
        "issue_id",
        "pr_id",
        "marker_text",
        "marker_location",
        "confidence",
        "matched_tool",
        "created_at",
    ]

    marker_agg = defaultdict(
        lambda: {
            "count": 0,
            "pr": 0,
            "issue": 0,
            "tools": set(),
            "locations": set(),
            "confidences": set(),
        }
    )

    with marker_file.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        w = csv.DictWriter(
            f,
            fieldnames=marker_fields,
        )
        w.writeheader()

        marker_count = 0

        query = """
        SELECT
            am.case_id,
            am.issue_id,
            am.pr_id,
            am.marker_text,
            am.marker_location,
            am.confidence,
            am.matched_tool,
            am.created_at
        FROM ai_markers am
        JOIN cases c
            ON c.id = am.case_id
        ORDER BY am.case_id, am.id
        """

        for r in con.execute(query):
            row = dict(r)
            w.writerow(row)

            cid = int(row["case_id"])
            a = marker_agg[cid]

            a["count"] += 1

            location = str(
                row.get("marker_location") or ""
            )

            if location.startswith("pr_"):
                a["pr"] += 1

            if location.startswith("issue_"):
                a["issue"] += 1

            tool = str(
                row.get("matched_tool") or ""
            ).strip()

            if tool:
                a["tools"].add(tool)

            if location:
                a["locations"].add(location)

            confidence = str(
                row.get("confidence") or ""
            ).strip()

            if confidence:
                a["confidences"].add(
                    confidence
                )

            marker_count += 1

    marker_summary = []

    for cid in sorted(marker_agg):
        a = marker_agg[cid]

        marker_summary.append(
            {
                "case_id": cid,
                "ai_marker_count": a["count"],
                "pr_marker_count": a["pr"],
                "issue_marker_count": a["issue"],
                "pr_side_agent_marker":
                    int(a["pr"] > 0),
                "issue_side_agent_marker":
                    int(a["issue"] > 0),
                "agent_tools":
                    ";".join(sorted(a["tools"])),
                "ai_marker_locations":
                    ";".join(
                        sorted(a["locations"])
                    ),
                "ai_marker_confidences":
                    ";".join(
                        sorted(a["confidences"])
                    ),
            }
        )

    write_csv(
        out / "ai_case_agg.csv",
        marker_summary,
    )

    retrieval_rows = [
        dict(r)
        for r in con.execute(
            """
            SELECT
                cr.case_id,
                cr.stream_key,
                cr.term,
                cr.final_query,
                cr.created_at
            FROM case_retrievals cr
            JOIN cases c
                ON c.id = cr.case_id
            ORDER BY cr.case_id, cr.id
            """
        )
    ]

    write_csv(
        out / "case_retrievals.csv",
        retrieval_rows,
    )

    retrieval_agg = defaultdict(
        lambda: {
            "count": 0,
            "streams": set(),
            "terms": set(),
        }
    )

    for row in retrieval_rows:
        cid = int(row["case_id"])
        a = retrieval_agg[cid]

        a["count"] += 1

        stream = str(
            row.get("stream_key") or ""
        ).strip()

        term = str(
            row.get("term") or ""
        ).strip()

        if stream:
            a["streams"].add(stream)

        if term:
            a["terms"].add(term)

    retrieval_summary = []

    for cid in sorted(retrieval_agg):
        a = retrieval_agg[cid]

        retrieval_summary.append(
            {
                "case_id": cid,
                "retrieval_count": a["count"],
                "retrieval_streams":
                    ";".join(
                        sorted(a["streams"])
                    ),
                "retrieval_terms":
                    ";".join(
                        sorted(a["terms"])
                    ),
            }
        )

    write_csv(
        out / "retrieval_case_agg.csv",
        retrieval_summary,
    )

    con.close()

    (out / "CONTEXT_DONE.txt").write_text(
        f"issue_feature_rows={len(feature_rows)}\n"
        f"ai_marker_rows={marker_count}\n"
        f"retrieval_rows={len(retrieval_rows)}\n"
    )

    print(
        f"CONTEXT DONE: features={len(feature_rows)}, "
        f"markers={marker_count}, "
        f"retrievals={len(retrieval_rows)}"
    )


def scanner_worker(db, out):
    con = connect(db)

    runs = [
        dict(r)
        for r in con.execute(
            """
            SELECT
                sr.case_id,
                sr.pr_id,
                sr.scanner,
                sr.status,
                sr.started_at,
                sr.finished_at
            FROM scanner_runs sr
            JOIN cases c
                ON c.id = sr.case_id
            ORDER BY sr.case_id, sr.scanner, sr.id
            """
        )
    ]

    write_csv(
        out / "scanner_runs.csv",
        runs,
    )

    jobs = [
        dict(r)
        for r in con.execute(
            """
            SELECT
                sj.case_id,
                sj.job_type,
                sj.status,
                sj.priority,
                sj.attempts,
                sj.created_at,
                sj.started_at,
                sj.finished_at,
                sj.route_reason
            FROM scanner_jobs sj
            JOIN cases c
                ON c.id = sj.case_id
            ORDER BY sj.case_id, sj.job_type, sj.id
            """
        )
    ]

    write_csv(
        out / "scanner_jobs.csv",
        jobs,
    )

    findings = [
        dict(r)
        for r in con.execute(
            """
            SELECT
                sf.id AS finding_id,
                sf.case_id,
                sf.pr_id,
                sf.scanner,
                sf.finding_type,
                sf.severity,
                sf.rule_id,
                sf.cwe,
                sf.file_path,
                sf.line,
                sf.description,
                sf.introduced,
                sf.created_at
            FROM scanner_findings sf
            JOIN cases c
                ON c.id = sf.case_id
            ORDER BY sf.case_id, sf.id
            """
        )
    ]

    write_csv(
        out / "scanner_findings.csv",
        findings,
    )

    case_agg = defaultdict(
        lambda: {
            "run_count": 0,
            "job_count": 0,
            "finding_count": 0,
            "introduced_count": 0,
            "scanners_seen": set(),
            "run_statuses": set(),
            "job_types": set(),
            "job_statuses": set(),
            "positive_scanners": set(),
        }
    )

    scanner_status = Counter()

    for row in runs:
        cid = int(row["case_id"])
        a = case_agg[cid]

        a["run_count"] += 1

        scanner = str(
            row.get("scanner") or ""
        ).strip()

        status = str(
            row.get("status") or ""
        ).strip()

        if scanner:
            a["scanners_seen"].add(scanner)

        if status:
            a["run_statuses"].add(status)

        scanner_status[
            (scanner, status)
        ] += 1

    for row in jobs:
        cid = int(row["case_id"])
        a = case_agg[cid]

        a["job_count"] += 1

        job_type = str(
            row.get("job_type") or ""
        ).strip()

        status = str(
            row.get("status") or ""
        ).strip()

        if job_type:
            a["job_types"].add(job_type)

        if status:
            a["job_statuses"].add(status)

    for row in findings:
        cid = int(row["case_id"])
        a = case_agg[cid]

        a["finding_count"] += 1

        if int(row.get("introduced") or 0) == 1:
            a["introduced_count"] += 1

            scanner = str(
                row.get("scanner") or ""
            ).strip()

            if scanner:
                a["positive_scanners"].add(
                    scanner
                )

    output = []

    for cid in sorted(case_agg):
        a = case_agg[cid]

        output.append(
            {
                "case_id": cid,
                "scanner_run_count":
                    a["run_count"],
                "scanner_job_count":
                    a["job_count"],
                "raw_finding_count":
                    a["finding_count"],
                "introduced_finding_count":
                    a["introduced_count"],
                "snapshot_scanner_positive":
                    int(
                        a["introduced_count"] > 0
                    ),
                "scanners_seen":
                    ";".join(
                        sorted(
                            a["scanners_seen"]
                        )
                    ),
                "scanner_run_statuses":
                    ";".join(
                        sorted(
                            a["run_statuses"]
                        )
                    ),
                "scanner_job_types":
                    ";".join(
                        sorted(
                            a["job_types"]
                        )
                    ),
                "scanner_job_statuses":
                    ";".join(
                        sorted(
                            a["job_statuses"]
                        )
                    ),
                "positive_scanners":
                    ";".join(
                        sorted(
                            a["positive_scanners"]
                        )
                    ),
                "positive_scanner_count":
                    len(a["positive_scanners"]),
            }
        )

    write_csv(
        out / "scanner_case_agg.csv",
        output,
    )

    write_csv(
        out / "summary_scanner_status.csv",
        [
            {
                "scanner": scanner,
                "status": status,
                "run_rows": count,
            }
            for (
                scanner,
                status,
            ), count in sorted(
                scanner_status.items()
            )
        ],
    )

    con.close()

    (out / "SCANNER_DONE.txt").write_text(
        f"scanner_runs={len(runs)}\n"
        f"scanner_jobs={len(jobs)}\n"
        f"scanner_findings={len(findings)}\n"
    )

    print(
        f"SCANNER DONE: runs={len(runs)}, "
        f"jobs={len(jobs)}, "
        f"findings={len(findings)}"
    )


def merge_worker(out, validated_file, excluded_file):
    required = [
        "CORE_DONE.txt",
        "FILES_DONE.txt",
        "CONTEXT_DONE.txt",
        "SCANNER_DONE.txt",
    ]

    missing = [
        name
        for name in required
        if not (out / name).exists()
    ]

    if missing:
        raise RuntimeError(
            "Missing worker outputs: "
            + ", ".join(missing)
        )

    core = read_csv(
        out / "core_cases.csv"
    )

    if len(core) != EXPECTED_CASES:
        raise RuntimeError(
            f"core_cases={len(core)}, "
            f"expected={EXPECTED_CASES}"
        )

    sources = {}

    for filename in [
        "case_file_agg.csv",
        "issue_features.csv",
        "ai_case_agg.csv",
        "retrieval_case_agg.csv",
        "scanner_case_agg.csv",
    ]:
        data = read_csv(out / filename)

        sources[filename] = {
            str(r["case_id"]): r
            for r in data
        }

    validated = case_set(
        Path(validated_file)
    )

    excluded = case_set(
        Path(excluded_file)
    )

    master = []

    for row in core:
        cid = str(row["case_id"])

        merged = dict(row)

        for filename, index in sources.items():
            extra = index.get(cid, {})

            for key, value in extra.items():
                if key == "case_id":
                    continue

                merged[key] = value

        case_int = int(cid)

        merged["validated_positive_122"] = int(
            case_int in validated
        )

        merged[
            "excluded_after_validation_16"
        ] = int(case_int in excluded)

        master.append(merged)

    ids = {
        int(r["case_id"])
        for r in master
    }

    if len(ids) != EXPECTED_CASES:
        raise RuntimeError(
            f"unique_case_ids={len(ids)}, "
            f"expected={EXPECTED_CASES}"
        )

    if len(validated) != 122:
        raise RuntimeError(
            f"validated ID file has "
            f"{len(validated)} IDs, expected 122"
        )

    if len(excluded) != 16:
        raise RuntimeError(
            f"excluded ID file has "
            f"{len(excluded)} IDs, expected 16"
        )

    missing_validated = validated - ids

    if missing_validated:
        raise RuntimeError(
            "Validated IDs missing from corpus: "
            + ",".join(
                map(
                    str,
                    sorted(missing_validated),
                )
            )
        )

    write_csv(
        out / "eda_cases_3809_master.csv",
        master,
    )

    positive = [
        r
        for r in master
        if int(
            float(
                r.get(
                    "validated_positive_122",
                    0,
                )
                or 0
            )
        )
        == 1
    ]

    rest = [
        r
        for r in master
        if int(
            float(
                r.get(
                    "validated_positive_122",
                    0,
                )
                or 0
            )
        )
        == 0
    ]

    numeric_fields = [
        "repo_stars",
        "issue_comments",
        "issue_word_count",
        "issue_title_chars",
        "issue_body_chars",
        "issue_body_lines",
        "issue_duration_hours",
        "issue_to_pr_hours",
        "pr_time_to_merge_hours",
        "pr_additions",
        "pr_deletions",
        "pr_total_changed_lines",
        "pr_changed_files",
        "pr_commits",
        "pr_review_comments",
        "file_row_count",
        "file_additions",
        "file_deletions",
        "largest_file_change_lines",
        "source_file_count",
        "test_file_count",
        "dependency_file_count",
        "lockfile_count",
        "ci_file_count",
        "config_file_count",
        "docs_file_count",
        "ai_marker_count",
        "retrieval_count",
        "scanner_run_count",
        "scanner_job_count",
    ]

    binary_fields = [
        "same_issue_pr_author",
        "pr_review_comments_present",
        "has_code_block",
        "has_inline_code",
        "has_traceback_or_log",
        "has_file_path",
        "has_function_or_class",
        "has_dependency_or_version",
        "has_suggested_fix",
        "pr_side_agent_marker",
        "issue_side_agent_marker",
        "source_changed",
        "tests_changed",
        "dependencies_changed",
        "lockfile_changed",
        "ci_changed",
        "config_changed",
        "docs_changed",
    ]

    comparison = []

    for field in numeric_fields:
        comparison.append(
            {
                "field": field,
                "type": "numeric",
                "positive_n": len(
                    [
                        r
                        for r in positive
                        if num(
                            r.get(field)
                        )
                        is not None
                    ]
                ),
                "rest_n": len(
                    [
                        r
                        for r in rest
                        if num(
                            r.get(field)
                        )
                        is not None
                    ]
                ),
                "positive_median":
                    med(
                        [
                            r.get(field)
                            for r in positive
                        ]
                    ),
                "rest_median":
                    med(
                        [
                            r.get(field)
                            for r in rest
                        ]
                    ),
                "positive_mean":
                    mean(
                        [
                            r.get(field)
                            for r in positive
                        ]
                    ),
                "rest_mean":
                    mean(
                        [
                            r.get(field)
                            for r in rest
                        ]
                    ),
            }
        )

    for field in binary_fields:
        pos = pct_true(
            positive,
            field,
        )

        neg = pct_true(
            rest,
            field,
        )

        difference = ""

        if (
            num(pos) is not None
            and num(neg) is not None
        ):
            difference = round(
                float(pos) - float(neg),
                3,
            )

        comparison.append(
            {
                "field": field,
                "type": "binary",
                "positive_pct_true": pos,
                "rest_pct_true": neg,
                "difference_percentage_points":
                    difference,
            }
        )

    write_csv(
        out
        / "summary_positive_vs_rest.csv",
        comparison,
    )

    overview = [
        {
            "total_cases": len(master),
            "unique_cases": len(ids),
            "unique_repositories": len(
                {
                    r.get("repository")
                    for r in master
                    if r.get("repository")
                }
            ),
            "validated_positive_122":
                len(positive),
            "remaining_cases":
                len(rest),
            "snapshot_scanner_positive":
                sum(
                    int(
                        float(
                            r.get(
                                "snapshot_scanner_positive",
                                0,
                            )
                            or 0
                        )
                    )
                    for r in master
                ),
            "excluded_after_validation_16":
                sum(
                    int(
                        float(
                            r.get(
                                "excluded_after_validation_16",
                                0,
                            )
                            or 0
                        )
                    )
                    for r in master
                ),
        }
    ]

    write_csv(
        out / "summary_overview.csv",
        overview,
    )

    repo_counts = defaultdict(
        lambda: {
            "cases": 0,
            "positive": 0,
        }
    )

    for row in master:
        repo = (
            row.get("repository")
            or "(unknown)"
        )

        repo_counts[repo]["cases"] += 1

        repo_counts[repo]["positive"] += int(
            row.get(
                "validated_positive_122",
                0,
            )
            or 0
        )

    write_csv(
        out / "summary_by_repository.csv",
        [
            {
                "repository": repo,
                "cases": values["cases"],
                "positive_cases":
                    values["positive"],
                "positive_rate_pct": round(
                    100
                    * values["positive"]
                    / values["cases"],
                    3,
                ),
            }
            for repo, values in sorted(
                repo_counts.items(),
                key=lambda x: (
                    -x[1]["cases"],
                    x[0],
                ),
            )
        ],
    )

    language_counts = defaultdict(
        lambda: {
            "cases": 0,
            "positive": 0,
        }
    )

    for row in master:
        language = (
            row.get("repo_language")
            or "(unknown)"
        )

        language_counts[
            language
        ]["cases"] += 1

        language_counts[
            language
        ]["positive"] += int(
            row.get(
                "validated_positive_122",
                0,
            )
            or 0
        )

    write_csv(
        out / "summary_by_language.csv",
        [
            {
                "language": language,
                "cases": values["cases"],
                "positive_cases":
                    values["positive"],
                "positive_rate_pct": round(
                    100
                    * values["positive"]
                    / values["cases"],
                    3,
                ),
            }
            for language, values in sorted(
                language_counts.items(),
                key=lambda x: (
                    -x[1]["cases"],
                    x[0],
                ),
            )
        ],
    )

    agent_counts = defaultdict(
        lambda: {
            "cases": set(),
            "positive": set(),
        }
    )

    for row in master:
        cid = row["case_id"]

        tools = [
            x
            for x in str(
                row.get("agent_tools") or ""
            ).split(";")
            if x
        ]

        if not tools:
            tools = ["(unknown)"]

        for tool in tools:
            agent_counts[
                tool
            ]["cases"].add(cid)

            if int(
                row.get(
                    "validated_positive_122",
                    0,
                )
                or 0
            ):
                agent_counts[
                    tool
                ]["positive"].add(cid)

    write_csv(
        out / "summary_by_agent_tool.csv",
        [
            {
                "agent_tool": tool,
                "cases":
                    len(values["cases"]),
                "positive_cases":
                    len(values["positive"]),
                "positive_rate_pct": round(
                    100
                    * len(values["positive"])
                    / len(values["cases"]),
                    3,
                )
                if values["cases"]
                else "",
            }
            for tool, values in sorted(
                agent_counts.items(),
                key=lambda x: (
                    -len(
                        x[1]["cases"]
                    ),
                    x[0],
                ),
            )
        ],
    )

    month_counts = defaultdict(
        lambda: {
            "cases": 0,
            "positive": 0,
        }
    )

    for row in master:
        d = iso_dt(
            row.get("issue_created_at")
        )

        month = (
            d.strftime("%Y-%m")
            if d
            else "(unknown)"
        )

        month_counts[
            month
        ]["cases"] += 1

        month_counts[
            month
        ]["positive"] += int(
            row.get(
                "validated_positive_122",
                0,
            )
            or 0
        )

    write_csv(
        out / "summary_by_month.csv",
        [
            {
                "month": month,
                "cases": values["cases"],
                "positive_cases":
                    values["positive"],
            }
            for month, values in sorted(
                month_counts.items()
            )
        ],
    )

    flags = [
        "source_changed",
        "tests_changed",
        "dependencies_changed",
        "lockfile_changed",
        "ci_changed",
        "config_changed",
        "docs_changed",
    ]

    flag_rows = []

    for flag in flags:
        total_true = sum(
            int(
                float(
                    r.get(flag, 0)
                    or 0
                )
            )
            for r in master
        )

        pos_true = sum(
            int(
                float(
                    r.get(flag, 0)
                    or 0
                )
            )
            for r in positive
        )

        flag_rows.append(
            {
                "change_type": flag,
                "all_cases_true":
                    total_true,
                "all_cases_pct": round(
                    100
                    * total_true
                    / len(master),
                    3,
                ),
                "positive_true":
                    pos_true,
                "positive_pct": round(
                    100
                    * pos_true
                    / len(positive),
                    3,
                ),
            }
        )

    write_csv(
        out / "summary_change_shapes.csv",
        flag_rows,
    )

    qc = [
        f"total_cases={len(master)}",
        f"unique_case_ids={len(ids)}",
        f"validated_positive_ids={len(validated)}",
        f"validated_positive_rows={len(positive)}",
        f"excluded_ids={len(excluded)}",
        "raw_pr_patch_exported=NO",
        "artifact_regions_used=NO",
        "pr_region_profiles_used=NO",
        "new_github_mining=NO",
        "llm_classification=NO",
        "fingerprint_analysis=NO",
        "QC_STATUS=PASS",
    ]

    (out / "QC_REPORT.txt").write_text(
        "\n".join(qc) + "\n"
    )

    (out / "README.txt").write_text(
        "FULL CORPUS EDA BUNDLE\n\n"
        "Purpose: factual map of all 3,809 existing "
        "agent-associated issue-to-PR workflows.\n\n"
        "The master CSV contains one compact row per case. "
        "Long issue/PR text is kept in case_text.csv. "
        "Raw PR patches are deliberately excluded.\n\n"
        "The positive-vs-rest summaries are exploratory. "
        "They are for discovering broad candidate patterns, "
        "not final causal claims. Matched controls and deeper "
        "manual analysis come later.\n"
    )

    zip_path = out.parent / (
        out.name + ".zip"
    )

    with zipfile.ZipFile(
        zip_path,
        "w",
        zipfile.ZIP_DEFLATED,
    ) as zf:
        for path in sorted(out.iterdir()):
            if path.is_file():
                zf.write(
                    path,
                    path.relative_to(
                        out.parent
                    ),
                )

    print(
        (out / "QC_REPORT.txt").read_text()
    )

    print(f"ZIP={zip_path}")


def main():
    if len(sys.argv) < 4:
        print(
            "Usage: eda_parallel.py "
            "<mode> <db> <out> "
            "[validated_ids] [excluded_ids]"
        )
        return 2

    mode = sys.argv[1]
    db = Path(sys.argv[2])
    out = Path(sys.argv[3])

    out.mkdir(
        parents=True,
        exist_ok=True,
    )

    if mode == "core":
        core_worker(db, out)
        return 0

    if mode == "files":
        files_worker(db, out)
        return 0

    if mode == "context":
        context_worker(db, out)
        return 0

    if mode == "scanner":
        scanner_worker(db, out)
        return 0

    if mode == "merge":
        if len(sys.argv) < 6:
            print(
                "merge needs validated "
                "and excluded ID files"
            )
            return 3

        merge_worker(
            out,
            sys.argv[4],
            sys.argv[5],
        )
        return 0

    print(f"Unknown mode: {mode}")
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
