#!/bin/bash
#SBATCH --job-name=url_candidates
#SBATCH --partition=batch
#SBATCH --time=00:10:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/url_boundary_census/candidates.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/url_boundary_census/candidates.err

python3 - <<'PY'
from pathlib import Path
import csv, sqlite3, json, zipfile, hashlib, re

HOME = Path.home()
OUT = HOME/"research_artifacts/url_boundary_census"
D = HOME/"research_artifacts/D_COMPLETE_ROOT_PROVENANCE_v1_0"

# Exact frozen 233-M artifact.
hits = list((HOME/"research_artifacts").rglob(
    "D7_FINAL_M_ROOTS_233_WITH_COHORTS.csv"
))

if not hits:
    print("ERROR=D7_FINAL_M_ROOTS_233_WITH_COHORTS.csv_NOT_FOUND")
    print("Searching exact D7 filenames only:")
    for name in [
        "D7_FINAL_ROOT_CENSUS_WITH_COHORTS_342.csv",
        "D7_RESULTS.json",
        "D7_SUMMARY.md",
    ]:
        for p in (HOME/"research_artifacts").rglob(name):
            print(p)
    raise SystemExit(2)

mfile = hits[0]
cross = D/"01_INPUT/D1_ROOT_PC_EVIDENCE_CROSSWALK_455.csv"

print("M_ROOT_FILE=", mfile)
print("CROSSWALK=", cross)

with mfile.open(newline="", encoding="utf-8-sig") as f:
    mrows = list(csv.DictReader(f))

print("M_ROWS=", len(mrows))
if len(mrows) != 233:
    raise SystemExit(f"Expected 233 M roots, got {len(mrows)}")

root_col = next(
    c for c in mrows[0]
    if c.lower().replace(" ","_") in {"root_id","rootid"}
)
mroots = {r[root_col].strip() for r in mrows}

with cross.open(newline="", encoding="utf-8-sig") as f:
    pcrows = list(csv.DictReader(f))

byroot = {}
for r in pcrows:
    rid = (r.get("C_Root ID") or "").strip()
    if rid in mroots:
        byroot.setdefault(rid, []).append(r)

if len(byroot) != 233:
    print("WARNING_JOINED_M_ROOTS=", len(byroot))

DB = Path(
    "/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/"
    "data/final-study-snapshot-20260829/"
    "full3809-scanner-complete-20260829.db"
)
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

def issue(case_id):
    q = con.execute("""
        SELECT i.title, i.body, i.url
        FROM cases c
        JOIN issues i ON i.id=c.issue_id
        WHERE c.id=?
    """, (int(case_id),)).fetchone()
    return dict(q) if q else {}

strong_rules = (
    "incomplete-url-substring",
    "incomplete-hostname-regexp",
)

boundary_terms = re.compile(
    r"\b(hostname|host name|domain|allowed host|trusted host|"
    r"provider host|origin|destination|url validation|validate url|"
    r"recognize url|recognise url|url check)\b",
    re.I
)

operation_terms = re.compile(
    r"\b(fetch|request|redirect|navigate|open|load|connect|provider|"
    r"allow|deny|accept|reject|authorize|authorise)\b",
    re.I
)

generic_url = re.compile(r"\b(url|uri|http|https)\b", re.I)

records = []

for rid, rows in sorted(byroot.items()):
    first = rows[0]

    fields = {
        "root_summary": first.get("C_Root Summary",""),
        "repository": first.get("C_Repository",""),
        "case_id": first.get("C_Case ID",""),
        "rules": " || ".join(sorted({
            x.get("PROV_Rule ID(s)","") for x in rows
            if x.get("PROV_Rule ID(s)")
        })),
        "finding_families": " || ".join(sorted({
            x.get("PROV_Finding Family","") for x in rows
            if x.get("PROV_Finding Family")
        })),
        "mechanisms": " || ".join(
            x.get("PROV_Security-Relevant Mechanism","") for x in rows
        ),
        "producing_changes": " || ".join(
            x.get("PROV_Finding-Producing Change","") for x in rows
        ),
        "requested_goals": " || ".join(
            x.get("PROV_Requested Goal Set","") for x in rows
        ),
        "goal_evidence": " || ".join(
            x.get("PROV_Goal Evidence","") for x in rows
        ),
        "issue_title_frozen": first.get("PROV_Issue Title",""),
    }

    text = " ".join(fields.values())

    rule_specific = any(x in fields["rules"].lower() for x in strong_rules)
    boundary = bool(boundary_terms.search(text))
    operation = bool(operation_terms.search(text))
    url_only = bool(generic_url.search(text))

    # This is only a high-recall shortlist, NOT final eligibility.
    if rule_specific:
        rank = "A_RULE_SPECIFIC"
    elif boundary and operation:
        rank = "B_BOUNDARY_OPERATION"
    elif boundary:
        rank = "C_BOUNDARY_TEXT"
    elif url_only:
        continue
    else:
        continue

    iss = issue(fields["case_id"])

    records.append({
        "candidate_rank": rank,
        "root_id": rid,
        "case_id": fields["case_id"],
        "repository": fields["repository"],
        "issue_title": iss.get("title") or fields["issue_title_frozen"],
        "issue_body": iss.get("body") or "",
        "issue_url": iss.get("url") or "",
        "root_summary": fields["root_summary"],
        "rule_ids": fields["rules"],
        "finding_families": fields["finding_families"],
        "security_relevant_mechanism": fields["mechanisms"],
        "finding_producing_change": fields["producing_changes"],
        "requested_goal": fields["requested_goals"],
        "goal_evidence": fields["goal_evidence"],
        "pc_count": len(rows),
    })

order = {"A_RULE_SPECIFIC":0, "B_BOUNDARY_OPERATION":1, "C_BOUNDARY_TEXT":2}
records.sort(key=lambda r: (order[r["candidate_rank"]], r["root_id"]))

csv_path = OUT/"URL_HOST_M_CANDIDATES_v1.csv"
jsonl_path = OUT/"URL_HOST_M_CANDIDATES_v1.jsonl"

with csv_path.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=records[0].keys() if records else [
        "candidate_rank","root_id","case_id","repository"
    ])
    w.writeheader()
    w.writerows(records)

with jsonl_path.open("w", encoding="utf-8") as f:
    for r in records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

counts = {}
for r in records:
    counts[r["candidate_rank"]] = counts.get(r["candidate_rank"],0)+1

summary = OUT/"URL_HOST_M_CENSUS_SUMMARY.txt"
with summary.open("w", encoding="utf-8") as f:
    f.write("URL/HOST BOUNDARY CANDIDATE CENSUS\n")
    f.write("SOURCE_M_ROOTS=233\n")
    f.write(f"SHORTLISTED_ROOTS={len(records)}\n")
    for k in ["A_RULE_SPECIFIC","B_BOUNDARY_OPERATION","C_BOUNDARY_TEXT"]:
        f.write(f"{k}={counts.get(k,0)}\n")

    f.write("\n=== CANDIDATES ===\n")
    for r in records:
        f.write(
            f"\n{r['candidate_rank']} | {r['root_id']} | "
            f"case={r['case_id']} | {r['repository']}\n"
        )
        f.write(f"ISSUE: {r['issue_title']}\n")
        f.write(f"RULES: {r['rule_ids']}\n")
        f.write(f"ROOT: {r['root_summary']}\n")
        f.write(f"MECH: {r['security_relevant_mechanism'][:800]}\n")

zip_path = OUT/"URL_HOST_M_CANDIDATES_v1.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    z.write(csv_path, csv_path.name)
    z.write(jsonl_path, jsonl_path.name)
    z.write(summary, summary.name)

sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()

print(summary.read_text())
print()
print("ZIP=", zip_path)
print("SHA256=", sha)

con.close()
PY
