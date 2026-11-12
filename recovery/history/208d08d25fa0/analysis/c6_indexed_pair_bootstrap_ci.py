"""Analytic pair-bootstrap distribution check using indexed paired categorical counts.

This computes *mathematical* percentiles for nonparametric IID resampling
of n matched-pair difference values in {-1, 0, +1}. The original C6 random
seed, number of resamples and exact percentile algorithm are unknown, so
agreement with its reported pair-bootstrap intervals is a consistency check,
NOT historical CI replication. Repository-blocked bootstraps are untouched.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "provenance" / "c6_indexed_main_pair_bootstrap_ci_20261022.json"
AGGREGATES = ROOT / "provenance" / "c6_c7_indexed_aggregate_matrices_20261022.json"


class IndexedBootstrapError(ValueError):
    """Fail closed when the indexed source or paired counts are inconsistent."""


def require(cond: bool, why: str) -> None:
    if not cond:
        raise IndexedBootstrapError(why)


def empirical_bootstrap_pmf(positive_only: int, control_only: int, neither_or_both: int) -> list[float]:
    """Exact empirical bootstrap PMF for n paired indicator differences.

    A replicate resamples n times with replacement from the n observed
    differences. PMF output index j represents (j-n) / n; there are 2n+1
    slots for integer differences -n...n. No Monte-Carlo randomness is used.
    """
    sizes = (positive_only, control_only, neither_or_both)
    require(all(type(k) is int and k >= 0 for k in sizes),
            "Invalid paired +1/-1/zero counts")
    n = sum(sizes)
    require(0 < n <= 500, "Invalid empirical bootstrap sample size")
    pm = control_only/n
    p0 = neither_or_both/n
    pp = positive_only/n
    state = [1.0]
    for length in range(1, n+1):
        nxt = [0.0] * (2*length+1)
        for j, probability in enumerate(state):
            if probability:
                nxt[j] += probability*pm
                nxt[j+1] += probability*p0
                nxt[j+2] += probability*pp
        state = nxt
    require(abs(sum(state)-1.0) < 1e-9 and
            all(math.isfinite(v) and v >= 0 for v in state),
            "Numerical bootstrap distribution unstable")
    return state


def quantile_of_signed_sum(pmf: list[float], q: float) -> int:
    """Discrete inverse-CDF quantile, expressed as signed count not rate."""
    require(isinstance(q, (float,int)) and math.isfinite(q) and 0 < q < 1,
            "Invalid quantile level")
    require(len(pmf) > 1 and len(pmf)%2 == 1 and
            abs(sum(pmf)-1.0) < 1e-9, "Invalid signed-count PMF")
    n = (len(pmf)-1)//2
    cdf = 0.0
    for index, value in enumerate(pmf):
        cdf += value
        if cdf >= q:
            return index - n
    raise IndexedBootstrapError("Cannot locate a valid bootstrap quantile")


def paired_difference_counts(counts: list[list[int]], i: int) -> tuple[int,int,int]:
    n = len(counts)
    require(n >= 2 and type(i) is int and 0 <= i < n and
            all(isinstance(row,list) and len(row)==n and
                all(type(v) is int and v >= 0 for v in row) for row in counts),
            "Paired categorical matrix malformed")
    total = sum(map(sum,counts))
    pos_only = sum(counts[i]) - counts[i][i]
    ctrl_only = sum(counts[j][i] for j in range(n)) - counts[i][i]
    both_neither = total-pos_only-ctrl_only
    require(total > 0 and both_neither >= 0, "Invalid categorical counts")
    return pos_only,ctrl_only,both_neither


def replay(*, source: dict | None = None, aggregates: dict | None = None) -> dict:
    source = json.loads(SOURCE.read_text()) if source is None else source
    aggregates = json.loads(AGGREGATES.read_text()) if aggregates is None else aggregates
    require(source.get("schema_version")==1 and source.get("status")==
            "INDEXED_SOURCE_REPORTED_PAIR_BOOTSTRAP_CI_NOT_SOURCE_BYTE_AUTHENTICATED",
            "Unknown source provenance status")
    require(source["original_source_C6_file_bytes_authenticated"] is False and
            source["original_repository_blocked_CIs_recomputed"] is False and
            source["historical_bootstrap_draws_and_seed_known"] is False and
            source["historical_replicate_percentile_algorithm_known"] is False,
            "Historical source/seed/repository bootstrap claim unsupported")
    require(aggregates.get("scientific_limits",{}).get("staged_original_C6_C7_csv_sha256_verified") is False,
            "Original staged-source status unexpectedly changed")
    entries=source["source_reported_rows"]
    expected_keys = {("Instruction specificity","Explicit instruction"),
                     ("Instruction specificity","Suggests solution"),
                     ("Goal alignment","Aligned")}
    keys={(x["variable"],x["category"]) for x in entries}
    require(len(entries)==3 and keys==expected_keys,"Expected three frozen category CI checks")
    report=[]
    for value in entries:
        variable,cat=value["variable"],value["category"]
        table=aggregates["primary_categorical"][variable]
        i=table["categories"].index(cat)
        plus,minus,zero=paired_difference_counts(table["counts"],i)
        n=plus+minus+zero
        p=sum(table["counts"][i]);c=sum(row[i] for row in table["counts"])
        require(n==value["n_pairs"]==190 and p==value["positive_count"] and c==value["control_count"],
                "Source-reported category margin changed")
        distribution=empirical_bootstrap_pmf(plus,minus,zero)
        lo,hi=[100*quantile_of_signed_sum(distribution,q)/n for q in (.025,.975)]
        reported=(value["source_reported_pair_boot_ci95_low_pp"],
                  value["source_reported_pair_boot_ci95_high_pp"])
        require(all(type(z) in (float,int) and math.isfinite(z) for z in reported) and
                reported[0] <= reported[1],"Malformed historical CI")
        diff=[abs(lo-reported[0]),abs(hi-reported[1])]
        tolerance=100/n+1e-9
        require(max(diff)<=tolerance,"Analytic bootstrap percentile differs by over one 190-pair increment")
        report.append({"variable":variable,"category":cat,"pairs":n,
                       "positive_only_pairs":plus,"control_only_pairs":minus,
                       "both_or_neither_pairs":zero,
                       "observed_paired_difference_pp":100*(plus-minus)/n,
                       "analytic_resampling_ci95_pp":[lo,hi],
                       "source_reported_pair_bootstrap_ci95_pp":list(reported),
                       "endpoint_absolute_deviations_pp":diff,
                       "match_within_one_discrete_pair_increment":True})
    return {
        "status":"PASS_INDEXED_C6_ANALYTIC_PAIR_BOOTSTRAP_DISTRIBUTION_CHECK_ONLY",
        "categories_checked":len(report),
        "comparisons":report,
        "analytic_quantiles_computed_without_random_draws":True,
        "source_ci_method_exactly_reproduced":False,
        "original_C6_source_sha256_verified":False,
        "original_repository_blocked_CIs_reproduced":False,
        "original_case_level_paired_coding_authenticated":False,
        "causal_interpretation_supported":False,
    }


def main(argv: list[str] | None=None) -> int:
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.parse_args(argv)
    try:
        result,code=replay(),0
    except (IndexedBootstrapError,KeyError,OSError,TypeError,ValueError) as exc:
        result,code={"status":"BLOCKED_INDEXED_C6_PAIR_BOOTSTRAP_CHECK",
                     "reason":str(exc),"historical_CI_reproduced":False},2
    print(json.dumps(result,indent=2,sort_keys=True))
    return code


if __name__=="__main__":
    sys.exit(main())
