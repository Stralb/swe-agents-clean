from __future__ import annotations

import json
import os
from pathlib import Path

from src.artifacts.regions import classify_files, profile_summary
from src.db.database import Database
from src.settings import PROJECT_ROOT


def main() -> None:
    db = Database(Path(os.getenv("DB_PATH", PROJECT_ROOT / "data/miner.db")))
    db.init_schema(PROJECT_ROOT / "src/db/schema.sql")
    cases = db.query("SELECT id, pr_id FROM cases ORDER BY id")
    for case in cases:
        case_id = int(case["id"])
        pr_id = int(case["pr_id"])
        files = db.query("SELECT id, filename, status, additions, deletions, patch, category FROM pr_files WHERE pr_id=?", (pr_id,))
        classes = classify_files(files)
        summary = profile_summary(classes)
        db.execute("DELETE FROM artifact_regions WHERE case_id=?", (case_id,))
        for f, c in zip(files, classes):
            db.execute(
                """
                INSERT INTO artifact_regions(case_id, pr_id, pr_file_id, path, region, language, generated, vendor, scanner_routes, confidence, evidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    case_id, pr_id, int(f["id"]), c.path, c.region, c.language, int(c.generated), int(c.vendor),
                    json.dumps(c.scanner_routes), c.confidence, c.evidence,
                ),
            )
        db.execute(
            """
            INSERT INTO pr_region_profiles(case_id, pr_id, primary_region, region_counts_json, scanner_routes_json, language_json, file_count, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(case_id) DO UPDATE SET
                primary_region=excluded.primary_region,
                region_counts_json=excluded.region_counts_json,
                scanner_routes_json=excluded.scanner_routes_json,
                language_json=excluded.language_json,
                file_count=excluded.file_count,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                case_id, pr_id, summary["primary_region"], json.dumps(summary["region_counts"], sort_keys=True),
                json.dumps(summary["scanner_routes"]), json.dumps(summary["languages"]), int(summary["file_count"]),
            ),
        )
    print(f"profiled_cases={len(cases)}")
    for row in db.query("SELECT primary_region, COUNT(*) AS n FROM pr_region_profiles GROUP BY primary_region ORDER BY n DESC, primary_region"):
        print((row["primary_region"], row["n"]))


if __name__ == "__main__":
    main()
