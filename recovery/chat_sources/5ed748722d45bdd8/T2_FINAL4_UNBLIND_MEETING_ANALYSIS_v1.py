#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, json, tarfile
from collections import defaultdict
from pathlib import Path

ROOT = Path.home() / "research_artifacts"
TASK = ROOT / "T2_FINAL4_BLIND_TASK_M_FREEZE_v1.csv"
EXPECTED_TASK_SHA = "636ed943c7160a8aab58f26570a5b3366ac574ab63737c31a168781e5b64280b"

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()

def load_run_maps():
    out = {}
    for s in range(4):
        p = ROOT / f"T2_FINAL5_PACKET_BUILD_v2_S{s}_SEALED.tar.gz"
        if not p.exists():
            raise SystemExit(f"MISSING {p}")
        with tarfile.open(p, "r:gz") as tf:
            m = next(x for x in tf.getmembers()
                     if x.isfile() and x.name.endswith("/RUN_MAP.json"))
            obj = json.loads(tf.extractfile(m).read().decode("utf-8"))
            for run_id, meta in obj.items():
                if run_id in out:
                    raise SystemExit(f"DUPLICATE RUN {run_id}")
                out[run_id] = {
                    "pair_id": meta["pair_id"],
                    "role": meta["role"],
                    "x_exposed": bool(meta["x_exposed"]),
                    "rep": int(meta["rep"]),
                }
    return out

def load_scanner():
    rows = {}
    for s in range(8):
        p = ROOT / f"T2_FINAL4_CODEQL_PUBLIC_v1_S{s}.json"
        if not p.exists():
            raise SystemExit(f"MISSING {p}")
        obj = json.loads(p.read_text())
        for r in obj["runs"] if "runs" in obj else []:
            rid = r["run_id"]
            if rid in rows:
                raise SystemExit(f"DUPLICATE SCANNER RUN {rid}")
            rows[rid] = r

    # Older public JSONs from the scanner script store only aggregate fields,
    # so recover per-run public rows from job logs if needed.
    if len(rows) != 32:
        import re, glob
        log_rows = {}
        for fp in glob.glob(str(ROOT / "T2_FINAL4_CODEQL_BLIND_v1_*.out")):
            txt = Path(fp).read_text(errors="ignore")
            # Keep latest successful public observation per run. Never use sealed details.
            for line in txt.splitlines():
                m = re.match(
                    r"^(RUN_\d{3}) scanner_valid=(\d) scanner_positive=(True|False)"
                    r"(?: target_count=(\d+))? status=([A-Z_]+)$", line.strip()
                )
                if m:
                    rid, valid, pos, count, status = m.groups()
                    log_rows[rid] = {
                        "run_id": rid,
                        "scanner_valid": valid == "1",
                        "scanner_positive": pos == "True",
                        "target_finding_count": int(count or 0),
                        "status": status,
                    }
        rows = log_rows
    return rows

if not TASK.exists():
    raise SystemExit(f"MISSING {TASK}")
if sha256_file(TASK) != EXPECTED_TASK_SHA:
    raise SystemExit("TASK_FREEZE_HASH_MISMATCH")

task = {}
with TASK.open(newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        task[r["run_id"]] = r

run_map = load_run_maps()
scanner = load_scanner()

expected = set(run_map)
if len(expected) != 32:
    raise SystemExit(f"EXPECTED_32_RUNS_IN_SEALED_MAP_GOT={len(expected)}")
if set(task) != expected:
    raise SystemExit("TASK_RUN_SET_MISMATCH")
if set(scanner) != expected:
    missing = sorted(expected - set(scanner))
    extra = sorted(set(scanner) - expected)
    raise SystemExit(f"SCANNER_RUN_SET_MISMATCH missing={missing} extra={extra}")

invalid = sorted(r for r in expected if not scanner[r].get("scanner_valid"))
if invalid:
    raise SystemExit(f"SCANNER_NOT_FULLY_FROZEN invalid={invalid}")

rows = []
for rid in sorted(expected):
    m = run_map[rid]
    t = task[rid]
    s = scanner[rid]
    condition = ("P" if m["role"] == "positive" else "N") + ("+" if m["x_exposed"] else "-")
    rows.append({
        "run_id": rid,
        "pair_id": m["pair_id"],
        "condition": condition,
        "rep": m["rep"],
        "task_pass": t["blind_task_alignment"] == "PASS",
        "M_selected": t["blind_mechanism_M_selected"] == "YES",
        "scanner_positive": bool(s["scanner_positive"]),
    })

# Freeze public run-level outcomes after unblinding. No repo/rule/path details included.
run_csv = ROOT / "T2_FINAL4_UNBLINDED_RUN_OUTCOMES_v1.csv"
with run_csv.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

conditions = ["P-", "P+", "N-", "N+"]
summary = {}
for c in conditions:
    rr = [x for x in rows if x["condition"] == c]
    summary[c] = {
        "n": len(rr),
        "task_pass": sum(x["task_pass"] for x in rr),
        "M_selected": sum(x["M_selected"] for x in rr),
        "scanner_positive": sum(x["scanner_positive"] for x in rr),
    }

pair_ids = sorted({x["pair_id"] for x in rows})
pair_table = []
for pid in pair_ids:
    prow = {"pair_id": pid}
    for c in conditions:
        rr = [x for x in rows if x["pair_id"] == pid and x["condition"] == c]
        if len(rr) != 2:
            raise SystemExit(f"EXPECTED_2_REPS {pid} {c} got {len(rr)}")
        prow[c] = {
            "task": sum(x["task_pass"] for x in rr),
            "M": sum(x["M_selected"] for x in rr),
            "scanner": sum(x["scanner_positive"] for x in rr),
        }
    pair_table.append(prow)

def effect(endpoint):
    p_plus = summary["P+"][endpoint] / summary["P+"]["n"]
    p_minus = summary["P-"][endpoint] / summary["P-"]["n"]
    n_plus = summary["N+"][endpoint] / summary["N+"]["n"]
    n_minus = summary["N-"][endpoint] / summary["N-"]["n"]
    return {
        "positive_ablation_Pplus_minus_Pminus": p_plus - p_minus,
        "negative_addition_Nplus_minus_Nminus": n_plus - n_minus,
    }

effects = {
    "task_pass": effect("task_pass"),
    "M_selected": effect("M_selected"),
    "scanner_positive": effect("scanner_positive"),
}

directional = {}
for endpoint_key, cell_key in [
    ("task_pass", "task"),
    ("M_selected", "M"),
    ("scanner_positive", "scanner"),
]:
    directional[endpoint_key] = {
        "positive_pairs_Pplus_gt_Pminus": sum(p["P+"][cell_key] > p["P-"][cell_key] for p in pair_table),
        "positive_pairs_equal": sum(p["P+"][cell_key] == p["P-"][cell_key] for p in pair_table),
        "positive_pairs_Pplus_lt_Pminus": sum(p["P+"][cell_key] < p["P-"][cell_key] for p in pair_table),
        "negative_pairs_Nplus_gt_Nminus": sum(p["N+"][cell_key] > p["N-"][cell_key] for p in pair_table),
        "negative_pairs_equal": sum(p["N+"][cell_key] == p["N-"][cell_key] for p in pair_table),
        "negative_pairs_Nplus_lt_Nminus": sum(p["N+"][cell_key] < p["N-"][cell_key] for p in pair_table),
    }

result = {
    "version": "T2_FINAL4_MEETING_RESULT_v1",
    "design": {
        "independent_pairs": len(pair_ids),
        "replicates_per_cell": 2,
        "runs": len(rows),
        "conditions": conditions,
    },
    "condition_counts": summary,
    "pair_table": pair_table,
    "effects": effects,
    "pair_direction_counts": directional,
    "caveats": [
        "Pilot-sized bidirectional replay: four independent matched pairs.",
        "Task outcome is blinded implementation-alignment adjudication, not repository-level functional/build-test validation.",
        "Scanner outcome was frozen before condition unblinding.",
        "No population-wide causal generalization should be claimed from four pairs."
    ],
}
json_out = ROOT / "T2_FINAL4_MEETING_RESULT_v1.json"
json_out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

def pct(k, c):
    n = summary[c]["n"]
    return 100.0 * summary[c][k] / n if n else float("nan")

lines = []
lines.append("T2 FINAL4 BIDIRECTIONAL REPLAY — MEETING RESULT")
lines.append("=" * 54)
lines.append(f"Design: {len(pair_ids)} independent pairs × 4 cells × 2 reps = {len(rows)} runs")
lines.append("")
lines.append("CELL COUNTS")
for c in conditions:
    x = summary[c]
    lines.append(
        f"{c}: n={x['n']} | task={x['task_pass']}/{x['n']} ({pct('task_pass',c):.1f}%)"
        f" | M={x['M_selected']}/{x['n']} ({pct('M_selected',c):.1f}%)"
        f" | scanner+={x['scanner_positive']}/{x['n']} ({pct('scanner_positive',c):.1f}%)"
    )
lines.append("")
lines.append("CAUSAL CONTRASTS (percentage points; descriptive pilot)")
for endpoint, e in effects.items():
    lines.append(
        f"{endpoint}: P+−P−={100*e['positive_ablation_Pplus_minus_Pminus']:+.1f} pp"
        f" | N+−N−={100*e['negative_addition_Nplus_minus_Nminus']:+.1f} pp"
    )
lines.append("")
lines.append("PAIR-LEVEL (counts out of 2 reps)")
for p in pair_table:
    lines.append(
        f"{p['pair_id']}: "
        + " | ".join(
            f"{c}[task={p[c]['task']},M={p[c]['M']},scan={p[c]['scanner']}]"
            for c in conditions
        )
    )
lines.append("")
lines.append("IMPORTANT: task endpoint is blind implementation alignment, not full repository functional validation.")
txt_out = ROOT / "T2_FINAL4_MEETING_RESULT_v1.txt"
txt_out.write_text("\n".join(lines) + "\n", encoding="utf-8")

print(txt_out.read_text())
print("RUN_CSV_SHA256=", sha256_file(run_csv))
print("RESULT_JSON_SHA256=", sha256_file(json_out))
print("RESULT_TXT_SHA256=", sha256_file(txt_out))
