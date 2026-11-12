"""Reproduce eight paired C6 tests from supplied aggregate sufficient statistics.

The ninth test (issue-to-PR delay) is reported from the historical results; its
paired signed observations are not included and cannot be inferred from margins.
No personal/repository case data, external packages or network access required.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "c6_matched_tables.json"

def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)

def solve(matrix: list[list[float]], values: list[float]) -> list[float]:
    n = len(values)
    a = [list(map(float, matrix[i])) + [float(values[i])] for i in range(n)]
    for j in range(n):
        pivot = max(range(j, n), key=lambda k: abs(a[k][j]))
        require(abs(a[pivot][j]) > 1e-10, "Singular Stuart-Maxwell covariance")
        a[j], a[pivot] = a[pivot], a[j]
        divisor = a[j][j]
        for k in range(j, n + 1):
            a[j][k] /= divisor
        for i in range(n):
            if i == j:
                continue
            factor = a[i][j]
            for k in range(j, n + 1):
                a[i][k] -= factor * a[j][k]
    return [r[-1] for r in a]

def chi2_survival(statistic: float, df: int) -> float:
    require(statistic >= 0 and df > 0, "Invalid chi-square distribution")
    z = statistic / 2
    if df % 2 == 0:
        term = total = 1.0
        for j in range(1, df // 2):
            term *= z / j
            total += term
        return math.exp(-z) * total
    total = math.erfc(math.sqrt(z))
    for j in range((df - 1) // 2):
        s = j + .5
        total += math.exp(-z) * z ** s / math.gamma(s + 1)
    return min(1., total)

def stuart_maxwell(counts: list[list[int]]) -> dict:
    k = len(counts)
    require(k > 1 and all(len(r) == k for r in counts), "Non-square contingency")
    require(all(isinstance(v, int) and v >= 0 for r in counts for v in r),
            "Invalid categorical counts")
    n = sum(map(sum, counts))
    positive = [sum(r) for r in counts]
    control = [sum(counts[i][j] for i in range(k)) for j in range(k)]
    d = [positive[i] - control[i] for i in range(k)]
    cov = [[positive[i] + control[i] - 2 * counts[i][i] if i == j
            else -(counts[i][j] + counts[j][i])
            for j in range(k - 1)] for i in range(k - 1)]
    solution = solve(cov, d[:k-1])
    chi2 = sum(d[i] * solution[i] for i in range(k-1))
    return {"pairs": n, "statistic": chi2, "p_value": chi2_survival(chi2, k-1),
            "effect": sum(abs(x) for x in d)/(2*n), "df": k-1, "kind": "TVD"}

def exact_mcnemar(table: dict) -> dict:
    yy = table["both_yes"]
    b = table["positive_only_yes"]
    c = table["control_only_yes"]
    nn = table["both_no"]
    n = yy+b+c+nn
    require(n > 0 and n == table["complete_pairs"], "Invalid binary pair table")
    discordant = b+c
    if discordant == 0:
        p = 1.
    else:
        term = 2.**(-discordant)
        tail = term
        for j in range(1, min(b,c)+1):
            term *= (discordant-j+1)/j
            tail += term
        p = min(1., 2*tail)
    return {"pairs": n, "p_value": p, "effect": (b-c)/n, "kind": "Rate difference",
            "discordant_positive_only": b, "discordant_control_only": c}

def holm_adjust(raw: dict[str, float]) -> dict[str, float]:
    order = sorted(raw, key=raw.__getitem__)
    output = {}
    maximum = 0.
    for i, name in enumerate(order):
        maximum = max(maximum, min(1., raw[name] * (len(order)-i)))
        output[name] = maximum
    return output

def replay(path: Path = DATA, *, check: bool = False) -> list[dict]:
    source = json.loads(path.read_text(encoding="utf-8"))
    require(source["matched_pairs"] == 190, "Unexpected study pair denominator")
    require(source["same_repository_pairs"] == 115 and
            source["cross_repository_pairs"] == 75, "Matching split changed")
    raw_p: dict[str, float] = {}
    results: dict[str, dict] = {}
    for name, item in source["categorical"].items():
        result = stuart_maxwell(item["counts"])
        require(result["pairs"] == 190 and len(item["categories"]) == len(item["counts"]),
                "Categorical pair denominator/category mapping drift")
        results[name] = result
        raw_p[name] = result["p_value"]
    for name, item in source["binary"].items():
        results[name] = exact_mcnemar(item)
        raw_p[name] = results[name]["p_value"]
    reported = source["delay_reported"]
    delay = reported["name"]
    require(reported["replayed_from_aggregate"] is False,
            "Do not claim Wilcoxon was replayed from marginals")
    results[delay] = {"pairs": reported["complete_pairs"], "p_value": reported["p_value"],
                      "effect": reported["median_paired_difference_hours"],
                      "kind": "Median hours", "source": "historical report"}
    raw_p[delay] = reported["p_value"]
    require(set(results) == set(source["comparison_order"]) ==
            set(source["historical_pvalues"]) and len(results) == 9,
            "Nine-test family changed")
    adjusted = holm_adjust(raw_p)
    output = []
    for name in source["comparison_order"]:
        result = dict(results[name])
        result.update({"variable": name, "holm_p": adjusted[name],
                       "source": result.get("source", "aggregate replay")})
        if check:
            expected = source["historical_pvalues"][name]
            require(abs(result["p_value"] - expected) < 1e-8,
                    f"Historical paired test mismatch: {name}")
        output.append(result)
    return output

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="Assert all nine p-values match the historical report")
    parser.add_argument("--json", action="store_true", help="Print JSON")
    args = parser.parse_args()
    rows = replay(check=args.check)
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
    else:
        print("Matched issue–PR analysis (190 pairs; eight tests replayed, delay reported)")
        print(f"{'Comparison':40} {'N':>3} {'Effect':>10} {'p':>11} {'Holm':>11}")
        for r in rows:
            print(f"{r['variable'][:40]:40} {r['pairs']:3d} "
                  f"{r['effect']:10.6f} {r['p_value']:11.8f} {r['holm_p']:11.8f}")
        print("Note: delay p-value is historical; source raw files are not bundled.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
