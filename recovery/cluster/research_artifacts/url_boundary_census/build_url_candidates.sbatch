#!/bin/bash
#SBATCH --job-name=urlcand
#SBATCH --partition=batch
#SBATCH --time=00:10:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/url_boundary_census/url_candidates.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/url_boundary_census/url_candidates.err

set -euo pipefail

python3 - <<'PY'
from pathlib import Path
import csv, sqlite3, json, re, zipfile, hashlib
from collections import defaultdict, Counter

HOME = Path.home()
OUT = HOME / "research_artifacts/url_boundary_census"
D = HOME / "research_artifacts/D_COMPLETE_ROOT_PROVENANCE_v1_0"

ROOTS = D / "01_INPUT/C6_ROOT_CENSUS.csv"
XWALK = D / "01_INPUT/D1_ROOT_PC_EVIDENCE_CROSSWALK_455.csv"

DB = Path(
    "/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/"
    "data/final-study-snapshot-20260829/"
    "full3809-scanner-complete-20260829.db"
)

with ROOTS.open(newline="", encoding="utf-8-sig") as f:
    roots = {r["Root ID"]: r for r in csv.DictReader(f)}

with XWALK.open(newline="", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

byroot = defaultdict(list)
for r in rows:
    byroot[r["C_Root ID"]].append(r)

assert len(roots) == 342
assert len(byroot) == 342

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

def issue(case_id):
    r = con.execute("""
        SELECT i.title, i.body, i.url
        FROM cases c
        JOIN issues i ON i.id = c.issue_id
        WHERE c.id = ?
    """, (int(case_id),)).fetchone()
    return dict(r) if r else {}

def uniq(rows, col):
    return " || ".join(dict.fromkeys(
        str(r.get(col) or "").strip()
        for r in rows
        if str(r.get(col) or "").strip()
    ))

# Strong scanner-side indicators of URL/host identity/boundary logic.
rule_re = re.compile(
    r"(incomplete-url|hostname|host-name|url-substring|"
    r"request-forgery|ssrf|url-redirection|open-redirect)",
    re.I,
)

# Semantic terms. We intentionally do NOT search for http/https.
boundary_re = re.compile(
    r"\b(url|uri|hostname|host name|domain|origin|destination|"
    r"allowed host|trusted host|provider host|endpoint)\b",
    re.I,
)

# Consequential operations rather than merely displaying/parsing a URL.
operation_re = re.compile(
    r"\b(fetch|request|redirect|navigate|open|load|connect|download|"
    r"upload|proxy|provider|authorize|authorise|allow|deny|"
    r"accept|reject|access|send)\b",
    re.I,
)

# Concrete validation/recognition mechanism language.
validation_re = re.compile(
    r"\b(validate|validation|check|match|recognize|recognise|"
    r"filter|sanitize|sanitise|allowlist|whitelist|denylist|"
    r"substring|includes|regex|regexp|parse)\b",
    re.I,
)

records = []

for rid, root in roots.items():
    rr = byroot[rid]

    case_id = root["Case ID"]
    iss = issue(case_id)

    rules = uniq(rr, "PROV_Rule ID(s)")
    fams = uniq(rr, "PROV_Finding Family")
    mech = uniq(rr, "PROV_Security-Relevant Mechanism")
    change = uniq(rr, "PROV_Finding-Producing Change")
    goal = uniq(rr, "PROV_Requested Goal Set")
    goal_ev = uniq(rr, "PROV_Goal Evidence")
    diff_ev = uniq(rr, "PROV_Diff Evidence")
    a_labels = uniq(rr, "Effective A Label")
    b_labels = uniq(rr, "Effective B Label")

    # Keep source-code vulnerability roots only.
    fam_lower = fams.lower()
    if "code vulnerability" not in fam_lower:
        continue

    issue_title = iss.get("title") or ""
    issue_body = iss.get("body") or ""

    mechanism_text = " ".join([
        root.get("Root Summary", ""),
        root.get("Subproblem", ""),
        root.get("Shared Strategy", ""),
        mech,
        change,
    ])

    upstream_text = " ".join([
        issue_title,
        issue_body,
        goal,
        goal_ev,
    ])

    rule_hit = bool(rule_re.search(rules))
    mechanism_boundary = bool(boundary_re.search(mechanism_text))
    mechanism_validation = bool(validation_re.search(mechanism_text))
    mechanism_operation = bool(operation_re.search(mechanism_text))

    upstream_boundary = bool(boundary_re.search(upstream_text))
    upstream_operation = bool(operation_re.search(upstream_text))

    # High-recall, but based only on meaningful fields.
    if rule_hit:
        rank = "A_RULE"
    elif mechanism_boundary and mechanism_validation:
        rank = "B_MECHANISM"
    elif mechanism_boundary and mechanism_operation and upstream_boundary:
        rank = "C_BOUNDARY"
    else:
        continue

    records.append({
        "rank": rank,
        "root_id": rid,
        "case_id": case_id,
        "repository": root["Repository"],
        "pc_count": root["PC Count"],
        "issue_title": issue_title,
        "issue_body": issue_body,
        "issue_url": iss.get("url") or "",
        "root_summary": root.get("Root Summary", ""),
        "subproblem": root.get("Subproblem", ""),
        "shared_strategy": root.get("Shared Strategy", ""),
        "rule_ids": rules,
        "finding_family": fams,
        "security_mechanism": mech,
        "producing_change": change,
        "requested_goal": goal,
        "goal_evidence": goal_ev,
        "effective_A_labels": a_labels,
        "effective_B_labels": b_labels,
        "rule_hit": rule_hit,
        "mechanism_boundary": mechanism_boundary,
        "mechanism_validation": mechanism_validation,
        "mechanism_operation": mechanism_operation,
        "upstream_boundary": upstream_boundary,
        "upstream_operation": upstream_operation,
        "diff_evidence": diff_ev,
    })

order = {"A_RULE": 0, "B_MECHANISM": 1, "C_BOUNDARY": 2}
records.sort(key=lambda x: (order[x["rank"]], x["root_id"]))

csv_path = OUT / "URL_HOST_ROOT_CANDIDATES_v2.csv"
jsonl_path = OUT / "URL_HOST_ROOT_CANDIDATES_v2.jsonl"
summary_path = OUT / "URL_HOST_ROOT_CANDIDATES_v2_SUMMARY.txt"

if records:
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=records[0].keys())
        w.writeheader()
        w.writerows(records)

with jsonl_path.open("w", encoding="utf-8") as f:
    for r in records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

counts = Counter(r["rank"] for r in records)

with summary_path.open("w", encoding="utf-8") as f:
    f.write("URL/HOSTNAME EXPERIMENT CANDIDATE CENSUS\n\n")
    f.write("FROZEN_ROOTS=342\n")
    f.write("SOURCE_CODE_ROOTS_EXPECTED=201\n")
    f.write(f"SHORTLISTED={len(records)}\n")
    f.write(f"A_RULE={counts['A_RULE']}\n")
    f.write(f"B_MECHANISM={counts['B_MECHANISM']}\n")
    f.write(f"C_BOUNDARY={counts['C_BOUNDARY']}\n")

    f.write("\n=== SHORTLIST ===\n")
    for r in records:
        f.write(
            f"\n{r['rank']} | {r['root_id']} | "
            f"case={r['case_id']} | {r['repository']}\n"
        )
        f.write(f"ISSUE: {r['issue_title']}\n")
        f.write(f"RULE: {r['rule_ids']}\n")
        f.write(f"ROOT: {r['root_summary']}\n")
        f.write(f"MECH: {r['security_mechanism'][:600]}\n")
        f.write(f"GOAL: {r['requested_goal'][:500]}\n")

zip_path = OUT / "URL_HOST_ROOT_CANDIDATES_v2.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    for p in [csv_path, jsonl_path, summary_path]:
        if p.exists():
            z.write(p, p.name)

sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()

print(summary_path.read_text())
print()
print("ZIP=", zip_path)
print("SHA256=", sha)
print("ZIP_BYTES=", zip_path.stat().st_size)

con.close()
PY
