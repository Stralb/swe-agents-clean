from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from miner.db.database import Database
from miner.utils.paths import EXPORT_DIR

EXPORT_QUERY = """
SELECT
    c.id AS case_id,
    r.full_name AS repo,
    i.title AS issue_title,
    i.url AS issue_url,
    p.title AS pr_title,
    p.url AS pr_url,
    c.ai_cohort,
    c.downstream_signal,
    c.auto_tags,
    c.final_label,
    c.status,
    c.review_notes
FROM cases c
JOIN repos r ON c.repo_id = r.id
JOIN issues i ON c.issue_id = i.id
JOIN pull_requests p ON c.pr_id = p.id
ORDER BY c.id DESC
"""


def export_cases(db_path: str | Path) -> Path:
    db = Database(db_path)
    rows = db.query(EXPORT_QUERY)
    df = pd.DataFrame(rows)
    out_csv = EXPORT_DIR / "cases_export.csv"
    out_json = EXPORT_DIR / "cases_export.json"
    df.to_csv(out_csv, index=False)
    out_json.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return out_csv
