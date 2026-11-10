from __future__ import annotations
import csv, sqlite3, statistics, sys, zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

EXPECTED = 3809

ACTIVE = {
7930,7791,6104,154,3340,16262,461,4379,5264,5267,10145,10146,10155,169,
4299,4309,13918,13919,13922,280,4621,3267,5355,15151,668,629,299,415,
15684,3697,3699,648,13501,12358,13422,10326,10330,10339,10361,16332,
16341,16343,10773,10779,3581,3582,3592,15686,3448,4207,4216,649,15694,
15703,3382,9992,9994,9998,10005,7682,12354,704,3882,11286,11539,12925,
10819,9942,12334,290,291,313,334,8461,3429,16311,15739,15748,15749,3490,
8135,14194,16298,3622,6145,6150,6183,12344,4408,12361,16301,4811,653,
3504,10375,708,10791,4134,4135,7680,12328,8147,8149,8152,10270,10277,
181,3684,16209,16213,8173,12888,11276,664,11275,16203,6017,166,16178,
12313,12898,608
}

EXCLUDED = {
59,147,155,3623,3689,4665,8038,8162,8298,8473,9279,
10187,10188,10189,10268,10825
}


def dt(s):
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d
    except Exception:
        return None


def hrs(a, b):
    a, b = dt(a), dt(b)
    return round((b - a).total_seconds() / 3600, 4) if a and b else None


def write_csv(path, rows, cols=None):
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)

    if cols is None:
        cols = []
        seen = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    seen.add(key)
                    cols.append(key)

    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def rows(con, sql, args=()):
    return [dict(r) for r in con.execute(sql, args)]


def exists(con, table):
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def cols(con, table):
    if not exists(con, table):
        return []
    return [r[1] for r in con.execute(f'PRAGMA table_info("{table}")')]


def median(vals):
    numbers = [float(x) for x in vals if x not in (None, "")]
    return round(statistics.median(numbers), 4) if numbers else None


def compact_table(con, table, keep, case_ids, out):
    if not exists(con, table):
        return []

    available = set(cols(con, table))
    use = [c for c in keep if c in available]

    if not use:
        return []

    data = rows(
        con,
        "SELECT "
        + ",".join('"' + c + '"' for c in use)
        + f' FROM "{table}"',
    )

    if "case_id" in use:
        data = [r for r in data if r.get("case_id") in case_ids]

    write_csv(out / f"{table}_compact.csv", data, use)
    return data


def main():
    if len(ACTIVE) != 122 or len(EXCLUDED) != 16:
        raise RuntimeError("embedded ID sets invalid")

    db = Path(sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(
        f"file:{db}?mode=ro&immutable=1",
        uri=True,
        timeout=120,
    )
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")

    n = con.execute("SELECT COUNT(*) FROM cases").fetchone()[0]

    if n != EXPECTED:
        (out / "QC_REPORT.txt").write_text(
            f"FAIL: cases table has {n} rows; expected {EXPECTED}. "
            "No guess made.\n"
        )
        print((out / "QC_REPORT.txt").read_text())
        return 4

    case_ids = {r[0] for r in con.execute("SELECT id FROM cases")}

    schema = []
    table_names = [
        r[0]
        for r in con.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' ORDER BY name"
        )
    ]

    for table in table_names:
        count = con.execute(
            f'SELECT COUNT(*) FROM "{table}"'
        ).fetchone()[0]

        for c in con.execute(
            f'PRAGMA table_info("{table}")'
        ):
            schema.append(
                {
                    "table": table,
                    "rows": count,
                    "column": c[1],
                    "type": c[2],
                    "pk": c[5],
                }
            )

    write_csv(out / "schema_inventory.csv", schema)

    master = rows(
        con,
        """
        WITH pf AS (
            SELECT
                pr_id,
                COUNT(*) file_rows,
                SUM(additions) file_additions,
                SUM(deletions) file_deletions,
                MAX(additions + deletions) largest_file_change,
                GROUP_CONCAT(DISTINCT category) file_categories
            FROM pr_files
            GROUP BY pr_id
        ),
        am AS (
            SELECT
                case_id,
                COUNT(*) ai_marker_count,
                GROUP_CONCAT(DISTINCT matched_tool) ai_tools,
                GROUP_CONCAT(DISTINCT marker_location)
                    ai_marker_locations,
                GROUP_CONCAT(DISTINCT confidence)
                    ai_marker_confidence
            FROM ai_markers
            GROUP BY case_id
        ),
        sr AS (
            SELECT
                case_id,
                COUNT(*) scanner_run_rows,
                GROUP_CONCAT(DISTINCT scanner) scanners_seen,
                GROUP_CONCAT(DISTINCT status)
                    scanner_run_statuses
            FROM scanner_runs
            GROUP BY case_id
        ),
        sj AS (
            SELECT
                case_id,
                COUNT(*) scanner_job_rows,
                GROUP_CONCAT(DISTINCT job_type)
                    scanner_job_types,
                GROUP_CONCAT(DISTINCT status)
                    scanner_job_statuses
            FROM scanner_jobs
            GROUP BY case_id
        ),
        sf AS (
            SELECT
                case_id,
                COUNT(*) raw_finding_count,
                SUM(
                    CASE
                        WHEN introduced = 1 THEN 1
                        ELSE 0
                    END
                ) introduced_finding_count,
                COUNT(
                    DISTINCT CASE
                        WHEN introduced = 1 THEN scanner
                    END
                ) positive_scanner_count,
                GROUP_CONCAT(
                    DISTINCT CASE
                        WHEN introduced = 1 THEN scanner
                    END
                ) positive_scanners
            FROM scanner_findings
            GROUP BY case_id
        )

        SELECT
            c.id case_id,
            c.status case_status,
            c.ai_cohort,
            c.downstream_signal,

            r.full_name repository,
            r.html_url repo_url,

            i.number issue_number,
            i.url issue_url,
            i.author issue_author,
            i.title issue_title,
            i.created_at issue_created_at,
            i.closed_at issue_closed_at,
            i.comments_count issue_comments,
            i.word_count issue_word_count,

            p.number pr_number,
            p.url pr_url,
            p.author pr_author,
            p.title pr_title,
            p.created_at pr_created_at,
            p.closed_at pr_closed_at,
            p.merged_at pr_merged_at,
            p.additions pr_additions,
            p.deletions pr_deletions,
            p.changed_files_count pr_changed_files,
            p.commits_count pr_commits,
            p.review_comments_count pr_review_comments,

            uf.has_code_block,
            uf.has_inline_code,
            uf.has_traceback_or_log,
            uf.has_file_path,
            uf.has_function_or_class,
            uf.has_dependency_or_version,
            uf.has_suggested_fix,
            uf.has_ai_marker,

            COALESCE(pf.file_rows, 0) file_rows,
            COALESCE(pf.file_additions, 0) file_additions,
            COALESCE(pf.file_deletions, 0) file_deletions,
            COALESCE(pf.largest_file_change, 0)
                largest_file_change,
            COALESCE(pf.file_categories, "")
                file_categories,

            COALESCE(am.ai_marker_count, 0)
                ai_marker_count,
            COALESCE(am.ai_tools, "")
                ai_tools,
            COALESCE(am.ai_marker_locations, "")
                ai_marker_locations,
            COALESCE(am.ai_marker_confidence, "")
                ai_marker_confidence,

            COALESCE(sr.scanner_run_rows, 0)
                scanner_run_rows,
            COALESCE(sr.scanners_seen, "")
                scanners_seen,
            COALESCE(sr.scanner_run_statuses, "")
                scanner_run_statuses,

            COALESCE(sj.scanner_job_rows, 0)
                scanner_job_rows,
            COALESCE(sj.scanner_job_types, "")
                scanner_job_types,
            COALESCE(sj.scanner_job_statuses, "")
                scanner_job_statuses,

            COALESCE(sf.raw_finding_count, 0)
                raw_finding_count,
            COALESCE(sf.introduced_finding_count, 0)
                introduced_finding_count,
            COALESCE(sf.positive_scanner_count, 0)
                positive_scanner_count,
            COALESCE(sf.positive_scanners, "")
                positive_scanners

        FROM cases c
        JOIN repos r
            ON r.id = c.repo_id
        JOIN issues i
            ON i.id = c.issue_id
        JOIN pull_requests p
            ON p.id = c.pr_id
        LEFT JOIN upstream_features uf
            ON uf.issue_id = i.id
        LEFT JOIN pf
            ON pf.pr_id = p.id
        LEFT JOIN am
            ON am.case_id = c.id
        LEFT JOIN sr
            ON sr.case_id = c.id
        LEFT JOIN sj
            ON sj.case_id = c.id
        LEFT JOIN sf
            ON sf.case_id = c.id
        ORDER BY c.id
        """,
    )

    for row in master:
        cid = row["case_id"]

        row["issue_duration_hours"] = hrs(
            row["issue_created_at"],
            row["issue_closed_at"],
        )

        row["issue_to_pr_hours"] = hrs(
            row["issue_created_at"],
            row["pr_created_at"],
        )

        row["pr_time_to_merge_hours"] = hrs(
            row["pr_created_at"],
            row["pr_merged_at"],
        )

        row["same_issue_pr_author"] = int(
            bool(
                row["issue_author"]
                and row["pr_author"]
                and row["issue_author"].lower()
                == row["pr_author"].lower()
            )
        )

        row["snapshot_scanner_positive"] = int(
            row["introduced_finding_count"] > 0
        )

        row["validated_positive_122"] = int(
            cid in ACTIVE
        )

        row["excluded_after_validation_16"] = int(
            cid in EXCLUDED
        )

        row["pr_total_changed_lines"] = (
            (row["pr_additions"] or 0)
            + (row["pr_deletions"] or 0)
        )

    write_csv(
        out / "eda_cases_master.csv",
        master,
    )

    text = rows(
        con,
        """
        SELECT
            c.id case_id,
            i.title issue_title,
            i.body issue_body,
            p.title pr_title,
            p.body pr_body
        FROM cases c
        JOIN issues i
            ON i.id = c.issue_id
        JOIN pull_requests p
            ON p.id = c.pr_id
        ORDER BY c.id
        """,
    )

    write_csv(
        out / "eda_case_text.csv",
        text,
    )

    files = rows(
        con,
        """
        SELECT
            c.id case_id,
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
        """,
    )

    write_csv(
        out / "eda_case_files.csv",
        files,
    )

    findings = compact_table(
        con,
        "scanner_findings",
        [
            "id",
            "case_id",
            "pr_id",
            "scanner",
            "finding_type",
            "severity",
            "rule_id",
            "cwe",
            "file_path",
            "line",
            "description",
            "introduced",
            "created_at",
        ],
        case_ids,
        out,
    )

    runs = (
        rows(
            con,
            """
            SELECT
                case_id,
                scanner,
                status,
                COUNT(*) records,
                MIN(started_at) first_started_at,
                MAX(finished_at) last_finished_at
            FROM scanner_runs
            WHERE case_id IS NOT NULL
            GROUP BY case_id, scanner, status
            ORDER BY case_id, scanner, status
            """,
        )
        if exists(con, "scanner_runs")
        else []
    )

    write_csv(
        out / "scanner_runs_compact.csv",
        runs,
    )

    jobs = (
        rows(
            con,
            """
            SELECT
                case_id,
                job_type,
                status,
                COUNT(*) records,
                MAX(attempts) max_attempts,
                MIN(created_at) first_created_at,
                MAX(finished_at) last_finished_at
            FROM scanner_jobs
            WHERE case_id IS NOT NULL
            GROUP BY case_id, job_type, status
            ORDER BY case_id, job_type, status
            """,
        )
        if exists(con, "scanner_jobs")
        else []
    )

    write_csv(
        out / "scanner_jobs_compact.csv",
        jobs,
    )

    markers = compact_table(
        con,
        "ai_markers",
        [
            "id",
            "case_id",
            "issue_id",
            "pr_id",
            "marker_text",
            "marker_location",
            "confidence",
            "matched_tool",
            "created_at",
        ],
        case_ids,
        out,
    )

    regions = compact_table(
        con,
        "artifact_regions",
        [
            "id",
            "case_id",
            "pr_id",
            "pr_file_id",
            "path",
            "region",
            "created_at",
        ],
        case_ids,
        out,
    )

    compact_table(
        con,
        "pr_region_profiles",
        [
            "id",
            "case_id",
            "pr_id",
            "primary_region",
            "regions_json",
            "created_at",
            "updated_at",
        ],
        case_ids,
        out,
    )

    compact_table(
        con,
        "case_retrievals",
        [
            "id",
            "case_id",
            "term",
            "stream",
            "created_at",
        ],
        case_ids,
        out,
    )

    apparent = sum(
        r["snapshot_scanner_positive"]
        for r in master
    )

    final = sum(
        r["validated_positive_122"]
        for r in master
    )

    overview = [
        {
            "cases": len(master),
            "repositories": len(
                {r["repository"] for r in master}
            ),
            "snapshot_apparent_positive": apparent,
            "validated_positive_122": final,
            "excluded_after_validation_16": sum(
                r["excluded_after_validation_16"]
                for r in master
            ),
            "file_rows": len(files),
            "finding_rows_compact": len(findings),
            "scanner_run_rows_compact": len(runs),
            "scanner_job_rows_compact": len(jobs),
            "ai_marker_rows": len(markers),
        }
    ]

    write_csv(
        out / "summary_overview.csv",
        overview,
    )

    for key, outname in [
        ("ai_tools", "summary_by_agent_tool.csv"),
        (
            "file_categories",
            "summary_by_file_category.csv",
        ),
        (
            "positive_scanners",
            "summary_by_positive_scanner.csv",
        ),
    ]:
        total = Counter()
        positive = Counter()

        for row in master:
            values = [
                x.strip()
                for x in str(row.get(key) or "").split(",")
                if x.strip()
            ] or ["(none)"]

            for value in values:
                total[value] += 1
                positive[value] += row[
                    "validated_positive_122"
                ]

        write_csv(
            out / outname,
            [
                {
                    "value": value,
                    "cases": total[value],
                    "validated_positive_122":
                        positive[value],
                    "positive_rate_pct": round(
                        100
                        * positive[value]
                        / total[value],
                        3,
                    ),
                }
                for value in sorted(
                    total,
                    key=lambda x: (-total[x], x),
                )
            ],
        )

    region_total = Counter()
    region_positive = Counter()

    for row in regions:
        region = str(
            row.get("region") or "(none)"
        )
        cid = row.get("case_id")

        region_total[region] += 1
        region_positive[region] += int(
            cid in ACTIVE
        )

    write_csv(
        out / "summary_by_artifact_region.csv",
        [
            {
                "region": region,
                "region_rows": region_total[region],
                "validated_positive_rows":
                    region_positive[region],
            }
            for region in sorted(
                region_total,
                key=lambda x: (
                    -region_total[x],
                    x,
                ),
            )
        ],
    )

    repo_summary = defaultdict(
        lambda: {"cases": 0, "positive": 0}
    )

    for row in master:
        repo_summary[row["repository"]]["cases"] += 1
        repo_summary[row["repository"]]["positive"] += (
            row["validated_positive_122"]
        )

    write_csv(
        out / "summary_by_repo.csv",
        [
            {
                "repository": repo,
                "cases": values["cases"],
                "validated_positive_122":
                    values["positive"],
            }
            for repo, values in sorted(
                repo_summary.items(),
                key=lambda x: (
                    -x[1]["cases"],
                    x[0],
                ),
            )
        ],
    )

    month_summary = defaultdict(
        lambda: {"cases": 0, "positive": 0}
    )

    for row in master:
        d = dt(row["issue_created_at"])
        month = (
            d.strftime("%Y-%m")
            if d
            else "(unknown)"
        )

        month_summary[month]["cases"] += 1
        month_summary[month]["positive"] += (
            row["validated_positive_122"]
        )

    write_csv(
        out / "summary_by_month.csv",
        [
            {
                "month": month,
                **month_summary[month],
            }
            for month in sorted(month_summary)
        ],
    )

    numeric = [
        "issue_word_count",
        "issue_comments",
        "issue_duration_hours",
        "issue_to_pr_hours",
        "pr_time_to_merge_hours",
        "pr_additions",
        "pr_deletions",
        "pr_total_changed_lines",
        "pr_changed_files",
        "pr_commits",
        "pr_review_comments",
        "ai_marker_count",
        "scanner_run_rows",
        "scanner_job_rows",
    ]

    binary = [
        "has_code_block",
        "has_inline_code",
        "has_traceback_or_log",
        "has_file_path",
        "has_function_or_class",
        "has_dependency_or_version",
        "has_suggested_fix",
        "same_issue_pr_author",
    ]

    positives = [
        r
        for r in master
        if r["validated_positive_122"] == 1
    ]

    rest = [
        r
        for r in master
        if r["validated_positive_122"] == 0
    ]

    comparison = []

    for field in numeric:
        comparison.append(
            {
                "field": field,
                "kind": "continuous",
                "positive_median": median(
                    [r.get(field) for r in positives]
                ),
                "rest_median": median(
                    [r.get(field) for r in rest]
                ),
            }
        )

    for field in binary:
        def pct(group):
            values = [
                r.get(field)
                for r in group
                if r.get(field) not in (None, "")
            ]

            if not values:
                return None

            return round(
                100
                * sum(
                    int(v or 0) != 0
                    for v in values
                )
                / len(values),
                3,
            )

        comparison.append(
            {
                "field": field,
                "kind": "binary",
                "positive_pct_true": pct(positives),
                "rest_pct_true": pct(rest),
            }
        )

    write_csv(
        out / "summary_positive_vs_rest_descriptive.csv",
        comparison,
    )

    qc = [
        f"cases={len(master)} expected={EXPECTED}",
        (
            "unique_case_ids="
            f"{len({r['case_id'] for r in master})}"
        ),
        (
            "active_122_present="
            f"{sum(cid in case_ids for cid in ACTIVE)}/122"
        ),
        (
            "excluded_16_present="
            f"{sum(cid in case_ids for cid in EXCLUDED)}/16"
        ),
        f"snapshot_apparent_positive={apparent}",
        f"validated_positive={final}",
        "raw_code_diffs_exported=NO",
        "network_or_github_calls=NO",
        "llm_or_fingerprint_analysis=NO",
        "pragma_quick_check=NO",
    ]

    ok = (
        len(master) == EXPECTED
        and len(
            {r["case_id"] for r in master}
        ) == EXPECTED
        and final == 122
    )

    qc.append(
        "QC_STATUS="
        + ("PASS" if ok else "FAIL")
    )

    (out / "QC_REPORT.txt").write_text(
        "\n".join(qc) + "\n"
    )

    (out / "README.txt").write_text(
        "One-row-per-case factual EDA map of the "
        "existing 3,809 workflows. Raw patches/diffs "
        "are intentionally excluded. "
        "eda_case_text.csv keeps long issue/PR text "
        "separate. "
        "summary_positive_vs_rest_descriptive.csv is "
        "exploratory only; matched controls come later.\n"
    )

    con.close()

    zip_path = out.parent / (out.name + ".zip")

    with zipfile.ZipFile(
        zip_path,
        "w",
        zipfile.ZIP_DEFLATED,
    ) as archive:
        for path in sorted(out.iterdir()):
            if path.is_file():
                archive.write(
                    path,
                    path.relative_to(out.parent),
                )

    print(
        (out / "QC_REPORT.txt").read_text()
    )
    print("ZIP=" + str(zip_path))

    return 0 if ok else 5


if __name__ == "__main__":
    raise SystemExit(main())
