"""Source-count-conditional maximum-cardinality certificate for frozen C2.

This checks recorded eligibility-count rows, not the original C1 generator.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from analysis.frozen_c2_score_gate import (
    C2ScoreError, verify_candidate_cardinality,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate_counts", type=Path)
    parser.add_argument("matched_pairs", type=Path)
    args = parser.parse_args(argv)
    try:
        answer = verify_candidate_cardinality(args.candidate_counts,
                                               args.matched_pairs)
        code = 0
    except (C2ScoreError, OSError, ValueError, KeyError, TypeError) as exc:
        answer = {
            "status": "BLOCKED_C2_CANDIDATE_COUNT_CERTIFICATE",
            "error": str(exc),
            "original_candidate_generator_reproduced": False,
        }
        code = 2
    print(json.dumps(answer, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
