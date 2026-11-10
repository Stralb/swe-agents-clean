from __future__ import annotations

import json
from typing import Any

from src.artifacts.regions import classify_files, profile_summary
from src.db.database import Database

MAPPING_VERSION = "1.0"


def profile_case(db: Database, case_id: int) -> dict[str, Any]:
    """Persist the file-level region map for one issue-PR case.

    Scientific region membership is stored in artifact_regions and is therefore
    naturally multi-label at PR level. pr_region_profiles.primary_region remains
    only a backwards-compatible summary field.
    """
    case = db.one(
        "SELECT id, pr_id FROM cases WHERE id=?",
        (case_id,),
    )
    if not case:
        raise ValueError(f"Case {case_id} does not exist")

    files = db.query(
        """
        SELECT
            id,
            filename,
            status,
            additions,
            deletions,
            patch,
            category
        FROM pr_files
        WHERE pr_id=?
        ORDER BY id
        """,
        (int(case["pr_id"]),),
    )

    classifications = classify_files(files)
    summary = profile_summary(classifications)
    distinct_regions = sorted(summary["region_counts"])

    if not files:
        summary = {
            "primary_region": "unmapped",
            "region_counts": {},
            "scanner_routes": [],
            "languages": [],
            "file_count": 0,
        }
    elif len(distinct_regions) > 1:
        # Compatibility summary only. The actual pair retains every region.
        summary["primary_region"] = "multi_region"

    with db.transaction() as conn:
        with conn:
            conn.execute(
                "DELETE FROM artifact_regions WHERE case_id=?",
                (case_id,),
            )

            for file_row, classification in zip(
                files,
                classifications,
                strict=True,
            ):
                conn.execute(
                    """
                    INSERT INTO artifact_regions(
                        case_id,
                        pr_id,
                        pr_file_id,
                        path,
                        region,
                        language,
                        generated,
                        vendor,
                        scanner_routes,
                        confidence,
                        evidence,
                        mapping_version
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        case_id,
                        int(case["pr_id"]),
                        int(file_row["id"]),
                        classification.path,
                        classification.region,
                        classification.language,
                        int(classification.generated),
                        int(classification.vendor),
                        json.dumps(
                            classification.scanner_routes,
                            sort_keys=True,
                        ),
                        classification.confidence,
                        classification.evidence,
                        MAPPING_VERSION,
                    ),
                )

            conn.execute(
                """
                INSERT INTO pr_region_profiles(
                    case_id,
                    pr_id,
                    primary_region,
                    region_counts_json,
                    scanner_routes_json,
                    language_json,
                    file_count,
                    mapping_version,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(case_id) DO UPDATE SET
                    pr_id=excluded.pr_id,
                    primary_region=excluded.primary_region,
                    region_counts_json=excluded.region_counts_json,
                    scanner_routes_json=excluded.scanner_routes_json,
                    language_json=excluded.language_json,
                    file_count=excluded.file_count,
                    mapping_version=excluded.mapping_version,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    case_id,
                    int(case["pr_id"]),
                    str(summary["primary_region"]),
                    json.dumps(
                        summary["region_counts"],
                        sort_keys=True,
                    ),
                    json.dumps(
                        summary["scanner_routes"],
                        sort_keys=True,
                    ),
                    json.dumps(
                        summary["languages"],
                        sort_keys=True,
                    ),
                    int(summary["file_count"]),
                    MAPPING_VERSION,
                ),
            )

    return {
        "case_id": case_id,
        "pr_id": int(case["pr_id"]),
        "mapping_version": MAPPING_VERSION,
        **summary,
    }


def profile_missing_cases(db: Database) -> list[dict[str, Any]]:
    """Profile only missing, stale, or differently versioned cases."""
    rows = db.query(
        """
        SELECT c.id AS case_id
        FROM cases c
        LEFT JOIN pr_region_profiles prp
          ON prp.case_id=c.id
        WHERE prp.case_id IS NULL
           OR COALESCE(prp.mapping_version, '') != ?
           OR COALESCE(prp.file_count, -1) != (
                SELECT COUNT(*)
                FROM pr_files pf
                WHERE pf.pr_id=c.pr_id
           )
        ORDER BY c.id
        """,
        (MAPPING_VERSION,),
    )

    return [
        profile_case(db, int(row["case_id"]))
        for row in rows
    ]


def profile_all_cases(db: Database) -> list[dict[str, Any]]:
    """Force a complete rebuild using the current mapping version."""
    rows = db.query("SELECT id FROM cases ORDER BY id")
    return [
        profile_case(db, int(row["id"]))
        for row in rows
    ]
