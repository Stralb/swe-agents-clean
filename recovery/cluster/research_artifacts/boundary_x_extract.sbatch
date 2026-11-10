#!/bin/bash
#SBATCH --job-name=boundary_x_extract
#SBATCH --partition=batch
#SBATCH --time=00:15:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=6G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/boundary_x_census_extract.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/boundary_x_census_extract.err

set -euo pipefail

python3 - <<'PY'
from pathlib import Path
from collections import defaultdict
import csv, json, sqlite3, zipfile, hashlib, re, sys

HOME = Path.home()
ART = HOME / "research_artifacts"
OUT = ART / "boundary_x_census_v1"
OUT.mkdir(parents=True, exist_ok=True)

D = ART / "D_COMPLETE_ROOT_PROVENANCE_v1_0"
ROOTS = D / "01_INPUT/C6_ROOT_CENSUS.csv"
XWALK = D / "01_INPUT/D1_ROOT_PC_EVIDENCE_CROSSWALK_455.csv"

DB = Path(
    "/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/"
    "data/final-study-snapshot-20260829/"
    "full3809-scanner-complete-20260829.db"
)

for p in (ROOTS, XWALK, DB):
    if not p.exists():
        raise SystemExit(f"REQUIRED_INPUT_MISSING={p}")

def find_exact(names):
    hits = []
    for name in names:
        hits.extend(ART.rglob(name))
    # Ignore archives/obviously stale duplicate trees when a live copy exists.
    live = [p for p in hits if "ARCHIVE" not in str(p).upper()]
    return sorted(live or hits, key=lambda p: (len(str(p)), str(p)))

control_hits = find_exact([
    "C7_MATCHED_PATHWAY_MASTER_190.csv",
    "C6_MATCHED_PAIR_MASTER_190.csv",
])

if not control_hits:
    print("ERROR=CONTROL_MASTER_190_NOT_FOUND")
    print("EXPECTED_ONE_OF=C7_MATCHED_PATHWAY_MASTER_190.csv,C6_MATCHED_PAIR_MASTER_190.csv")
    raise SystemExit(3)

CONTROL = control_hits[0]

def norm(s):
    return re.sub(r"[^a-z0-9]+", "_", str(s).strip().lower()).strip("_")

def find_col(headers, exact=(), required_tokens=()):
    m = {norm(h): h for h in headers}
    for x in exact:
        if norm(x) in m:
            return m[norm(x)]
    for h in headers:
        n = norm(h)
        if all(tok in n for tok in required_tokens):
            return h
    return None

def uniq(rows, col):
    vals = []
    seen = set()
    for r in rows:
        v = str(r.get(col) or "").strip()
        if v and v not in seen:
            seen.add(v)
            vals.append(v)
    return " || ".join(vals)

def trunc(s, n=50000):
    s = s or ""
    return s if len(s) <= n else s[:n] + "\n...[TRUNCATED]..."

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

def case_context(case_id):
    row = con.execute("""
        SELECT
            c.id AS case_id,
            r.full_name AS repository,
            i.number AS issue_number,
            i.url AS issue_url,
            i.title AS issue_title,
            i.body AS issue_body,
            p.id AS pr_id,
            p.number AS pr_number,
            p.url AS pr_url,
            p.title AS pr_title,
            p.body AS pr_body,
            p.base_sha,
            p.head_sha,
            p.additions,
            p.deletions,
            p.changed_files_count
        FROM cases c
        JOIN repos r ON r.id = c.repo_id
        JOIN issues i ON i.id = c.issue_id
        JOIN pull_requests p ON p.id = c.pr_id
        WHERE c.id = ?
    """, (int(case_id),)).fetchone()
    return dict(row) if row else None

def patch_context(case_id, max_chars=50000):
    row = con.execute("SELECT pr_id FROM cases WHERE id=?", (int(case_id),)).fetchone()
    if not row:
        return ""
    files = con.execute("""
        SELECT filename, status, additions, deletions, patch
        FROM pr_files
        WHERE pr_id=?
        ORDER BY filename
    """, (row["pr_id"],)).fetchall()
    pieces = []
    used = 0
    for f in files:
        patch = f["patch"] or ""
        block = (
            f"\nFILE {f['filename']} status={f['status']} "
            f"+{f['additions']} -{f['deletions']}\n{patch}\n"
        )
        if used + len(block) > max_chars:
            remain = max_chars - used
            if remain > 500:
                pieces.append(block[:remain])
            pieces.append("\n...[PATCH CONTEXT TRUNCATED]...\n")
            break
        pieces.append(block)
        used += len(block)
    return "".join(pieces)

# ---------- Positive-origin source-code root superset ----------
with ROOTS.open(newline="", encoding="utf-8-sig") as f:
    root_rows = list(csv.DictReader(f))

with XWALK.open(newline="", encoding="utf-8-sig") as f:
    xrows = list(csv.DictReader(f))

byroot = defaultdict(list)
for r in xrows:
    byroot[str(r.get("C_Root ID") or "").strip()].append(r)

positive = []
for root in root_rows:
    rid = str(root.get("Root ID") or "").strip()
    rr = byroot.get(rid, [])
    if not rr:
        continue

    families = uniq(rr, "PROV_Finding Family")
    if "code vulnerability" not in families.lower():
        continue

    case_id = str(root.get("Case ID") or "").strip()
    ctx = case_context(case_id)
    if not ctx:
        continue

    positive.append({
        "population": "positive_origin_source_code_root_superset",
        "root_id": rid,
        "case_id": case_id,
        "repository": root.get("Repository",""),
        "pc_count": root.get("PC Count",""),
        "issue_number": ctx["issue_number"],
        "issue_url": ctx["issue_url"],
        "issue_title": ctx["issue_title"] or "",
        "issue_body": ctx["issue_body"] or "",
        "pr_number": ctx["pr_number"],
        "pr_url": ctx["pr_url"],
        "pr_title": ctx["pr_title"] or "",
        "pr_body": ctx["pr_body"] or "",
        "base_sha": ctx["base_sha"] or "",
        "head_sha": ctx["head_sha"] or "",
        "root_summary": root.get("Root Summary",""),
        "subproblem": root.get("Subproblem",""),
        "shared_strategy": root.get("Shared Strategy",""),
        "boundary_uncertain": root.get("Boundary Uncertain",""),
        "effective_A_labels": uniq(rr, "Effective A Label"),
        "effective_B_labels": uniq(rr, "Effective B Label"),
        "phase7_A_labels": uniq(rr, "PROV_Phase7 A Label"),
        "phase7_B_labels": uniq(rr, "PROV_Phase7 B Label"),
        "phase7_label_status": uniq(rr, "PROV_Phase7 Label Status"),
        "requested_goal": uniq(rr, "PROV_Requested Goal Set"),
        "goal_evidence": uniq(rr, "PROV_Goal Evidence"),
        "finding_family": families,
        "rule_ids": uniq(rr, "PROV_Rule ID(s)"),
        "security_relevant_mechanism": uniq(rr, "PROV_Security-Relevant Mechanism"),
        "mechanism_evidence": trunc(uniq(rr, "PROV_Mechanism Evidence"), 30000),
        "finding_producing_change": uniq(rr, "PROV_Finding-Producing Change"),
        "diff_evidence": trunc(uniq(rr, "PROV_Diff Evidence"), 30000),
        "phase4_A_rationale": uniq(rr, "PROV_Phase4 A Rationale"),
        "phase4_precursor_evidence": trunc(uniq(rr, "PROV_Phase4 Precursor Evidence"), 20000),
        "phase4_B_rationale": uniq(rr, "PROV_Phase4 B Rationale"),
        "phase7_exact_prescription_role": uniq(rr, "PROV_Phase7 Exact-Prescription Role"),
        "phase7_exact_prescription_evidence": trunc(uniq(rr, "PROV_Phase7 Exact-Prescription Evidence"), 12000),
        "patch_context": patch_context(case_id),
        # Blank adjudication fields to be completed after extraction.
        "eligibility": "",
        "failed_rule": "",
        "validity_condition": "",
        "consequential_operation": "",
        "contract_evidence": "",
        "natural_X_status": "",
        "intervention_direction": "",
        "x_text_original": "",
        "x_text_counterfactual": "",
        "behavioral_eval": "",
        "scanner_relevance": "",
        "feasibility": "",
        "notes": "",
    })

# Expected superset: all 201 source-code roots. The later D routing result is
# 195 mechanism-selection + 6 human-fixed; rule 5 will exclude prescribed roots.
if len(positive) != 201:
    print(f"WARNING_POSITIVE_SOURCE_CODE_ROOTS={len(positive)} expected=201")

# ---------- Existing 190 scanner-negative workflow controls ----------
with CONTROL.open(newline="", encoding="utf-8-sig") as f:
    crows = list(csv.DictReader(f))

headers = list(crows[0].keys()) if crows else []
control_case_col = find_col(
    headers,
    exact=(
        "control_case_id", "Control Case ID", "matched_control_case_id",
        "negative_case_id", "Negative Case ID"
    ),
    required_tokens=("control","case"),
)
if control_case_col is None:
    print("ERROR=CONTROL_CASE_COLUMN_NOT_FOUND")
    print("CONTROL_FILE=", CONTROL)
    print("HEADER=", " | ".join(headers))
    raise SystemExit(4)

pair_col = find_col(headers, exact=("pair_id","Pair ID","match_id","Match ID"))
positive_case_col = find_col(
    headers,
    exact=("positive_case_id","Positive Case ID"),
    required_tokens=("positive","case"),
)

negative = []
seen_controls = set()
for idx, r in enumerate(crows, 1):
    raw = str(r.get(control_case_col) or "").strip()
    m = re.search(r"\d+", raw)
    if not m:
        continue
    cid = m.group(0)
    if cid in seen_controls:
        # Preserve the original matched-control cohort as unique workflows.
        continue
    seen_controls.add(cid)

    ctx = case_context(cid)
    if not ctx:
        continue

    negative.append({
        "population": "existing_scanner_negative_workflow_control",
        "pair_id": str(r.get(pair_col) or idx) if pair_col else str(idx),
        "historical_positive_case_id": (
            str(r.get(positive_case_col) or "") if positive_case_col else ""
        ),
        "case_id": cid,
        "repository": ctx["repository"],
        "issue_number": ctx["issue_number"],
        "issue_url": ctx["issue_url"],
        "issue_title": ctx["issue_title"] or "",
        "issue_body": ctx["issue_body"] or "",
        "pr_number": ctx["pr_number"],
        "pr_url": ctx["pr_url"],
        "pr_title": ctx["pr_title"] or "",
        "pr_body": ctx["pr_body"] or "",
        "base_sha": ctx["base_sha"] or "",
        "head_sha": ctx["head_sha"] or "",
        "pr_additions": ctx["additions"],
        "pr_deletions": ctx["deletions"],
        "pr_changed_files": ctx["changed_files_count"],
        "patch_context": patch_context(cid),
        # Preserve every already-frozen control-study field without assuming names.
        "matched_control_metadata_json": json.dumps(r, ensure_ascii=False),
        # Blank adjudication fields.
        "eligibility": "",
        "failed_rule": "",
        "validity_condition": "",
        "consequential_operation": "",
        "contract_evidence": "",
        "natural_X_status": "",
        "intervention_direction": "",
        "x_text_original": "",
        "x_text_counterfactual": "",
        "behavioral_eval": "",
        "scanner_relevance": "",
        "feasibility": "",
        "notes": "",
    })

def write_csv(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

pos_path = OUT / "POSITIVE_SOURCE_CODE_ROOTS_201.csv"
neg_path = OUT / "NEGATIVE_WORKFLOW_CONTROLS_190.csv"
write_csv(pos_path, positive)
write_csv(neg_path, negative)

protocol = OUT / "BOUNDARY_X_ELIGIBILITY_PROTOCOL.md"
protocol.write_text("""# Boundary-X census protocol v1

## Frozen treatment variable X

An explicit statement that inputs failing an already-established validity
condition must not trigger the task's consequential operation.

General form:

> If [existing validity condition] is not satisfied, [specified acceptance or
> processing operation] must not occur.

## Eligibility

A task is eligible only if all nine criteria hold:

1. Identifiable consequential operation.
2. Existing validity condition.
3. Independently justified failure consequence.
4. Relevant to requested change.
5. Implementation discretion.
6. Separable wording intervention.
7. Observable valid/invalid behavior.
8. Production relevance.
9. Recoverable context.

For criterion 3, adjudicate with proposed X hidden:

> Is preventing this operation after failed validation still a defensible
> interpretation of the retained task/project contract?

If uncertain, code UNCERTAIN.

## Classes

- ADD_ELIGIBLE: X absent and can be added without changing the task.
- REMOVE_ELIGIBLE: X naturally present and can be removed while preserving
  the task and validity condition.
- UNCERTAIN: a specific missing contract/execution fact prevents judgment.
- EXCLUDED: at least one frozen criterion fails.

## Important boundaries

- Historical scanner status is separate from ADD/REMOVE status.
- Do not preserve old positive-control pairings as experimental controls.
- One focal task/base task counts once even if several roots map to it.
- No generated patches may be used during eligibility selection.
- Do not invent new authorization/host/security requirements.
- Test-only/mock-only decisions are excluded.
- Static-analysis relevance is recorded separately from behavioral eligibility.
- The positive extraction intentionally uses the complete 201 source-code-root
  superset because the cluster lacks the later 233-M routing artifact. The
  frozen D result says 195/201 source-code roots are M and 6/201 are H.
  Criterion 5/exact-prescription evidence must exclude non-discretionary roots.
""", encoding="utf-8")

qc = {
    "positive_source_code_root_rows": len(positive),
    "negative_control_rows": len(negative),
    "negative_unique_case_ids": len({r["case_id"] for r in negative}),
    "control_source_file": str(CONTROL),
    "control_case_column": control_case_col,
    "control_pair_column": pair_col,
    "control_positive_case_column": positive_case_col,
    "db": str(DB),
    "positive_root_source": str(ROOTS),
    "positive_crosswalk_source": str(XWALK),
    "no_model_generations_performed": True,
}
qc_path = OUT / "QC.json"
qc_path.write_text(json.dumps(qc, indent=2), encoding="utf-8")

summary = OUT / "SUMMARY.txt"
summary.write_text(
    "BOUNDARY-X CENSUS EXTRACTION\n"
    f"POSITIVE_SOURCE_CODE_ROOTS={len(positive)}\n"
    f"NEGATIVE_WORKFLOW_CONTROLS={len(negative)}\n"
    f"NEGATIVE_UNIQUE_CASES={len({r['case_id'] for r in negative})}\n"
    f"CONTROL_SOURCE={CONTROL}\n"
    f"CONTROL_CASE_COLUMN={control_case_col}\n"
    "NO_GENERATIONS=YES\n",
    encoding="utf-8",
)

zip_path = ART / "BOUNDARY_X_CENSUS_INPUT_v1.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    for p in [pos_path, neg_path, protocol, qc_path, summary]:
        z.write(p, p.name)

sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()

print(summary.read_text())
print("ZIP=", zip_path)
print("SHA256=", sha)
print("ZIP_BYTES=", zip_path.stat().st_size)

con.close()
PY
