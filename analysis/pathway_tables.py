"""Independently recalculate C6 matched categorical tests from indexed aggregate counts.

The checked-in aggregate matrices are index representations of the C6/C7 paired
tables. No new labels, imputation, network calls or writes to source files.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
AGGREGATES = ROOT / "data" / "pathway_aggregates.json"
METRICS = ("Explicit instruction rate", "Suggests-solution rate", "Aligned goal rate")
C6_COLUMNS = {"scope", "variable", "positive_category", "control_category", "count"}
C7_COLUMNS = {"scope", "positive_pathway", "pairs", "metric", "positive_rate", "matched_control_rate", "paired_difference"}


class AggregateReplayError(ValueError):
    """Fail closed when source, matrix, assumptions, or derived results disagree."""


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AggregateReplayError(message)


def chi2_survival(chi_square: float, degrees: int) -> float:
    """Survival function P(Chi-square_df >= x) for positive integer df.

    Uses exact finite sums for even df and erfc/gamma recurrence for odd df.
    This code uses only Python's standard library and no approximate normal test.
    """
    check(type(degrees) is int and degrees >= 1, "Invalid chi-square degrees of freedom")
    check(math.isfinite(chi_square) and chi_square >= 0, "Invalid chi-square statistic")
    x = chi_square / 2.0
    if degrees % 2 == 0:
        term = 1.0
        result = 1.0
        for j in range(1, degrees // 2):
            term *= x / j
            result += term
        return min(1.0, math.exp(-x) * result)
    q = math.erfc(math.sqrt(x))
    alpha = 0.5
    for _ in range((degrees - 1) // 2):
        if x:
            q += math.exp(-x + alpha * math.log(x) - math.lgamma(alpha + 1.0))
        alpha += 1.0
    return max(0.0, min(1.0, q))


def _linear_solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Pivoted Gaussian elimination. Refuse unidentified, singular marginals."""
    n = len(matrix)
    check(n >= 1 and len(vector) == n and all(len(row) == n for row in matrix),
          "Invalid covariance dimension")
    a = [list(map(float, row)) + [float(vector[i])] for i, row in enumerate(matrix)]
    scale = max(1.0, *(abs(x) for row in matrix for x in row))
    for col in range(n):
        pivot = max(range(col, n), key=lambda k: abs(a[k][col]))
        check(abs(a[pivot][col]) > 1e-12 * scale,
              "Singular marginal covariance: reduce categories only with preregistered rules")
        a[col], a[pivot] = a[pivot], a[col]
        for row in range(col + 1, n):
            mult = a[row][col] / a[col][col]
            for j in range(col, n + 1):
                a[row][j] -= mult * a[col][j]
    solution = [0.0] * n
    for i in range(n - 1, -1, -1):
        solution[i] = (a[i][n] - sum(a[i][j] * solution[j] for j in range(i + 1, n))) / a[i][i]
    return solution


def stuart_maxwell(matrix: list[list[int]]) -> dict:
    """Generalized McNemar marginal-homogeneity test of paired square counts."""
    check(isinstance(matrix, list) and len(matrix) >= 2,
          "Categorical test needs at least two categories")
    k = len(matrix)
    check(all(isinstance(row, list) and len(row) == k and
              all(type(x) is int and x >= 0 for x in row) for row in matrix),
          "Paired contingency must be square, nonnegative integer counts")
    row = [sum(m) for m in matrix]
    col = [sum(matrix[i][j] for i in range(k)) for j in range(k)]
    total = sum(row)
    check(total > 0, "Cannot test an empty paired contingency")
    discrepancy = [row[i] - col[i] for i in range(k)]
    cov = [[(row[i] + col[i] - 2 * matrix[i][i] if i == j else
             -(matrix[i][j] + matrix[j][i])) for j in range(k-1)] for i in range(k-1)]
    solved = _linear_solve(cov, discrepancy[:-1])
    statistic = sum(discrepancy[i] * solved[i] for i in range(k-1))
    check(math.isfinite(statistic) and statistic >= -1e-10, "Invalid marginal statistic")
    statistic = max(0.0, statistic)
    return {
        "n_pairs_from_contingency": total,
        "categories": k,
        "row_totals": row,
        "column_totals": col,
        "chi_square": statistic,
        "df": k-1,
        "p_value": chi2_survival(statistic, k-1),
        "method": "Stuart-Maxwell matched-pair marginal homogeneity",
    }


def _load(path: Path = AGGREGATES) -> dict:
    blob = json.loads(path.read_text(encoding="utf-8"))
    check(blob.get("schema_version") == 1 and
          blob.get("status") == "INDEXED_TABLE_COUNTS_ONLY_ORIGINAL_C6_C7_BYTES_NOT_SHA256_AUTHENTICATED",
          "Invalid or misleading indexed-aggregate provenance")
    return blob


def replay_indexed(source: dict | None = None) -> dict:
    if source is None:
        source = _load()
    matrices = source["primary_categorical"]
    check(len(matrices) == 5 and set(matrices) == {
        "Issue purpose", "Instruction specificity", "Goal alignment",
        "Implementation category", "Primary agent/tool"},
          "Original five categorical primary comparisons changed")
    statistics = {}
    for name, entry in matrices.items():
        labels = entry["categories"]
        check(len(labels) == len(set(labels)) == len(entry["counts"]),
              "Nonunique or malformed category labels")
        result = stuart_maxwell(entry["counts"])
        check(result["n_pairs_from_contingency"] == 190, "Frozen denominator changed")
        check(round(result["p_value"], entry["display_digits"]) ==
              entry["historical_display_p"], "Historical displayed p-value does not match")
        statistics[name] = result

    pathways = source["c7_pathways"]
    check(set(pathways) == {"All matched pairs", "Tier-A same-repository"},
          "C7 scope changed")
    expected = {"All matched pairs": 190, "Tier-A same-repository": 115}
    recomputed = {}
    for scope, strata in pathways.items():
        check(set(strata) == {"Direct-only", "Side-effect-only",
                             "Mixed Direct/Side-effect", "Unclear-only",
                             "No mapped producing change"}, "Unrecognized C7 stratum")
        n = sum(x["n"] for x in strata.values())
        check(n == expected[scope], "Frozen C7 scope denominator changed")
        result = {}
        for metric in METRICS:
            p, c = 0, 0
            for entry in strata.values():
                nn = entry["n"]
                x, y = entry[metric]
                check(type(nn) is int and nn > 0 and type(x) is int and type(y) is int
                      and 0 <= x <= nn and 0 <= y <= nn,
                      "C7 stratum numerator exceeds denominator")
                p += x
                c += y
            result[metric] = {"positive_count": p, "control_count": c,
                              "positive_rate": p/n, "control_rate": c/n,
                              "paired_difference": (p-c)/n}
        recomputed[scope] = {"n_pairs": n, "metrics": result}
    # These link the indexed C7 pathway strata back to indexed C6 matched-pair margins.
    mappings = [("Explicit instruction rate", "Instruction specificity", "Explicit instruction"),
                ("Suggests-solution rate", "Instruction specificity", "Suggests solution"),
                ("Aligned goal rate", "Goal alignment", "Aligned")]
    for metric, variable, category in mappings:
        group = matrices[variable]
        i = group["categories"].index(category)
        positive = statistics[variable]["row_totals"][i]
        control = statistics[variable]["column_totals"][i]
        value = recomputed["All matched pairs"]["metrics"][metric]
        check((positive, control) == (value["positive_count"], value["control_count"]),
              "Indexed C7 pathway margins disagree with indexed C6 primary cohort")

    for name, tier in pathways["Tier-A same-repository"].items():
        original = pathways["All matched pairs"][name]
        check(tier["n"] <= original["n"], "Tier-A stratum larger than full cohort")
        for metric in METRICS:
            check(all(tier[metric][i] <= original[metric][i] for i in (0, 1)),
                  "Tier-A numerator exceeds full matched stratum")
    return {
        "status": "PASS_INDEXED_C6_CATEGORICAL_OMNIBUS_AND_C7_MARGINS_ONLY",
        "primary_categorical_tests_recomputed": len(statistics),
        "categorical_omnibus": statistics,
        "c7_pathway_margins": recomputed,
        "c7_c6_cross_table_mismatches": 0,
        "original_C6_C7_file_bytes_authenticated": False,
        "original_pair_level_semantic_coding_authenticated": False,
        "remaining_four_frozen_primary_tests_recomputed": False,
        "repository_blocked_resampling_reproduced": False,
        "causal_inference_supported": False,
    }


def _staged_raw(path: Path, size: int, sha256: str) -> bytes:
    path = path.absolute()
    check(path != ROOT and ROOT not in path.parents, "Original data must stay outside Git")
    check(all(not p.is_symlink() for p in (path, *path.parents)),
          "Symlink in original data path")
    check(re.fullmatch(r"[0-9a-f]{64}", sha256) is not None,
          "Pre-established SHA-256 is required for staged-source verification")
    mode = path.stat()
    check(path.is_file() and stat.S_ISREG(mode.st_mode) and mode.st_size == size,
          "Staged original has wrong length/type")
    before = mode.st_dev, mode.st_ino, mode.st_size, mode.st_mtime_ns, mode.st_ctime_ns
    data = path.read_bytes()
    check(hashlib.sha256(data).hexdigest() == sha256, "Staged source digest mismatch")
    after = path.stat()
    check((after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
          == before, "Staged original changed during verification")
    return data


def _csv_rows(raw: bytes) -> list[dict[str, str]]:
    with io.StringIO(raw.decode("utf-8-sig"), newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        check(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)),
              "Ambiguous CSV header")
        result = list(reader)
    check(all(None not in row and all(v is not None for v in row.values()) for row in result),
          "Malformed CSV record")
    return result


def staged_c6_checks(path: Path, sha256: str, source: dict | None = None,
                     *, source_bytes: int = 14591) -> dict:
    """Offline strict cross-check of an approved, original raw C6 contingency CSV."""
    source = _load() if source is None else source
    data = _csv_rows(_staged_raw(path, source_bytes, sha256))
    check(len(data) == 165, "Original C6 contingency row count changed")
    check(all(C6_COLUMNS <= set(row) for row in data), "C6 contingency schema changed")
    observations = {}
    for x in data:
        if x["scope"] != "PRIMARY":
            continue
        variable = x["variable"]
        check(variable in source["primary_categorical"], "Unexpected primary C6 variable")
        check(x["count"].isascii() and x["count"].isdecimal(), "Bad C6 contingency count")
        key = (variable, x["positive_category"], x["control_category"])
        check(key not in observations, "Duplicate C6 contingency cell")
        observations[key] = int(x["count"])
    check(len(observations) > 0, "No primary C6 categorical cells")
    for name, meta in source["primary_categorical"].items():
        labels = meta["categories"]
        for i, left in enumerate(labels):
            for j, right in enumerate(labels):
                check(observations.pop((name, left, right), 0) == meta["counts"][i][j],
                      "Source-authenticated C6 contingency disagrees with indexed aggregate")
    check(not observations, "Unknown C6 primary categorical cell")
    result = replay_indexed(source)
    result["original_C6_contingency_source_sha256_verified"] = True
    result["original_C6_contingency_source_bytes"] = source_bytes
    result["original_C6_C7_file_bytes_authenticated"] = False
    return result


def staged_c7_strata_checks(path: Path, sha256: str, source: dict | None = None,
                            *, source_bytes: int = 5831) -> dict:
    """Verify original C7 strata rates/denominators against the indexed counts.

    Does not authenticate the C7 case-level pathway assignments or resample CIs.
    """
    source = _load() if source is None else source
    rows = _csv_rows(_staged_raw(path, source_bytes, sha256))
    check(len(rows) == 30, "Original C7 strata table row count changed")
    check(all(C7_COLUMNS <= set(row) for row in rows), "C7 strata schema changed")
    expected = source["c7_pathways"]
    found = set()
    for row in rows:
        scope, pathway, metric = row["scope"], row["positive_pathway"], row["metric"]
        check(scope in expected and pathway in expected[scope] and metric in METRICS,
              "Unexpected C7 scope, stratum or metric")
        key = scope, pathway, metric
        check(key not in found, "Duplicate C7 scope/stratum/metric")
        found.add(key)
        entry = expected[scope][pathway]
        check(row["pairs"].isascii() and row["pairs"].isdecimal() and
              int(row["pairs"]) == entry["n"], "C7 strata denominator changed")
        pp, cc = entry[metric]
        actual_p, actual_c, actual_delta = (
            float(row["positive_rate"]), float(row["matched_control_rate"]),
            float(row["paired_difference"]))
        check(all(math.isfinite(v) for v in (actual_p, actual_c, actual_delta)),
              "C7 nonfinite rate or difference")
        check(abs(actual_p * entry["n"] - pp) <= 1e-8 and
              abs(actual_c * entry["n"] - cc) <= 1e-8 and
              abs(actual_delta - (actual_p-actual_c)) <= 1e-12,
              "C7 source rates disagree with indexed integer counts")
    check(len(found) == 30, "Missing C7 strata rows")
    output = replay_indexed(source)
    output["staged_C7_strata_source_sha256_matched_supplied_digest"] = True
    output["staged_C7_strata_verified_bytes"] = source_bytes
    output["original_C6_C7_file_bytes_authenticated"] = False
    output["original_C7_pair_level_pathways_authenticated"] = False
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("replay-indexed", help="Recalculate safe, non-case-level indexed C6/C7 aggregates")
    strict = sub.add_parser("verify-staged-c6", help="Require separately approved original C6 CSV and pre-established digest")
    strict.add_argument("source_csv", type=Path)
    strict.add_argument("expected_sha256")
    strict_c7 = sub.add_parser("verify-staged-c7-strata", help="Original C7 aggregate CSV with pre-established digest")
    strict_c7.add_argument("source_csv", type=Path)
    strict_c7.add_argument("expected_sha256")
    args = parser.parse_args(argv)
    try:
        if args.action == "replay-indexed":
            output = replay_indexed()
        elif args.action == "verify-staged-c6":
            output = staged_c6_checks(args.source_csv, args.expected_sha256)
        else:
            output = staged_c7_strata_checks(args.source_csv, args.expected_sha256)
        status = 0
    except (AggregateReplayError, OSError, csv.Error, UnicodeError, ValueError, KeyError, TypeError) as exc:
        output = {"status": "BLOCKED_INDEXED_C6_C7_REPLAY", "reason": str(exc),
                  "original_source_statistically_reproduced": False}
        status = 2
    print(json.dumps(output, indent=2, sort_keys=True))
    return status


if __name__ == "__main__":
    sys.exit(main())
