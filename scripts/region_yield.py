from __future__ import annotations

import os
from pathlib import Path

from src.db.database import Database
from src.settings import PROJECT_ROOT


def main() -> None:
    db = Database(Path(os.getenv("DB_PATH", PROJECT_ROOT / "data/miner.db")))
    db.init_schema(PROJECT_ROOT / "src/db/schema.sql")
    rows = db.query(
        """
        SELECT
            COALESCE(prp.primary_region, 'unprofiled') AS region,
            COUNT(DISTINCT c.id) AS candidate_count,
            COUNT(DISTINCT CASE WHEN sj.id IS NOT NULL THEN c.id END) AS scanner_routed_count,
            COUNT(DISTINCT CASE WHEN sf.id IS NOT NULL THEN c.id END) AS introduced_positive_count,
            COUNT(DISTINCT CASE WHEN c.status='needs_review' THEN c.id END) AS needs_review_count,
            COUNT(DISTINCT CASE WHEN c.final_label NOT IN ('Unclear','') THEN c.id END) AS manually_labeled_count
        FROM cases c
        LEFT JOIN pr_region_profiles prp ON prp.case_id=c.id
        LEFT JOIN scanner_jobs sj ON sj.case_id=c.id
        LEFT JOIN scanner_findings sf ON sf.case_id=c.id AND sf.introduced=1
        GROUP BY COALESCE(prp.primary_region, 'unprofiled')
        ORDER BY introduced_positive_count DESC, candidate_count DESC, region
        """
    )
    print("region,candidate_count,scanner_routed_count,introduced_positive_count,needs_review_count,manually_labeled_count,introduced_yield")
    for r in rows:
        cand = int(r["candidate_count"] or 0)
        intro = int(r["introduced_positive_count"] or 0)
        y = (intro / cand) if cand else 0.0
        print(f"{r['region']},{cand},{r['scanner_routed_count']},{intro},{r['needs_review_count']},{r['manually_labeled_count']},{y:.4f}")


if __name__ == "__main__":
    main()
