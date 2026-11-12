import csv, json, sqlite3, hashlib, shutil, zipfile
from pathlib import Path

DB = Path("/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/data/final-study-snapshot-20260829/full3809-scanner-complete-20260829.db")
ROOT = Path("/home-mscluster/astrauss/research_artifacts/audit31_stage1")
SEED = ROOT / "AUDIT31_STAGE1_INPUT_v1.csv"
RUBRIC = ROOT / "AUDIT31_RUBRIC_v1.md"

csv.field_size_limit(1024 * 1024 * 1024)

with SEED.open(newline="", encoding="utf-8-sig") as f:
    pairs = list(csv.DictReader(f))

assert len(pairs) == 31

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

def case_context(cid):
    r = con.execute("""
        SELECT
            c.id AS case_id,
            c.repo_id,
            c.issue_id,
            c.pr_id,
            r.full_name AS repository,
            i.title AS issue_title,
            i.body AS issue_body,
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
    """, (cid,)).fetchone()
    return dict(r) if r else None

def file_context(pr_id, wanted):
    rows = con.execute("""
        SELECT filename, status, additions, deletions, patch
        FROM pr_files
        WHERE pr_id = ?
    """, (pr_id,)).fetchall()

    wanted = (wanted or "").lstrip("./")

    exact = [x for x in rows if (x["filename"] or "").lstrip("./") == wanted]
    if len(exact) == 1:
        return dict(exact[0])

    suffix = [
        x for x in rows
        if wanted and (
            (x["filename"] or "").endswith("/" + wanted)
            or wanted.endswith("/" + (x["filename"] or ""))
        )
    ]
    if len(suffix) == 1:
        return dict(suffix[0])

    return None

def scanner_context(cid, wanted):
    rows = con.execute("""
        SELECT scanner, finding_type, severity, rule_id, cwe,
               file_path, line, description, evidence, introduced
        FROM scanner_findings
        WHERE case_id = ?
        ORDER BY id
    """, (cid,)).fetchall()

    wanted = (wanted or "").lstrip("./")

    def same_file(path):
        p = (path or "").lstrip("./")
        return (
            p == wanted
            or (wanted and p.endswith("/" + wanted))
            or (p and wanted.endswith("/" + p))
        )

    matched = [dict(x) for x in rows if same_file(x["file_path"])]
    introduced = [x for x in matched if x.get("introduced") in (1, True, "1")]

    return introduced if introduced else matched

def side(ctx, file_row, mechanism):
    return {
        "repository": ctx["repository"],
        "issue_title": ctx["issue_title"],
        "issue_body": ctx["issue_body"] or "",
        "pr_title": ctx["pr_title"],
        "pr_body": ctx["pr_body"] or "",
        "base_sha": ctx["base_sha"],
        "head_sha": ctx["head_sha"],
        "focus_file": file_row["filename"] if file_row else None,
        "focus_mechanism": mechanism,
        "file_status": file_row["status"] if file_row else None,
        "file_additions": file_row["additions"] if file_row else None,
        "file_deletions": file_row["deletions"] if file_row else None,
        "target_file_patch": file_row["patch"] if file_row else None
    }

blind = []
aware = []
keys = []
qc = []

for row in pairs:
    pid = row["pair_id"]
    pcid = int(row["positive_case_id"])
    ccid = int(row["control_case_id"])

    pctx = case_context(pcid)
    cctx = case_context(ccid)

    pf = file_context(pctx["pr_id"], row["positive_file_path"]) if pctx else None
    cf = file_context(cctx["pr_id"], row["control_file_path"]) if cctx else None

    pside = side(pctx, pf, row["positive_mechanism_summary"]) if pctx else None
    cside = side(cctx, cf, row["control_mechanism_summary"]) if cctx else None

    # Stable pair-level blinding: positive side is not always A.
    swap = hashlib.sha256(("AUDIT31-v1|" + pid).encode()).digest()[0] & 1

    if swap:
        A, B = cside, pside
        Arole, Brole = "CONTROL", "POSITIVE"
    else:
        A, B = pside, cside
        Arole, Brole = "POSITIVE", "CONTROL"

    base = {
        "pair_id": pid,
        "decision_family": row["decision_family"],
        "match_tier": row["match_tier"],
        "same_repository": row["same_repository"],
        "side_A": A,
        "side_B": B
    }

    blind.append(base)

    findings = scanner_context(pcid, row["positive_file_path"])

    aware.append({
        **base,
        "unblind": {
            "positive_side": "A" if Arole == "POSITIVE" else "B",
            "control_side": "A" if Arole == "CONTROL" else "B",
            "positive_case_id": pcid,
            "control_case_id": ccid,
            "positive_file_path": row["positive_file_path"],
            "positive_scanner_findings_on_focus_file": findings
        }
    })

    keys.append({
        "pair_id": pid,
        "side_A_role": Arole,
        "side_B_role": Brole,
        "positive_case_id": pcid,
        "control_case_id": ccid
    })

    qc.append({
        "pair_id": pid,
        "match_tier": row["match_tier"],
        "positive_case_id": pcid,
        "control_case_id": ccid,
        "positive_context": bool(pctx),
        "control_context": bool(cctx),
        "positive_focus_patch": bool(pf and pf.get("patch")),
        "control_focus_patch": bool(cf and cf.get("patch")),
        "positive_focus_findings": len(findings),
        "positive_patch_chars": len((pf or {}).get("patch") or ""),
        "control_patch_chars": len((cf or {}).get("patch") or "")
    })

def write_jsonl(path, rows):
    with path.open("w", encoding="utf-8") as f:
        for x in rows:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")

write_jsonl(ROOT / "AUDIT31_PASS1_BLIND.jsonl", blind)
write_jsonl(ROOT / "AUDIT31_PASS2_RULE_AWARE.jsonl", aware)

with (ROOT / "AUDIT31_SECRET_KEY.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=keys[0].keys())
    w.writeheader()
    w.writerows(keys)

with (ROOT / "AUDIT31_EXTRACTION_QC.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=qc[0].keys())
    w.writeheader()
    w.writerows(qc)

missing_ctx = sum(not x["positive_context"] or not x["control_context"] for x in qc)
missing_patch = sum(not x["positive_focus_patch"] or not x["control_focus_patch"] for x in qc)
missing_find = sum(x["positive_focus_findings"] == 0 for x in qc)

summary = f"""AUDIT31 STAGE-1 EXTRACTION

PAIRS={len(qc)}
UNIQUE_CASES=62
D1={sum(x['match_tier'].startswith('D1') for x in qc)}
D2={sum(x['match_tier'].startswith('D2') for x in qc)}

MISSING_CASE_CONTEXT_PAIRS={missing_ctx}
MISSING_FOCUS_PATCH_PAIRS={missing_patch}
POSITIVE_PAIRS_WITH_NO_FOCUS_FILE_SCANNER_EVIDENCE={missing_find}

PASS1=A/B blinded task + PR + exact focus-file patch
PASS2=same packets unblinded with scanner evidence
NO_EXISTING_GUARD_LABELS_INCLUDED_IN_PASS1
NO_NEW_GENERATIONS_PERFORMED
"""
(ROOT / "AUDIT31_EXTRACTION_SUMMARY.txt").write_text(summary)

files = [
    "AUDIT31_PASS1_BLIND.jsonl",
    "AUDIT31_PASS2_RULE_AWARE.jsonl",
    "AUDIT31_SECRET_KEY.csv",
    "AUDIT31_EXTRACTION_QC.csv",
    "AUDIT31_EXTRACTION_SUMMARY.txt",
    "AUDIT31_RUBRIC_v1.md"
]

zip_path = ROOT / "AUDIT31_STAGE1_PACKETS_v1.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    for name in files:
        z.write(ROOT / name, name)

sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
(ROOT / "AUDIT31_STAGE1_PACKETS_v1.sha256").write_text(
    f"{sha}  {zip_path.name}\n"
)

print(summary)
print("ZIP=", zip_path)
print("SHA256=", sha)
print("ZIP_BYTES=", zip_path.stat().st_size)

con.close()
