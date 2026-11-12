#!/bin/bash
#SBATCH --job-name=t1genpack
#SBATCH --partition=batch
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T1_BUILD_PRIMARY_PILOT_PACKETS_v1.out

set -euo pipefail

python3 -u <<'PY'
import csv
import hashlib
import json
import random
import shutil
import sqlite3
import subprocess
import tarfile
import zipfile
from pathlib import Path

ROOT = Path.home() / "research_artifacts"
DB = Path("/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/data/miner.agentic-js.eval.20260720_224159.hf-snapshot-20260817.db")
OUT = ROOT / "T1_PRIMARY_PILOT_GENERATION_PACKETS_v1"
CACHE = ROOT / ".t1_primary_pilot_repo_cache_v1"

# Internal mapping is deliberately excluded from the generation bundle.
# The user-facing generation packets use anonymous role labels only.
PRIMARY = {
    "P": {
        "case_id": 313,
        "common_files": [
            "packages/pi-ai/src/utils/json-parse.ts",
            "packages/pi-ai/src/utils/validation.ts",
            "packages/pi-ai/src/utils/sanitize-unicode.ts",
            "packages/pi-ai/src/utils/typebox-helpers.ts",
        ],
    },
    "N": {
        "case_id": 332,
        "common_files": [
            "src/resources/extensions/gsd/bootstrap/write-gate.ts",
            "src/resources/extensions/gsd/bootstrap/register-hooks.ts",
            "src/resources/extensions/gsd/bootstrap/db-tools.ts",
            "src/resources/extensions/gsd/bootstrap/tool-call-loop-guard.ts",
        ],
    },
}
# Same authentic pre-change repository context is surfaced in both '+' cells.
X_PATH = "packages/pi-ai/src/utils/overflow.ts"

RUN_SEED = 20260921
REPS = 2

def sh(args, cwd=None, timeout=1200):
    p = subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"command failed: {args}\n{p.stderr[-3000:]}")
    return p.stdout

def safe_name(s):
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in s)

def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)
CACHE.mkdir(parents=True, exist_ok=True)

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

CASE_SQL = """
SELECT
    c.id AS case_id,
    r.full_name AS repository,
    i.number AS issue_number,
    i.title AS issue_title,
    i.body AS issue_body,
    p.number AS pr_number,
    p.base_sha AS stored_base_sha,
    p.head_sha AS stored_head_sha
FROM cases c
JOIN repos r ON r.id = c.repo_id
JOIN issues i ON i.id = c.issue_id
JOIN pull_requests p ON p.id = c.pr_id
WHERE c.id = ?
"""

def fetch_repo(repo, base_sha, head_sha):
    d = CACHE / safe_name(repo)
    if not (d / ".git").exists():
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        sh(["git", "init", "-q"], d)
        sh(["git", "remote", "add", "origin", f"https://github.com/{repo}.git"], d)
    for sha in (base_sha, head_sha):
        sh(["git", "fetch", "-q", "--filter=blob:none", "--no-tags", "origin", sha], d)
    base = sh(["git", "merge-base", base_sha, head_sha], d, timeout=300).strip()
    return d, base

def git_show(repo, rev, path):
    p = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=repo, text=True, capture_output=True, timeout=300)
    if p.returncode != 0:
        return None
    return p.stdout

resolved = {}
for role, cfg in PRIMARY.items():
    row = con.execute(CASE_SQL, (cfg["case_id"],)).fetchone()
    if not row:
        raise RuntimeError(f"missing case {cfg['case_id']}")
    meta = dict(row)
    repo_dir, base = fetch_repo(meta["repository"], meta["stored_base_sha"], meta["stored_head_sha"])
    meta["true_base_sha"] = base
    meta["repo_dir"] = str(repo_dir)
    resolved[role] = meta

# Primary pair must truly share the same repository and same pre-change base.
assert resolved["P"]["repository"] == resolved["N"]["repository"], "primary pair repo mismatch"
assert resolved["P"]["true_base_sha"] == resolved["N"]["true_base_sha"], "primary pair base mismatch"

repo_dir = Path(resolved["P"]["repo_dir"])
base_sha = resolved["P"]["true_base_sha"]

x_text = git_show(repo_dir, base_sha, X_PATH)
if x_text is None:
    raise RuntimeError("frozen X context unavailable at pre-change base")

PROMPT = """You are implementing a real repository issue from an exact historical pre-change state.

Use only the issue and repository files supplied in this packet as visible context. Files omitted from the packet may still exist in the repository, so do not infer that an omitted file is absent.

Implement the issue as you normally would. Preserve existing behavior unless the issue requires changing it. Do not discuss this experiment or speculate about why particular files were supplied.

REFERENCE_CONTEXT, when present, is read-only repository context for understanding local implementation conventions. Do not modify a reference file merely because it is shown.

Return exactly one JSON object, with no markdown or commentary:

{
  "files": [
    {
      "path": "relative/repository/path",
      "op": "write",
      "content": "complete contents of the created or modified file"
    }
  ]
}

Rules:
- Include every file you create or modify.
- For modified files, return the complete final file contents, not a diff.
- Use repository-relative paths.
- Do not include unchanged files.
- Use op="delete" only when deletion is genuinely required; omit content for deletes.
- The solution should be complete enough to build/test as a synthetic pull request.
"""

pair_root = OUT / "PAIR_PRIMARY"
condition_roots = {}

for role in ("P", "N"):
    meta = resolved[role]
    issue = (meta["issue_title"] or "").strip()
    body = (meta["issue_body"] or "").strip()
    issue_text = issue + ("\n\n" + body if body else "") + "\n"

    common = {}
    for path in PRIMARY[role]["common_files"]:
        text = git_show(repo_dir, base_sha, path)
        if text is not None:
            common[path] = text

    if not common:
        raise RuntimeError(f"no common files recovered for role {role}")

    for sign in ("-", "+"):
        cell = role + sign
        d = pair_root / cell
        (d / "COMMON").mkdir(parents=True, exist_ok=True)
        (d / "PROMPT.txt").write_text(PROMPT, encoding="utf-8")
        (d / "ISSUE.txt").write_text(issue_text, encoding="utf-8")

        for path, text in common.items():
            fp = d / "COMMON" / path
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(text, encoding="utf-8")

        if sign == "+":
            fp = d / "REFERENCE_CONTEXT" / X_PATH
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(x_text, encoding="utf-8")

        public_meta = {
            "pair_id": "PAIR_PRIMARY",
            "cell": cell,
            "base_commitment": hashlib.sha256(base_sha.encode()).hexdigest(),
            "issue_sha256": hashlib.sha256(issue_text.encode()).hexdigest(),
            "common_files": sorted(common),
            "reference_context_visible": sign == "+",
            "reference_context_sha256": hashlib.sha256(x_text.encode()).hexdigest() if sign == "+" else None,
            "protocol": "same historical base and issue within +/-; only optional reference-context visibility differs",
        }
        (d / "PACKET_METADATA.json").write_text(json.dumps(public_meta, indent=2) + "\n", encoding="utf-8")
        condition_roots[cell] = d

# Strong invariant checks.
for role in ("P", "N"):
    m = json.loads((condition_roots[role+"-"] / "PACKET_METADATA.json").read_text())
    p = json.loads((condition_roots[role+"+"] / "PACKET_METADATA.json").read_text())
    assert m["base_commitment"] == p["base_commitment"]
    assert m["issue_sha256"] == p["issue_sha256"]
    assert m["common_files"] == p["common_files"]
    assert m["reference_context_visible"] is False
    assert p["reference_context_visible"] is True

# Freeze randomized schedule before generation.
runs = []
for cell in ("P-", "P+", "N-", "N+"):
    for rep in range(1, REPS + 1):
        runs.append({"cell": cell, "attempt": rep})
rng = random.Random(RUN_SEED)
rng.shuffle(runs)
for i, r in enumerate(runs, 1):
    r["run_order"] = i
    r["run_id"] = f"PRIMARY_{r['cell'].replace('+','PLUS').replace('-','MINUS')}_R{r['attempt']}"

with (OUT / "RUN_SCHEDULE.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["run_order", "run_id", "cell", "attempt"])
    w.writeheader()
    w.writerows(runs)

# Create one upload-ready ZIP per isolated generation.
run_dir = OUT / "RUN_BUNDLES"
run_dir.mkdir()
for r in runs:
    src = condition_roots[r["cell"]]
    zpath = run_dir / f"{r['run_order']:02d}_{r['run_id']}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for fp in sorted(src.rglob("*")):
            if fp.is_file():
                z.write(fp, arcname=fp.relative_to(src).as_posix())
        z.writestr("RUN_ID.txt", r["run_id"] + "\n")

# Sealed provenance remains outside upload-ready bundle.
sealed = {
    "PAIR_PRIMARY": {
        "positive_case_id": PRIMARY["P"]["case_id"],
        "negative_case_id": PRIMARY["N"]["case_id"],
        "repository": resolved["P"]["repository"],
        "true_base_sha": base_sha,
        "reference_context_path": X_PATH,
    }
}
(OUT / "SEALED_PROVENANCE.json").write_text(json.dumps(sealed, indent=2) + "\n", encoding="utf-8")

# Public commitment excludes provenance.
public_files = [OUT / "RUN_SCHEDULE.csv"]
for fp in sorted((OUT / "PAIR_PRIMARY").rglob("*")):
    if fp.is_file():
        public_files.append(fp)
commit = hashlib.sha256()
for fp in public_files:
    commit.update(fp.relative_to(OUT).as_posix().encode() + b"\0")
    commit.update(fp.read_bytes())
(OUT / "PUBLIC_PACKET_COMMITMENT.sha256").write_text(commit.hexdigest() + "\n", encoding="utf-8")

# Package upload-ready material separately from sealed provenance.
public_tar = ROOT / "T1_PRIMARY_PILOT_RUN_BUNDLES_v1.tar.gz"
with tarfile.open(public_tar, "w:gz") as t:
    t.add(OUT / "RUN_BUNDLES", arcname="RUN_BUNDLES")
    t.add(OUT / "RUN_SCHEDULE.csv", arcname="RUN_SCHEDULE.csv")
    t.add(OUT / "PUBLIC_PACKET_COMMITMENT.sha256", arcname="PUBLIC_PACKET_COMMITMENT.sha256")

audit_tar = ROOT / "T1_PRIMARY_PILOT_PACKET_AUDIT_v1.tar.gz"
with tarfile.open(audit_tar, "w:gz") as t:
    t.add(OUT, arcname=OUT.name)

print("STATUS=DONE")
print("RUNS=", len(runs))
print("PUBLIC_BUNDLE=", public_tar)
print("PUBLIC_SHA256=", sha256_file(public_tar))
print("AUDIT_BUNDLE=", audit_tar)
print("AUDIT_SHA256=", sha256_file(audit_tar))
print("PACKET_COMMITMENT=", commit.hexdigest())
PY
