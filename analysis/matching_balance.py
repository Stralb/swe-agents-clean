"""Verify frozen C2 selected-pair scores and source-reported balance tables.

Read-only, source-byte pinned, standard-library only, offline. Does not run
original optimizer or reproduce security scanner results. Raw rows remain private.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import stat
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
MAX_INPUT_BYTES = 1_000_000
FINGERPRINTS = {
    "pairs": (56175, "4568dcadd50e827004b13c9a435c7034babce8ebf96d6a9bee49b66c9b11be2b"),
    "summary": (1025, "c5b64415961cd0598aeb4581b3f8669150b7d6e91b58a1ebc36039f4958ce6f9"),
    "balance": (361, "205d88f6e0155135de4d7d3adc7c71150af1368791b82d90de8816871e8f2947"),
    "quality": (365, "a4828f69cb5110c25453b8afb312dba9edd47471a515ca9bcd9c68b8428bf126"),
}
EXPECTED_C1_SHA = "6028cb41a3ab80921395f16ffd7c398763631d901363a4a326cb5f04bdca5d7b"
PAIRS_REQUIRED = {
    "positive_case_id", "control_case_id", "match_tier", "same_repository",
    "positive_repository", "control_repository", "opportunity_relation",
    "positive_opportunity_signature", "control_opportunity_signature",
    "positive_pr_created_at", "control_pr_created_at", "abs_pr_time_days",
    "positive_changed_lines", "control_changed_lines",
    "abs_log1p_changed_lines_diff", "changed_lines_ratio_larger_to_smaller_approx",
    "positive_changed_files", "control_changed_files",
    "abs_log1p_changed_files_diff", "changed_files_ratio_larger_to_smaller_approx",
    "normalized_distance",
}
METRICS = {
    "absolute_pr_time_days": "time",
    "changed_lines_ratio_larger_to_smaller_approx": "line_ratio",
    "changed_files_ratio_larger_to_smaller_approx": "file_ratio",
    "normalized_distance": "distance",
}
TOLERANCE = 1e-10


class C2ScoreError(ValueError):
    """A frozen C2 source, metric or caliper violates the expected contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise C2ScoreError(message)


def _file_bytes(path: Path, pin: tuple[int, str]) -> bytes:
    path = path.absolute()
    require(path != ROOT and ROOT not in path.parents,
            "Research input must not be placed inside repository")
    require(all(not x.is_symlink() for x in (path, *path.parents)),
            "Research input has a symlink component")
    require(path.is_file() and stat.S_ISREG(path.stat().st_mode),
            "Research input is missing or nonregular")
    stat_before = path.stat()
    require(stat_before.st_size == pin[0] and 0 < pin[0] <= MAX_INPUT_BYTES,
            "Frozen input size differs from expected byte count")
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == pin[1],
            "Frozen input SHA-256 mismatch")
    stat_after = path.stat()
    require((stat_before.st_dev, stat_before.st_ino, stat_before.st_size,
             stat_before.st_mtime_ns, stat_before.st_ctime_ns) ==
            (stat_after.st_dev, stat_after.st_ino, stat_after.st_size,
             stat_after.st_mtime_ns, stat_after.st_ctime_ns),
            "Research input changed during read")
    return raw


def _csv_rows(raw: bytes, required: set[str]) -> list[dict[str, str]]:
    try:
        stream = io.StringIO(raw.decode("utf-8-sig"), newline="")
        reader = csv.DictReader(stream, strict=True)
        header = reader.fieldnames
        require(bool(header) and len(header) == len(set(header)) and
                required <= set(header), "Frozen CSV header invalid")
        rows = list(reader)
    except (csv.Error, UnicodeError) as exc:
        raise C2ScoreError("Malformed frozen CSV") from exc
    require(bool(rows) and all(None not in r and
            all(isinstance(v, str) for v in r.values()) for r in rows),
            "Malformed frozen CSV record")
    return rows


def _finite(s: str, label: str) -> float:
    try:
        value = float(s)
    except (TypeError, ValueError) as exc:
        raise C2ScoreError("Non-numeric " + label) from exc
    require(math.isfinite(value), "Non-finite " + label)
    return value


def _nonnegative_int(s: str, label: str) -> int:
    require(s.isascii() and s.isdecimal() and str(int(s)) == s,
            "Noncanonical nonnegative integer: " + label)
    return int(s)


def _utc_millis(s: str) -> float:
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError as exc:
        raise C2ScoreError("Invalid original PR timestamp") from exc
    require(dt.tzinfo is not None and dt.utcoffset() is not None,
            "Timestamp missing UTC offset")
    return dt.astimezone(timezone.utc).timestamp() * 1000


def _sig(s: str) -> set[str]:
    p = s.split(";")
    require(all(x and x == x.strip() for x in p) and len(p) == len(set(p)),
            "Invalid scanner-opportunity signature")
    return set(p)


def _close(a: float, b: float) -> bool:
    return math.isfinite(a) and math.isfinite(b) and abs(a-b) <= (
        TOLERANCE * max(1.0, abs(a), abs(b))
    )


def _quantile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    at = p * (len(ordered) - 1)
    lower = math.floor(at)
    upper = math.ceil(at)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (at - lower)


def _must_equal_metric(value: float, raw: str, label: str) -> None:
    require(_close(value, _finite(raw, label)), "C2 metric mismatch: " + label)


def verify_scores(pairs: Path, summary: Path, balance: Path, quality: Path,
                  *, pins: dict | None = None, expected_pairs: int = 190,
                  expected_a: int = 115,
                  expected_c1_sha: str = EXPECTED_C1_SHA) -> dict:
    """Byte-attest four frozen C2 files; test-only pins/count overrides."""
    pins = FINGERPRINTS if pins is None else pins
    require(type(expected_pairs) is int and type(expected_a) is int and
            0 < expected_pairs and 0 <= expected_a <= expected_pairs,
            "Invalid expected frozen cohort counts")
    sources = dict(pairs=pairs, summary=summary, balance=balance, quality=quality)
    raw = {name: _file_bytes(path, pins[name]) for name, path in sources.items()}
    rows = _csv_rows(raw["pairs"], PAIRS_REQUIRED)
    require(len(rows) == expected_pairs, "Unexpected frozen pair count")
    try:
        original = json.loads(raw["summary"].decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise C2ScoreError("Malformed frozen summary") from exc
    require(isinstance(original, dict), "Frozen summary is not an object")
    require(original.get("c1_input_sha256") == expected_c1_sha,
            "C2 source C1 fingerprint differs")
    require(original.get("matched_pairs") == expected_pairs and
            original.get("tier_a_same_repo_pairs") == expected_a and
            original.get("tier_b_cross_repo_exact_pairs") == expected_pairs-expected_a and
            original.get("time_caliper_days") == 90.0 and
            original.get("size_ratio_caliper_approx") == 4.0,
            "C2 summary cohort/caliper parameters differ")
    tiers = {"A": 0, "B": 0}
    by_tier: dict[tuple[str, str], list[dict[str, float]]] = {}
    metrics = {x: [] for x in METRICS.values()}
    seen_positives, seen_controls = set(), set()
    for r in rows:
        positive, negative = r["positive_case_id"], r["control_case_id"]
        require(positive.isascii() and positive.isdecimal() and
                negative.isascii() and negative.isdecimal() and
                positive != negative and positive not in seen_positives and
                negative not in seen_controls,
                "Duplicate or malformed frozen pair identifiers")
        seen_positives.add(positive)
        seen_controls.add(negative)
        tier = r["match_tier"]
        require(tier in tiers, "Unrecognized frozen tier")
        tiers[tier] += 1
        same_repo = r["positive_repository"] == r["control_repository"]
        require(bool(r["positive_repository"].strip()) and
                bool(r["control_repository"].strip()) and
                r["same_repository"] == ("1" if same_repo else "0"),
                "Invalid repository/same-repository pairing")
        ps, ns = _sig(r["positive_opportunity_signature"]), _sig(
            r["control_opportunity_signature"])
        equal = ps == ns
        if tier == "A":
            require(same_repo and ps <= ns, "Invalid Tier A opportunity pairing")
        else:
            require(not same_repo and equal, "Invalid Tier B opportunity pairing")
        relation = "exact" if equal else "superset"
        require(r["opportunity_relation"] == relation,
                "C2 opportunity relation not implied by source signatures")
        lp = _nonnegative_int(r["positive_changed_lines"], "positive lines")
        ln = _nonnegative_int(r["control_changed_lines"], "control lines")
        fp = _nonnegative_int(r["positive_changed_files"], "positive files")
        fn = _nonnegative_int(r["control_changed_files"], "control files")
        days = abs(_utc_millis(r["positive_pr_created_at"]) -
                   _utc_millis(r["control_pr_created_at"])) / 86_400_000
        delta_lines = abs(math.log1p(lp) - math.log1p(ln))
        delta_files = abs(math.log1p(fp) - math.log1p(fn))
        line_ratio = (max(lp, ln) + 1) / (min(lp, ln) + 1)
        file_ratio = (max(fp, fn) + 1) / (min(fp, fn) + 1)
        distance = days/90 + (delta_lines + delta_files)/math.log(4)
        require(days <= 90 + TOLERANCE and line_ratio <= 4 + TOLERANCE and
                file_ratio <= 4 + TOLERANCE,
                "Frozen 90-day / 4x changed-size matching caliper violated")
        for k, v in (
            ("abs_pr_time_days", days),
            ("abs_log1p_changed_lines_diff", delta_lines),
            ("abs_log1p_changed_files_diff", delta_files),
            ("changed_lines_ratio_larger_to_smaller_approx", line_ratio),
            ("changed_files_ratio_larger_to_smaller_approx", file_ratio),
            ("normalized_distance", distance),
        ):
            _must_equal_metric(v, r[k], k)
        computed = dict(time=days, line_ratio=line_ratio,
                        file_ratio=file_ratio, distance=distance)
        by_tier.setdefault((tier, relation), []).append(computed)
        for key, val in computed.items():
            metrics[key].append(val)
    require(tiers == {"A": expected_a, "B": expected_pairs-expected_a},
            "Frozen tier counts differ from source summary")
    require(not seen_positives.intersection(seen_controls),
            "A historical positive reused as a negative control")
    recorded = {
        "time": ("median_abs_time_days", "p90_abs_time_days"),
        "line_ratio": ("median_changed_lines_ratio", "p90_changed_lines_ratio"),
        "file_ratio": ("median_changed_files_ratio", "p90_changed_files_ratio"),
    }
    for key, (median_col, p90_col) in recorded.items():
        _must_equal_metric(_quantile(metrics[key], 0.5), str(original[median_col]),
                           "summary " + median_col)
        _must_equal_metric(_quantile(metrics[key], 0.9), str(original[p90_col]),
                           "summary " + p90_col)
    _must_equal_metric(tiers["A"]/expected_pairs,
                       str(original["same_repository_fraction"]),
                       "summary same_repository_fraction")
    balance_rows = _csv_rows(raw["balance"], {"metric", "median", "p90", "max"})
    require(len(balance_rows) == 4, "Balance must have precisely four metric rows")
    visited = set()
    for r in balance_rows:
        label = r["metric"]
        require(label in METRICS and label not in visited,
                "Unknown or duplicated C2 balance metric")
        visited.add(label)
        values = metrics[METRICS[label]]
        for col, target in (("median", _quantile(values, .5)),
                            ("p90", _quantile(values, .9)),
                            ("max", max(values))):
            _must_equal_metric(target, r[col], "balance " + label + ":" + col)
    require(visited == set(METRICS), "Missing C2 balance metrics")
    tier_rows = _csv_rows(raw["quality"], {
        "match_tier", "opportunity_relation", "pairs", "median_time_days",
        "median_line_ratio", "median_file_ratio", "median_distance",
    })
    require(len(tier_rows) == len(by_tier), "Quality group count mismatch")
    seen_groups = set()
    for r in tier_rows:
        key = (r["match_tier"], r["opportunity_relation"])
        require(key in by_tier and key not in seen_groups,
                "Missing/duplicate/unexpected tier quality group")
        seen_groups.add(key)
        vals = by_tier[key]
        require(_nonnegative_int(r["pairs"], "quality group size") == len(vals),
                "Tier group size differs")
        for field, metric in (("median_time_days", "time"),
                              ("median_line_ratio", "line_ratio"),
                              ("median_file_ratio", "file_ratio"),
                              ("median_distance", "distance")):
            _must_equal_metric(_quantile([v[metric] for v in vals], .5),
                               r[field], "quality " + field)
    require(seen_groups == set(by_tier), "Tier groups not fully represented")
    return {
        "status": "PASS_BYTE_VERIFIED_FROZEN_C2_SCORE_AND_CALIPER_ONLY",
        "verified_pair_rows": len(rows),
        "tier_a_same_repo": tiers["A"],
        "tier_b_cross_repo": tiers["B"],
        "opportunity_group_counts": {
            f"{tier}_{relation}": len(group)
            for (tier, relation), group in sorted(by_tier.items())
        },
        "median_abs_pr_time_days": _quantile(metrics["time"], .5),
        "median_changed_lines_ratio": _quantile(metrics["line_ratio"], .5),
        "median_changed_files_ratio": _quantile(metrics["file_ratio"], .5),
        "median_normalized_distance": _quantile(metrics["distance"], .5),
        "full_sha256_verified_for_all_four_original_inputs": True,
        "original_global_matching_optimizer_rerun": False,
        "eligible_candidate_counts_reproduced": False,
        "final_sqlite_authenticated": False,
        "security_outcomes_reproduced": False,
        "statistical_treatment_effects_reproduced": False,
        "note": "Matches recorded pair-score arithmetic and selected-pair metadata; no claim of optimizer optimality or security validity.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pairs", type=Path)
    parser.add_argument("summary", type=Path)
    parser.add_argument("balance", type=Path)
    parser.add_argument("quality", type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify_scores(args.pairs, args.summary, args.balance, args.quality)
        status = 0
    except (C2ScoreError, OSError, ValueError, KeyError, TypeError, csv.Error) as exc:
        result = {
            "status": "BLOCKED_C2_SOURCE_BYTES_OR_MATCH_METRICS",
            "error": str(exc),
            "historical_optimizer_rerun": False,
            "scientific_replication_complete": False,
        }
        status = 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return status



# A matching-cardinality certificate relative to the archived C2 eligibility counts.
# It cannot establish how those candidate counts were originally generated.
CANDIDATE_COUNTS_PIN = (
    13393, "6e4e09e7ac4b091a018b9bb55cfeab581fb67196159a729cf034e8851b728c8d",
)
CANDIDATE_COLUMNS = {
    "positive_case_id", "repository", "required_complete_opportunity_signature",
    "tier_a_same_repo_candidates", "tier_b_cross_repo_exact_candidates",
    "has_any_eligible_candidate",
}


def verify_candidate_cardinality(candidate_counts: Path, pairs: Path, *,
                                 candidate_pin: tuple[int, str] = CANDIDATE_COUNTS_PIN,
                                 pairs_pin: tuple[int, str] = FINGERPRINTS["pairs"],
                                 expected_positive_cases: int = 192,
                                 expected_pairs: int = 190,
                                 expected_tier_a: int = 115,
                                 expected_unmatched: tuple[str, ...] =
                                 ("13918", "17460")) -> dict:
    """Prove matched cardinality reaches the bound of frozen eligible positives.

    Test-only overrides cannot be provided via CLI. Original candidate generation,
    maximum Tier-A assignment and minimum-distance optimality are not rerun.
    """
    require(type(expected_positive_cases) is int and
            type(expected_pairs) is int and type(expected_tier_a) is int and
            0 < expected_pairs <= expected_positive_cases and
            0 <= expected_tier_a <= expected_pairs,
            "Invalid candidate-certificate denominator")
    original = _csv_rows(_file_bytes(candidate_counts, candidate_pin),
                         CANDIDATE_COLUMNS)
    selected = _csv_rows(_file_bytes(pairs, pairs_pin), PAIRS_REQUIRED)
    require(len(original) == expected_positive_cases and
            len(selected) == expected_pairs,
            "Frozen candidate/matched pair denominator changed")
    indexed = {}
    eligible = set()
    a_eligible, b_eligible, a_edges, b_edges = 0, 0, 0, 0
    for row in original:
        cid = row["positive_case_id"]
        require(cid.isascii() and cid.isdecimal() and str(int(cid)) == cid
                and cid not in indexed, "Duplicate or noncanonical candidate case")
        repository = row["repository"]
        require(bool(repository) and repository == repository.strip(),
                "Missing or altered candidate repository")
        _sig(row["required_complete_opportunity_signature"])
        ac = _nonnegative_int(row["tier_a_same_repo_candidates"], "Tier-A candidates")
        bc = _nonnegative_int(row["tier_b_cross_repo_exact_candidates"], "Tier-B candidates")
        flag = row["has_any_eligible_candidate"]
        require(flag in ("0", "1") and (flag == "1") == bool(ac + bc),
                "Candidate eligibility flag contradicts available controls")
        indexed[cid] = (row["repository"], row["required_complete_opportunity_signature"], ac, bc)
        if ac + bc:
            eligible.add(cid)
        a_eligible += ac > 0
        b_eligible += bc > 0
        a_edges += ac
        b_edges += bc
    used_positive, used_negative, tiers = set(), set(), {"A": 0, "B": 0}
    for row in selected:
        p, n = row["positive_case_id"], row["control_case_id"]
        require(p in indexed and p not in used_positive and n not in used_negative
                and p != n, "Selected case absent, duplicated, or self-matched")
        used_positive.add(p)
        used_negative.add(n)
        repo, signature, ac, bc = indexed[p]
        require(row["positive_repository"] == repo and
                row["positive_opportunity_signature"] == signature,
                "Selected positive differs from original candidate record")
        tier = row["match_tier"]
        require(tier in tiers, "Unknown selected candidate tier")
        tiers[tier] += 1
        require((ac if tier == "A" else bc) > 0,
                "Chosen matching tier has zero recorded eligible candidates")
    require(not used_positive.intersection(used_negative),
            "Historical positive reused as a negative control")
    missing = sorted(set(indexed) - used_positive, key=int)
    require(missing == list(expected_unmatched),
            "Unmatched positive set differs from source selection")
    require(len(eligible) == expected_pairs and used_positive == eligible and
            tiers == {"A": expected_tier_a, "B": expected_pairs - expected_tier_a},
            "Selected matching fails frozen maximum-cardinality bound")
    return {
        "status": "PASS_MAX_CARDINALITY_CONDITIONAL_ON_FROZEN_CANDIDATE_COUNTS",
        "positive_cases": len(indexed),
        "positives_with_eligible_candidates": len(eligible),
        "distinct_matched_positive_cases": len(used_positive),
        "distinct_matched_controls": len(used_negative),
        "unmatched_positive_count": len(missing),
        "unmatched_positive_case_ids": missing,
        "tier_a_selected": tiers["A"], "tier_b_selected": tiers["B"],
        "tier_a_candidate_eligible_positives": a_eligible,
        "tier_b_candidate_eligible_positives": b_eligible,
        "source_recorded_tier_a_candidate_edges": a_edges,
        "source_recorded_tier_b_candidate_edges": b_edges,
        "sha256_verified_for_both_original_inputs": True,
        "maximum_cardinality_proven_given_frozen_counts": True,
        "eligibility_counts_recomputed_from_c1": False,
        "global_matching_optimizer_rerun": False,
        "tier_a_optimality_reproduced": False,
        "minimum_total_distance_reproduced": False,
        "note": "Conditional combinatorial upper bound only; the source candidate generator is not rerun.",
    }


if __name__ == "__main__":
    sys.exit(main())
