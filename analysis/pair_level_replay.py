"""Reproduce all nine primary C6 paired tests from the ORIGINAL 190-pair CSV.

Five marginal-homogeneity and three exact-McNemar tests are recalculated
from the aggregate tables. This code replays all nine, including
Wilcoxon and original missing-data exclusions, when an authorized ORIGINAL
raw CSV is staged locally (original file-size gate + new SHA256 output).

No raw C6 master is included in this repo. CI tests are purely synthetic.
Indexed Library TEXT is not byte-level source authentication; an original
source SHA-256 anchor is still needed for final release. Do not interpret
observational paired associations as causal effects of issuing instructions.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import median

ORIGINAL_SIZE = 98431
ORIGINAL_PAIRS = 190
EXPECTED = {
    "Issue purpose": (190, 0.0971925657089748),
    "Instruction specificity": (190, 0.000520117009904),
    "Goal alignment": (190, 0.0010186743792719),
    "Implementation category": (190, 0.1195235832394017),
    "Formal human review before merge": (189, 0.4187541882690154),
    "Issue→PR creation delay (hours)": (190, 0.2412317385974189),
    "Same issue/PR author": (190, 1.0),
    "Any requester prior repo activity": (187, 0.3355576182340152),
    "Primary agent/tool": (190, 0.2190106974324261),
}
CATEGORY_COLS = {
    "Issue purpose": ("positive_issue_purpose", "control_issue_purpose"),
    "Instruction specificity": (
        "positive_instruction_specificity", "control_instruction_specificity"
    ),
    "Goal alignment": ("positive_goal_alignment", "control_goal_alignment"),
    "Implementation category": (
        "positive_implementation_pattern", "control_implementation_pattern"
    ),
    "Primary agent/tool": ("positive_primary_agent_tool", "control_primary_agent_tool"),
}
BINARY_COLS = {
    "Formal human review before merge": (
        "positive_human_review", "control_human_review"
    ),
    "Same issue/PR author": (
        "positive_same_issue_pr_author", "control_same_issue_pr_author"
    ),
    "Any requester prior repo activity": (
        "positive_any_prior_repo_activity", "control_any_prior_repo_activity"
    ),
}


class PairedReplayError(ValueError):
    """Original cohort, provenance, missingness or exact-test mismatch."""


def require(cond: bool, message: str) -> None:
    if not cond:
        raise PairedReplayError(message)


def solve(A: list[list[float]], b: list[float]) -> list[float]:
    n = len(b)
    require(len(A) == n and all(len(row) == n for row in A),
            "Malformed categorical covariance")
    M = [list(map(float, row)) + [float(b[i])] for i, row in enumerate(A)]
    for j in range(n):
        pivot = max(range(j, n), key=lambda i: abs(M[i][j]))
        require(abs(M[pivot][j]) > 1e-10,
                "Singular Stuart-Maxwell covariance; inspect category support")
        M[j], M[pivot] = M[pivot], M[j]
        div = M[j][j]
        for c in range(j, n + 1):
            M[j][c] /= div
        for i in range(n):
            if i == j:
                continue
            factor = M[i][j]
            for c in range(j, n + 1):
                M[i][c] -= factor*M[j][c]
    return [row[n] for row in M]


def chisq_sf(chisq: float, df: int) -> float:
    require(df >= 1 and chisq >= -1e-9,
            "Invalid degrees of freedom or negative chi-square")
    z = max(0.0, chisq) / 2
    if df % 2 == 0:
        v, total = 1.0, 1.0
        for j in range(1, df // 2):
            v *= z/j
            total += v
        return min(1.0, math.exp(-z)*total)
    tail = math.erfc(math.sqrt(z))
    for j in range((df-1)//2):
        s = j + 0.5
        tail += math.exp(-z)*z**s/math.gamma(s+1)
    return min(1.0, tail)


def stuart_maxwell(pairs: list[dict], pa: str, ca: str) -> dict:
    cats = sorted({r[column] for r in pairs for column in (pa, ca)})
    require(all(cats) and len(cats) > 1,
            "Cannot analyze missing/single-category original pair labels")
    index = {cat:i for i,cat in enumerate(cats)}
    k = len(cats)
    counts = [[0]*k for _ in range(k)]
    for row in pairs:
        counts[index[row[pa]]][index[row[ca]]] += 1
    n = sum(map(sum, counts))
    pr = list(map(sum, counts))
    ct = [sum(counts[i][j] for i in range(k)) for j in range(k)]
    d = [pr[i]-ct[i] for i in range(k)]
    cov = [[(pr[i]+ct[i]-2*counts[i][i] if i==j else
             -(counts[i][j]+counts[j][i])) for j in range(k-1)]
           for i in range(k-1)]
    sol = solve(cov, d[:k-1])
    statistic = sum(d[i]*sol[i] for i in range(k-1))
    agreement = sum(counts[i][i] for i in range(k))/n
    return {
        "test":"Stuart-Maxwell marginal homogeneity", "n":n, "df":k-1,
        "statistic": statistic, "p_value": chisq_sf(statistic,k-1),
        "effect_name":"Total variation distance",
        "effect_value": sum(abs(v) for v in d)/(2*n),
        "agreement":agreement,
        "categories":cats,
        "contingency":counts,
    }


def binom_exact_mcnemar(b: int, c: int) -> float:
    require(min(b,c) >= 0, "Negative discordant pair count")
    n = b+c
    if n == 0:
        return 1.0
    term = 2.0**(-n)
    tail = term
    for j in range(1, min(b,c)+1):
        term *= (n-j+1)/j
        tail += term
    return min(1.0, 2*tail)


def binary_mcnemar(pairs: list[dict], pa: str, ca: str) -> dict:
    eligible = [r for r in pairs if r[pa] in ("Yes","No")
                and r[ca] in ("Yes","No")]
    YY = sum(r[pa]=="Yes" and r[ca]=="Yes" for r in eligible)
    YN = sum(r[pa]=="Yes" and r[ca]=="No" for r in eligible)
    NY = sum(r[pa]=="No" and r[ca]=="Yes" for r in eligible)
    NN = sum(r[pa]=="No" and r[ca]=="No" for r in eligible)
    n = len(eligible)
    require(YY+YN+NY+NN == n and n > 0, "Empty/corrupt paired binary labels")
    return {
        "test":"Exact McNemar", "n":n,
        "p_value":binom_exact_mcnemar(YN,NY),
        "both_yes":YY, "positive_only_yes":YN, "control_only_yes":NY,
        "both_no":NN, "positive_yes":YY+YN, "control_yes":YY+NY,
        "effect_name":"Matched rate difference","effect_value":(YN-NY)/n,
        "agreement":(YY+NN)/n,
        "excluded_pair_ids":[int(r["pair_index"]) for r in pairs
                             if r[pa] not in ("Yes","No") or
                                r[ca] not in ("Yes","No")],
    }


def wilcoxon_delay(pairs: list[dict]) -> dict:
    try:
        diffs = [float(r["positive_issue_to_pr_delay_hours"]) -
                 float(r["control_issue_to_pr_delay_hours"]) for r in pairs]
    except ValueError as e:
        raise PairedReplayError("Original delay hours missing/not numeric") from e
    require(all(math.isfinite(v) for v in diffs),
            "Non-finite original paired issue→PR delays")
    nonzero = sorted([(abs(x),x) for x in diffs if x!=0],key=lambda t:t[0])
    n = len(nonzero)
    require(n > 0, "All Wilcoxon paired differences are zero")
    positive_rank = 0.0
    ties = []
    i=0
    while i<n:
        j=i+1
        while j<n and nonzero[j][0]==nonzero[i][0]:
            j+=1
        rank=(i+1+j)/2
        positive_rank+=rank*sum(nonzero[k][1]>0 for k in range(i,j))
        if j-i>1:
            ties.append(j-i)
        i=j
    negative_rank=n*(n+1)/2-positive_rank
    mean=n*(n+1)/4
    variance=n*(n+1)*(2*n+1)/24-sum(t**3-t for t in ties)/48
    require(variance>0,"Degenerate original Wilcoxon variance")
    z=(positive_rank-mean)/math.sqrt(variance)
    p=math.erfc(abs(z)/math.sqrt(2))
    return {
        "test":"Wilcoxon signed-rank asymptotic two-sided (no continuity correction)",
        "n":len(diffs),"nonzero":n,"zero_differences":len(diffs)-n,
        "positive_rank_sum":positive_rank,"negative_rank_sum":negative_rank,
        "z":z,"p_value":p,
        "effect_name":"Median paired difference hours",
        "effect_value":median(diffs),
        "tie_group_sizes":ties,
    }


def audit_original(path: Path, strict: bool = True) -> dict:
    require(path.is_file() and not path.is_symlink(),
            "Original master must be an approved ordinary local file")
    require(path.stat().st_size == ORIGINAL_SIZE,
            "Original frozen 190-pair source-size mismatch")
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    try:
        lines = raw.decode("utf-8-sig").splitlines(keepends=True)
        pairs = list(csv.DictReader(lines))
    except (UnicodeError,csv.Error) as e:
        raise PairedReplayError("Cannot parse original C6 paired master CSV") from e
    require(len(pairs)==ORIGINAL_PAIRS and
            all(None not in row for row in pairs),
            "Original C6 must contain exactly 190 intact paired rows")
    require({int(r["pair_index"]) for r in pairs} == set(range(1,191)) and
            len({r["positive_case_id"] for r in pairs})==190 and
            len({r["control_case_id"] for r in pairs})==190,
            "Frozen C2 matching population or one-to-one pair IDs changed")
    require(sum(r["same_repository_match"]=="1" for r in pairs)==115,
            "Original 115 same-repository C2 match membership changed")
    output={}
    for name,(pa,ca) in CATEGORY_COLS.items():
        output[name]=stuart_maxwell(pairs,pa,ca)
    for name,(pa,ca) in BINARY_COLS.items():
        output[name]=binary_mcnemar(pairs,pa,ca)
    output["Issue→PR creation delay (hours)"]=wilcoxon_delay(pairs)
    for variable,(n,expected_p) in EXPECTED.items():
        result=output[variable]
        require(result["n"]==n, "Original complete-case n mismatch: "+variable)
        if strict:
            require(abs(result["p_value"]-expected_p)<1e-7,
                    "Original paired hypothesis statistic/p-value drift: "+variable)
    return {
        "status":"PASS_ORIGINAL_FULL_C6_PAIRED_190_NINE_TESTS" if strict else
                 "PASS_ORIGINAL_C6_190_PAIRED_ROWS_NO_EXPECTED_P_ASSERTION",
        "original_190_CSV_bytes_rehashed_this_run": True,
        "raw_original_C6_SHA256_newly_observed":digest,
        "original_C6_trusted_archival_SHA256_available": False,
        "source_bytes":len(raw),"n_pairs":len(pairs),
        "n_same_repository_pairs":115,
        "p_values_all_nine_checked_against_original_report":strict,
        "original_historical_bootstrap_CIs_rerun":False,
        "scanner_warnings_established_as_exploitable":False,
        "observational_differences_establish_causation":False,
        "comparisons":output,
    }


def main(argv: list[str] | None = None) -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--original-pair-master",required=True,type=Path,
                    help="Approved original C6_MATCHED_PAIR_MASTER_190.csv")
    args=ap.parse_args(argv)
    print(json.dumps(audit_original(args.original_pair_master),
                     sort_keys=True,indent=2,ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
