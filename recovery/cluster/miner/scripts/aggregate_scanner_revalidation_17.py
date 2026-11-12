#Group members:
#Tazeem Tayob - 2659956
#Arno Strauss - 2613224
#Zeeshaan Ebrahim - 2543004.

from __future__ import annotations

import csv
import json
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(
    "/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"
)

BASE = (
    ROOT
    / "data"
    / "scanner_revalidation_17"
)

RESULT_DIR = BASE / "results"

SUMMARY_CSV = (
    BASE
    / "scanner_revalidation_17_summary.csv"
)

SUMMARY_TXT = (
    BASE
    / "scanner_revalidation_17_summary.txt"
)

MANIFEST = (
    BASE
    / "scanner_revalidation_17_manifest.json"
)

ZIP_OUT = (
    ROOT
    / "data"
    / "scanner_revalidation_17_results.zip"
)

CASE_IDS = [
    59,
    290,
    291,
    299,
    649,
    3882,
    4621,
    5355,
    8038,
    8162,
    8461,
    9992,
    10361,
    10825,
    15151,
    15739,
    16203,
]

rows = []
results = []

for case_id in CASE_IDS:
    path = (
        RESULT_DIR
        / f"case_{case_id}.json"
    )

    if not path.exists():
        result = {
            "case_id": case_id,
            "status": "MISSING",
            "verdict": "SCAN_ERROR",
            "error": "Result file missing",
        }
    else:
        result = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    results.append(result)

    rows.append(
        {
            "case_id": case_id,
            "validation_type":
                result.get(
                    "validation_type"
                ),
            "status":
                result.get("status"),
            "verdict":
                result.get("verdict"),
            "repo":
                result.get(
                    "repo_full_name"
                ),
            "pr_number":
                result.get(
                    "pr_number"
                ),
            "original_base_sha":
                result.get(
                    "original_base_sha"
                ),
            "true_merge_base":
                result.get(
                    "true_merge_base"
                ),
            "head_sha":
                result.get(
                    "head_sha"
                ),
            "old_finding_count":
                result.get(
                    "old_finding_count"
                ),
            "new_finding_count":
                result.get(
                    "new_finding_count"
                ),
            "old_only_count":
                len(
                    result.get(
                        "old_only_signatures"
                    )
                    or []
                ),
            "new_only_count":
                len(
                    result.get(
                        "new_only_signatures"
                    )
                    or []
                ),
            "failed_required_runs":
                json.dumps(
                    result.get(
                        "failed_required_runs"
                    )
                    or {},
                    ensure_ascii=False,
                ),
            "error":
                result.get("error"),
        }
    )


with SUMMARY_CSV.open(
    "w",
    encoding="utf-8",
    newline="",
) as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=list(
            rows[0].keys()
        ),
    )

    writer.writeheader()
    writer.writerows(rows)


verdict_counts = Counter(
    str(
        result.get("verdict")
        or "UNKNOWN"
    )
    for result in results
)

status_counts = Counter(
    str(
        result.get("status")
        or "UNKNOWN"
    )
    for result in results
)

still_positive = [
    int(result["case_id"])
    for result in results
    if int(
        result.get(
            "new_finding_count"
        )
        or 0
    ) > 0
]

no_longer_positive = [
    int(result["case_id"])
    for result in results
    if result.get(
        "verdict"
    ) == "NO_LONGER_POSITIVE"
]

errors = [
    int(result["case_id"])
    for result in results
    if result.get(
        "verdict"
    ) == "SCAN_ERROR"
]

summary = (
    "SCANNER REVALIDATION - 17 CASES\n\n"
    f"Expected cases: {len(CASE_IDS)}\n"
    f"Result files:   {len(results)}\n\n"
    f"Status counts:  {dict(status_counts)}\n"
    f"Verdicts:       {dict(verdict_counts)}\n\n"
    f"Still positive: {still_positive}\n"
    f"No longer positive: {no_longer_positive}\n"
    f"Errors: {errors}\n"
)

SUMMARY_TXT.write_text(
    summary,
    encoding="utf-8",
)

manifest = {
    "created_at_utc":
        datetime.now(
            timezone.utc
        ).isoformat(),
    "case_ids": CASE_IDS,
    "status_counts":
        dict(status_counts),
    "verdict_counts":
        dict(verdict_counts),
    "still_positive_case_ids":
        still_positive,
    "no_longer_positive_case_ids":
        no_longer_positive,
    "error_case_ids":
        errors,
    "method": (
        "Re-run only the affected scanner family "
        "using true PR merge-base as before-state "
        "and stored PR head SHA as after-state. "
        "Original source database is read-only and "
        "never modified."
    ),
}

MANIFEST.write_text(
    json.dumps(
        manifest,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)

with zipfile.ZipFile(
    ZIP_OUT,
    "w",
    compression=zipfile.ZIP_DEFLATED,
    compresslevel=6,
) as archive:
    archive.write(
        SUMMARY_CSV,
        SUMMARY_CSV.name,
    )

    archive.write(
        SUMMARY_TXT,
        SUMMARY_TXT.name,
    )

    archive.write(
        MANIFEST,
        MANIFEST.name,
    )

    for case_id in CASE_IDS:
        result_file = (
            RESULT_DIR
            / f"case_{case_id}.json"
        )

        if result_file.exists():
            archive.write(
                result_file,
                f"results/{result_file.name}",
            )

print(summary)

print(
    f"ZIP: {ZIP_OUT}"
)
