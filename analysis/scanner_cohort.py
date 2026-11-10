"""Standalone, read-only byte and case-label audit of original frozen C1 CSV.

Does not need C2, perform scanner runs, reconstruct positives from SQLite,
or prove historical alert correctness. Private C1 rows remain outside Git.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from analysis.cohort_lineage import (
    StageEvidenceError, _csv_rows, audit_recorded, load_recorded, require,
)

REQUIRED = {
    "case_id", "is_positive", "repository", "pr_id",
    "complete_opportunity_signature",
}


def verify_c1_cases_only(path: Path, data: dict,
                         *, expected_cases: int | None = None,
                         expected_positives: int | None = None) -> dict:
    """Frozen C1 checksum, unique case IDs and recorded positive label counts."""
    meta = data["c1_scanner_opportunity"]
    cases_expected = 3809 if expected_cases is None else expected_cases
    positives_expected = 192 if expected_positives is None else expected_positives
    require(type(cases_expected) is int and type(positives_expected) is int and
            0 < cases_expected and 0 <= positives_expected <= cases_expected,
            "Invalid C1 expected count")
    rows = _csv_rows(
        path, meta["input_sha256"], meta["input_bytes"],
        REQUIRED, "C1 frozen scanner-opportunity",
    )
    identifiers = set()
    positives = 0
    for row in rows:
        identifier = row["case_id"]
        require(identifier.isdecimal() and identifier not in identifiers,
                "C1 duplicate/non-numeric case identifier")
        identifiers.add(identifier)
        require(bool(row["repository"].strip()) and row["pr_id"].isdecimal(),
                "C1 missing repository or invalid PR ID")
        label = row["is_positive"]
        require(label in ("0", "1"), "C1 positive label is not binary")
        if label == "1":
            positives += 1
            signature = row["complete_opportunity_signature"]
            tokens = signature.split(";")
            require(all(x and x.strip() == x for x in tokens) and
                    len(tokens) == len(set(tokens)),
                    "C1 positive lacks unambiguous scanner opportunity")
    require(len(rows) == cases_expected and
            len(identifiers) == cases_expected and
            positives == positives_expected,
            "C1 byte-verified cohort does not match original count")
    return {
        "status": "PASS_C1_BYTES_AND_FROZEN_LABEL_COUNTS_ONLY",
        "c1_source_sha256": meta["input_sha256"],
        "bytes_verified": meta["input_bytes"],
        "case_rows": len(rows),
        "distinct_case_ids": len(identifiers),
        "source_recorded_positive_labels": positives,
        "source_recorded_negative_pool": len(rows) - positives,
        "sha256_verified_against_frozen_metadata": True,
        "positive_case_label_correctness_independently_verified": False,
        "final_sqlite_positive_set_recomputed": False,
        "original_scanners_reexecuted": False,
        "matched_pairs_recomputed": False,
        "causal_results_reproduced": False,
        "note": "This checks frozen case labels and bytes only; a 192-positive "
                "label is not proof of a verified security regression.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frozen_c1_csv", type=Path)
    args = parser.parse_args(argv)
    try:
        data = load_recorded()
        audit_recorded(data)
        output = verify_c1_cases_only(args.frozen_c1_csv, data)
        status = 0
    except (StageEvidenceError, OSError, UnicodeError, ValueError, TypeError,
            KeyError, json.JSONDecodeError) as exc:
        output = {
            "status": "BLOCKED_C1_FILE_OR_FROZEN_LABELS",
            "error": str(exc),
            "scanner_positive_set_reproduced": False,
        }
        status = 2
    print(json.dumps(output, indent=2, sort_keys=True))
    return status


if __name__ == "__main__":
    sys.exit(main())
