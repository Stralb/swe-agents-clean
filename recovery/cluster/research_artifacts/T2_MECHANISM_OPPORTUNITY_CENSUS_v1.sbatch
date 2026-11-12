#!/bin/bash
#SBATCH --job-name=t2mechcensus
#SBATCH --partition=bigbatch
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T2_MECHANISM_OPPORTUNITY_CENSUS_v1_%j.out

set -euo pipefail

GROUP="${GROUP:?submit with --export=ALL,GROUP=0 or GROUP=1}"

python3 -u <<'PY'
import csv
import hashlib
import io
import json
import math
import os
import re
import sqlite3
import tarfile
from collections import Counter, defaultdict
from pathlib import Path

GROUP = int(os.environ["GROUP"])
if GROUP not in (0, 1):
    raise SystemExit("GROUP must be 0 or 1")

ROOT = Path.home() / "research_artifacts"
ROOTS_CSV = ROOT / "D7_FINAL_M_ROOTS_233_WITH_COHORTS.csv"
DB = Path("/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/data/miner.agentic-js.eval.20260720_224159.hf-snapshot-20260817.db")

OUT = ROOT / f"T2_MECHANISM_OPPORTUNITY_CENSUS_v1_G{GROUP}"
REVIEW_TAR = ROOT / f"T2_MECHANISM_OPPORTUNITY_CENSUS_v1_G{GROUP}_REVIEW.tar.gz"
SEALED_MAP = ROOT / f"T2_MECHANISM_OPPORTUNITY_CENSUS_v1_G{GROUP}_SEALED_MAP.json"

if not ROOTS_CSV.exists():
    raise SystemExit(f"MISSING_ROOTS_CSV={ROOTS_CSV}")
if not DB.exists():
    raise SystemExit(f"MISSING_DB={DB}")

OUT.mkdir(parents=True, exist_ok=True)

TEST_PARTS = {
    "test","tests","spec","specs","fixture","fixtures","mock","mocks",
    "__tests__","example","examples","benchmark","benchmarks"
}

SOURCE_EXTS = {
    ".js",".jsx",".ts",".tsx",".mjs",".cjs",
    ".py",".java",".go",".rb",".php",".rs",".c",".cc",".cpp",".h",".hpp",
    ".cs",".swift",".kt",".kts",
    ".json",".yaml",".yml",".toml",".xml",".html",".vue",".svelte"
}

FAMILY_BY_EXT = {
    ".js":"JS_TS",".jsx":"JS_TS",".ts":"JS_TS",".tsx":"JS_TS",".mjs":"JS_TS",".cjs":"JS_TS",
    ".py":"PYTHON",".java":"JVM",".kt":"JVM",".kts":"JVM",
    ".go":"GO",".rb":"RUBY",".php":"PHP",".rs":"RUST",
    ".c":"C_CPP",".cc":"C_CPP",".cpp":"C_CPP",".h":"C_CPP",".hpp":"C_CPP",
    ".cs":"CSHARP",".swift":"SWIFT",
    ".json":"CONFIG",".yaml":"CONFIG",".yml":"CONFIG",".toml":"CONFIG",".xml":"CONFIG",
    ".html":"WEB",".vue":"WEB",".svelte":"WEB",
}

STOP = {
    "the","and","for","with","from","that","this","into","when","where","while","then",
    "have","has","had","should","would","could","can","will","using","use","used","add",
    "added","change","changed","support","issue","feature","fix","update","make","ensure",
    "return","const","let","var","function","async","await","true","false","null","undefined",
    "new","get","set","create","remove","handle","code","file","files","value","values"
}

OP_FAMILIES = {
    "filesystem": {"file","path","directory","folder","read","write","rename","unlink","exists","stat","fs"},
    "normalization": {"normalize","normalise","slug","trim","lowercase","uppercase","casefold","canonical","alias","name","identifier"},
    "validation": {"validate","validation","check","guard","verify","match","recognize","recognise","accept","reject","allow","deny"},
    "url_domain": {"url","uri","domain","host","hostname","origin","github","http","https"},
    "regex_text": {"regex","regexp","pattern","substring","includes","startsWith","endsWith","replace","split","parse","text","string"},
    "random_identifier": {"random","uuid","nonce","token","identifier","id","entropy"},
    "secret_storage": {"password","secret","credential","token","apikey","api_key","storage","encrypt","decrypt"},
    "process_exec": {"exec","spawn","command","shell","process","child_process"},
    "network": {"request","http","https","fetch","axios","socket","network","client","server"},
    "database": {"sql","query","database","db","insert","select","update","delete","where"},
    "serialization": {"json","yaml","xml","serialize","deserialize","parse","stringify"},
    "authz_authn": {"auth","authentication","authorization","permission","role","login","session"},
    "archive": {"zip","tar","archive","extract","unpack","compress"},
    "dependency": {"dependency","package","version","npm","yarn","pnpm","lockfile"},
    "dom_html": {"html","dom","element","attribute","innerhtml","textcontent","render"},
}

def norm_text(s):
    return re.sub(r"\s+", " ", str(s or "").strip())

def words(s):
    out = []
    for raw in re.findall(r"[A-Za-z_$][A-Za-z0-9_$.-]{2,}", str(s or "")):
        parts = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", raw).replace(".", " ").replace("-", " ").replace("_", " ").split()
        for p in parts:
            q = p.casefold()
            if len(q) >= 3 and q not in STOP:
                out.append(q)
    return out

def api_tokens(s):
    toks = []
    text = str(s or "")
    for m in re.finditer(r"([A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*)\s*\(", text):
        val = m.group(1)
        pieces = val.split(".")
        toks.append(pieces[-1].casefold())
        if len(pieces) > 1:
            toks.append(".".join(pieces[-2:]).casefold())
    for m in re.finditer(r"\.([A-Za-z_$][A-Za-z0-9_$]*)", text):
        toks.append(m.group(1).casefold())
    return [t for t in toks if t not in STOP and len(t) >= 3]

def jaccard(a, b):
    a, b = set(a), set(b)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)

def op_families(text):
    ts = set(words(text))
    low = str(text or "").casefold()
    out = []
    for fam, ks in OP_FAMILIES.items():
        if ts & {k.casefold() for k in ks} or any(k.casefold() in low for k in ks if len(k) >= 5):
            out.append(fam)
    return sorted(set(out))

def is_test_path(path):
    parts = [p.casefold() for p in Path(str(path or "")).parts]
    name = Path(str(path or "")).name.casefold()
    return any(p in TEST_PARTS for p in parts) or bool(re.search(r"(^|[._-])(test|spec)([._-]|$)", name))

def ext_family(path):
    ext = Path(str(path or "")).suffix.casefold()
    return FAMILY_BY_EXT.get(ext, ext.upper().lstrip(".") if ext else "UNKNOWN")

def added_lines(patch, cap=120):
    out = []
    for ln in str(patch or "").splitlines():
        if ln.startswith("+") and not ln.startswith("+++"):
            x = ln[1:].strip()
            if x:
                out.append(x)
                if len(out) >= cap:
                    break
    return out

def path_role_tokens(path):
    vals = []
    for part in Path(str(path or "")).parts:
        vals.extend(words(part))
    return vals

def anon_id(root_id, case_id):
    h = hashlib.sha256(f"{root_id}|{case_id}|T2v1".encode()).hexdigest()[:10]
    return f"N-{h}"

# ---------- load frozen 233 roots ----------
with ROOTS_CSV.open(newline="", encoding="utf-8-sig") as f:
    roots = list(csv.DictReader(f))
if len(roots) != 233:
    raise SystemExit(f"ROOT_COUNT_MISMATCH expected=233 got={len(roots)}")

roots = sorted(roots, key=lambda r: r["root_id"])
group_roots = [r for i, r in enumerate(roots) if i % 2 == GROUP]

# ---------- DB preload ----------
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

issue_cols = {r[1] for r in con.execute('PRAGMA table_info("issues")')}
issue_body_expr = "i.body AS issue_body" if "body" in issue_cols else "'' AS issue_body"

case_rows = [
    dict(r) for r in con.execute(f"""
        SELECT
            c.id AS case_id,
            c.repo_id,
            r.full_name AS repository,
            i.number AS issue_number,
            i.title AS issue_title,
            {issue_body_expr},
            p.id AS pr_id,
            p.number AS pr_number,
            p.base_sha,
            p.head_sha
        FROM cases c
        JOIN repos r ON r.id=c.repo_id
        JOIN issues i ON i.id=c.issue_id
        JOIN pull_requests p ON p.id=c.pr_id
        ORDER BY c.id
    """)
]
cases = {int(r["case_id"]): r for r in case_rows}

files_by_pr = defaultdict(list)
for r in con.execute("""
    SELECT pr_id, filename, patch, status, additions, deletions
    FROM pr_files
"""):
    files_by_pr[int(r["pr_id"])].append(dict(r))

runs_by_case = defaultdict(dict)
for r in con.execute("""
    SELECT case_id, scanner, status
    FROM scanner_runs
"""):
    cid = int(r["case_id"])
    sc = str(r["scanner"] or "")
    # any ok run is sufficient
    old = runs_by_case[cid].get(sc)
    if old != "ok":
        runs_by_case[cid][sc] = str(r["status"] or "")

findings_by_case = defaultdict(list)
for r in con.execute("""
    SELECT case_id, scanner, rule_id, file_path, line, description, introduced
    FROM scanner_findings
"""):
    findings_by_case[int(r["case_id"])].append(dict(r))

# compact candidate features once
candidate_features = {}
for cid, c in cases.items():
    fs = files_by_pr.get(int(c["pr_id"]), [])
    prod = [f for f in fs if not is_test_path(f.get("filename")) and Path(str(f.get("filename") or "")).suffix.casefold() in SOURCE_EXTS]
    all_source = [f for f in fs if Path(str(f.get("filename") or "")).suffix.casefold() in SOURCE_EXTS]
    use = prod or all_source
    code = "\n".join("\n".join(added_lines(f.get("patch"), 80)) for f in use[:12])
    paths = [str(f.get("filename") or "") for f in use[:20]]
    issue = f"{c.get('issue_title','')}\n{c.get('issue_body','')}"
    candidate_features[cid] = {
        "production_change": bool(prod),
        "families": sorted(set(ext_family(p) for p in paths if p)),
        "issue_tokens": words(issue),
        "issue_text": norm_text(issue)[:6000],
        "op_families": op_families(issue + "\n" + code),
        "api_tokens": api_tokens(code),
        "path_tokens": [t for p in paths for t in path_role_tokens(p)],
        "paths": paths,
        "code_preview": added_lines(code, 16) if False else [],
        "code_text": code[:12000],
    }

review_records = []
sealed = {}
root_summary_rows = []

for root in group_roots:
    rid = root["root_id"]
    cid = int(root["case_id"])
    pos = cases.get(cid)
    status = {
        "root_id": rid,
        "case_present": bool(pos),
        "primary_eligible": False,
        "exclusion_reasons": [],
        "same_repo_primary_candidates": 0,
        "cross_repo_primary_candidates": 0,
        "sensitivity_candidates": 0,
        "retained_candidates": 0,
    }

    if not pos:
        status["exclusion_reasons"].append("CASE_NOT_IN_DB")
        root_summary_rows.append(status)
        continue

    introduced = [f for f in findings_by_case.get(cid, []) if int(f.get("introduced") or 0) == 1]
    summary_text = str(root.get("root_summary") or "")
    target_matches = []
    for f in introduced:
        fp = str(f.get("file_path") or "")
        if fp and (fp in summary_text or Path(fp).name in summary_text):
            target_matches.append(f)
    target_findings = target_matches or introduced

    target_scanners = sorted({str(f.get("scanner") or "") for f in target_findings if f.get("scanner")})
    target_rules = sorted({str(f.get("rule_id") or "") for f in target_findings if f.get("rule_id")})
    target_paths = sorted({str(f.get("file_path") or "") for f in target_findings if f.get("file_path")})

    if not target_scanners:
        status["exclusion_reasons"].append("NO_LINKED_SCANNER_FINDING")

    pos_files = files_by_pr.get(int(pos["pr_id"]), [])
    pos_target_files = [f for f in pos_files if str(f.get("filename") or "") in set(target_paths)]
    if not pos_target_files:
        # fall back to source files referenced lexically in root summary, then production sources
        lex = [f for f in pos_files if Path(str(f.get("filename") or "")).name and Path(str(f.get("filename") or "")).name in summary_text]
        pos_target_files = lex or [f for f in pos_files if not is_test_path(f.get("filename")) and Path(str(f.get("filename") or "")).suffix.casefold() in SOURCE_EXTS]

    pos_prod = [f for f in pos_target_files if not is_test_path(f.get("filename"))]
    if not pos_prod:
        status["exclusion_reasons"].append("POSITIVE_TARGET_TEST_OR_UNRESOLVED")

    chronology = str(root.get("final_chronology_ok") or "").strip().upper()
    evidence_complete = str(root.get("final_evidence_complete") or "").strip().casefold() in {"true","1","yes"}
    if chronology != "YES":
        status["exclusion_reasons"].append("CHRONOLOGY_NOT_CONFIRMED")
    if not evidence_complete:
        status["exclusion_reasons"].append("EVIDENCE_INCOMPLETE")

    pos_code = "\n".join("\n".join(added_lines(f.get("patch"), 100)) for f in pos_target_files[:8])
    pos_issue = f"{pos.get('issue_title','')}\n{pos.get('issue_body','')}"
    pos_task_tokens = words(pos_issue)
    pos_ops = op_families(pos_issue + "\n" + summary_text)
    pos_api = api_tokens(summary_text + "\n" + pos_code)
    pos_path_tokens = [t for p in target_paths for t in path_role_tokens(p)]
    pos_families = sorted(set(ext_family(p) for p in target_paths if p))
    if not pos_families:
        pos_families = sorted(set(ext_family(f.get("filename")) for f in pos_target_files if f.get("filename")))

    status["primary_eligible"] = (
        bool(pos) and bool(target_scanners) and bool(pos_prod)
        and chronology == "YES" and evidence_complete
    )

    primary = []
    sensitivity = []

    for ncid, neg in cases.items():
        if ncid == cid:
            continue
        cf = candidate_features[ncid]
        if not cf["production_change"]:
            continue

        # language/file family compatibility
        if pos_families and cf["families"] and not (set(pos_families) & set(cf["families"])):
            continue

        # require an OK run for at least one relevant scanner
        applicable_scanners = [s for s in target_scanners if runs_by_case[ncid].get(s) == "ok"]
        if not applicable_scanners:
            continue

        intro_neg = [f for f in findings_by_case.get(ncid, []) if int(f.get("introduced") or 0) == 1]
        strict_scanner_negative = all(
            not any(str(f.get("scanner") or "") == s for f in intro_neg)
            for s in applicable_scanners
        )
        exact_rule_negative = not any(
            str(f.get("scanner") or "") in applicable_scanners
            and str(f.get("rule_id") or "") in set(target_rules)
            for f in intro_neg
        )

        if not exact_rule_negative:
            continue

        same_repo = int(neg["repo_id"]) == int(pos["repo_id"])
        task_sim = jaccard(pos_task_tokens, cf["issue_tokens"])
        op_sim = jaccard(pos_ops, cf["op_families"])
        path_sim = jaccard(pos_path_tokens, cf["path_tokens"])
        api_sim = jaccard(pos_api, cf["api_tokens"])
        family_match = 1.0 if (set(pos_families) & set(cf["families"])) else 0.0

        # Candidate generation targets the same decision opportunity, not the same historical mechanism.
        score = (
            45.0 * task_sim
            + 25.0 * op_sim
            + 15.0 * path_sim
            + 5.0 * family_match
            + 5.0 * api_sim
            + 5.0 * (1.0 if same_repo else 0.0)
        )

        rec = {
            "negative_case_id": ncid,
            "same_repo": same_repo,
            "strict_scanner_negative": strict_scanner_negative,
            "exact_rule_negative": exact_rule_negative,
            "score": round(score, 6),
            "task_similarity": round(task_sim, 6),
            "operation_family_similarity": round(op_sim, 6),
            "path_role_similarity": round(path_sim, 6),
            "api_similarity_weak": round(api_sim, 6),
            "language_family_match": bool(family_match),
            "negative_issue_title": norm_text(neg.get("issue_title","")),
            "negative_issue_body_excerpt": norm_text(neg.get("issue_body",""))[:1200],
            "negative_op_families": cf["op_families"],
            "negative_api_tokens": cf["api_tokens"][:40],
            "negative_path_role_tokens": sorted(set(cf["path_tokens"]))[:50],
        }

        if strict_scanner_negative:
            primary.append(rec)
        else:
            sensitivity.append(rec)

    same_repo = sorted([x for x in primary if x["same_repo"]], key=lambda x: (-x["score"], x["negative_case_id"]))
    cross_repo = sorted([x for x in primary if not x["same_repo"]], key=lambda x: (-x["score"], x["negative_case_id"]))
    sensitivity = sorted(sensitivity, key=lambda x: (-x["score"], x["negative_case_id"]))

    status["same_repo_primary_candidates"] = len(same_repo)
    status["cross_repo_primary_candidates"] = len(cross_repo)
    status["sensitivity_candidates"] = len(sensitivity)

    retained = []
    for stratum, vals in (
        ("D1_SAME_REPO", same_repo[:3]),
        ("D2_CROSS_REPO", cross_repo[:3]),
        ("SENSITIVITY_RULE_NEGATIVE", sensitivity[:2]),
    ):
        for x in vals:
            aid = anon_id(rid, x["negative_case_id"])
            sealed[aid] = {
                "root_id": rid,
                "positive_case_id": cid,
                "negative_case_id": x["negative_case_id"],
                "stratum": stratum,
                "positive_repository": pos["repository"],
                "negative_repository": cases[x["negative_case_id"]]["repository"],
                "target_scanners": target_scanners,
                "target_rules": target_rules,
                "target_paths": target_paths,
            }
            retained.append((aid, stratum, x))

    status["retained_candidates"] = len(retained)
    if not retained:
        status["exclusion_reasons"].append("NO_NEGATIVE_CANDIDATE_RETAINED")

    root_summary_rows.append(status)

    for aid, stratum, x in retained:
        review_records.append({
            "root_id": rid,
            "candidate_id": aid,
            "stratum": stratum,
            "root_primary_eligible": status["primary_eligible"],
            "positive_issue_title": norm_text(pos.get("issue_title","")),
            "positive_issue_body_excerpt": norm_text(pos.get("issue_body",""))[:1200],
            "positive_root_summary": norm_text(summary_text),
            "positive_operation_families": pos_ops,
            "positive_api_tokens": pos_api[:40],
            "positive_language_families": pos_families,
            "negative_issue_title": x["negative_issue_title"],
            "negative_issue_body_excerpt": x["negative_issue_body_excerpt"],
            "negative_operation_families": x["negative_op_families"],
            "negative_api_tokens": x["negative_api_tokens"],
            "score_components": {
                "total": x["score"],
                "task": x["task_similarity"],
                "operation_family": x["operation_family_similarity"],
                "path_role": x["path_role_similarity"],
                "api_weak": x["api_similarity_weak"],
            },
            "semantic_adjudication": {
                "same_implementation_decision_opportunity": None,
                "negative_could_legitimately_choose_M_or_alternative": None,
                "provisional_decision": "UNADJUDICATED"
            }
        })

# review artifacts intentionally omit repository names, scanner rule IDs, case IDs, exact file paths, and raw code
review_jsonl = OUT / "REVIEW_CANDIDATES.jsonl"
with review_jsonl.open("w", encoding="utf-8") as f:
    for r in review_records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

summary_csv = OUT / "ROOT_CENSUS.csv"
fields = [
    "root_id","case_present","primary_eligible","exclusion_reasons",
    "same_repo_primary_candidates","cross_repo_primary_candidates",
    "sensitivity_candidates","retained_candidates"
]
with summary_csv.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for r in root_summary_rows:
        z = dict(r)
        z["exclusion_reasons"] = ";".join(z["exclusion_reasons"])
        w.writerow({k:z.get(k,"") for k in fields})

public_summary = {
    "version": "T2_MECHANISM_OPPORTUNITY_CENSUS_v1",
    "group": GROUP,
    "roots_in_group": len(group_roots),
    "primary_eligible_roots": sum(bool(r["primary_eligible"]) for r in root_summary_rows),
    "roots_with_retained_candidate": sum(int(r["retained_candidates"]) > 0 for r in root_summary_rows),
    "retained_review_pairs": len(review_records),
    "same_repo_retained": sum(r["stratum"] == "D1_SAME_REPO" for r in review_records),
    "cross_repo_retained": sum(r["stratum"] == "D2_CROSS_REPO" for r in review_records),
    "sensitivity_retained": sum(r["stratum"] == "SENSITIVITY_RULE_NEGATIVE" for r in review_records),
    "note": "Review archive is anonymized and excludes repository names, exact case IDs, rule IDs, exact file paths, and raw code. The sealed mapping remains on-cluster."
}
(OUT / "PUBLIC_SUMMARY.json").write_text(json.dumps(public_summary, indent=2) + "\n", encoding="utf-8")

# cluster-only mapping; deliberately not included in review archive
SEALED_MAP.write_text(json.dumps(sealed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

if REVIEW_TAR.exists():
    REVIEW_TAR.unlink()
with tarfile.open(REVIEW_TAR, "w:gz") as tf:
    tf.add(OUT / "REVIEW_CANDIDATES.jsonl", arcname="REVIEW_CANDIDATES.jsonl")
    tf.add(OUT / "ROOT_CENSUS.csv", arcname="ROOT_CENSUS.csv")
    tf.add(OUT / "PUBLIC_SUMMARY.json", arcname="PUBLIC_SUMMARY.json")

sha = hashlib.sha256(REVIEW_TAR.read_bytes()).hexdigest()

print("STATUS=DONE")
print("GROUP=", GROUP)
print("ROOTS=", len(group_roots))
print("PRIMARY_ELIGIBLE=", public_summary["primary_eligible_roots"])
print("ROOTS_WITH_CANDIDATE=", public_summary["roots_with_retained_candidate"])
print("REVIEW_PAIRS=", len(review_records))
print("D1_RETAINED=", public_summary["same_repo_retained"])
print("D2_RETAINED=", public_summary["cross_repo_retained"])
print("SENSITIVITY_RETAINED=", public_summary["sensitivity_retained"])
print("REVIEW_TAR=", REVIEW_TAR)
print("SEALED_MAP_ON_CLUSTER=", SEALED_MAP)
print("SHA256=", sha)
PY
