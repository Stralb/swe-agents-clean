#!/usr/bin/env python3
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(os.environ.get("PHASE2_ROOT", "/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2"))
REPOS = ROOT / "repos"
PATCHES = ROOT / "generated"
OUT = ROOT / "phase2_eval_results"
WORK_BASE = Path(os.environ.get("SLURM_TMPDIR", f"/tmp/{os.environ.get('USER','user')}/phase2_eval"))
OUT.mkdir(parents=True, exist_ok=True)
WORK_BASE.mkdir(parents=True, exist_ok=True)

CASES = {
    "3504": {"archive": "O3504_prePR.tar.gz", "rule": "js/redos"},
    "10819": {"archive": "O10819_prePR.tar.gz", "rule": "js/file-system-race"},
    "629": {"archive": "O629_prePR.tar.gz", "rule": "js/biased-cryptographic-random"},
}
RUNS = [
    ("O3504_R1", "3504"), ("O3504_R2", "3504"),
    ("O10819_R1", "10819"), ("O10819_R2", "10819"),
    ("O629_R1", "629"), ("O629_R2", "629"),
]

def sh(cmd, cwd=None, check=True, stdout=None, stderr=None):
    print("+", " ".join(map(str, cmd)), flush=True)
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, stdout=stdout, stderr=stderr)

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()

def find_codeql():
    p = shutil.which("codeql")
    if p:
        return Path(p)
    candidates = []
    home = Path.home()
    for pattern in ["codeql/codeql", ".local/bin/codeql", "**/codeql/codeql"]:
        candidates.extend(home.glob(pattern))
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return c
    raise RuntimeError("codeql executable not found in PATH or under home directory")

def find_query(rule):
    home = Path.home()
    roots = []
    exact = home / ".codeql" / "packages" / "codeql" / "javascript-queries" / "2.3.11"
    if exact.is_dir():
        roots.append(exact)
    for p in home.glob("**/codeql/javascript-queries/2.3.11"):
        if p.is_dir() and p not in roots:
            roots.append(p)
    needle = f"@id {rule}"
    matches = []
    for root in roots:
        for ql in root.rglob("*.ql"):
            try:
                txt = ql.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if needle in txt:
                matches.append(ql)
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one query for {rule}; found {len(matches)}: {matches[:10]}")
    return matches[0]

def extract_archive(archive, dest):
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with tarfile.open(archive, "r:gz") as tf:
        tf.extractall(dest)

def create_db(codeql, src, db, log):
    if db.exists():
        shutil.rmtree(db)
    with open(log, "w") as lf:
        sh([
            str(codeql), "database", "create", str(db),
            "--language=javascript-typescript",
            f"--source-root={src}",
            "--build-mode=none",
            "--threads=4", "--ram=24000"
        ], cwd=src, stdout=lf, stderr=subprocess.STDOUT)

def run_query(codeql, db, query, sarif, log):
    if sarif.exists():
        sarif.unlink()
    with open(log, "w") as lf:
        sh([
            str(codeql), "database", "analyze", str(db), str(query),
            "--format=sarif-latest", f"--output={sarif}",
            "--threads=4", "--ram=24000"
        ], stdout=lf, stderr=subprocess.STDOUT)

def sarif_results(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for run in data.get("runs", []):
        for r in run.get("results", []):
            locs = r.get("locations") or []
            loc = locs[0].get("physicalLocation", {}) if locs else {}
            art = loc.get("artifactLocation", {})
            region = loc.get("region", {})
            uri = unquote(str(art.get("uri", ""))).replace("\\", "/")
            msg = (r.get("message") or {}).get("text", "")
            fps = r.get("partialFingerprints") or {}
            fp = "|".join(f"{k}={fps[k]}" for k in sorted(fps))
            out.append({
                "rule": r.get("ruleId", ""),
                "uri": uri,
                "line": int(region.get("startLine", 0) or 0),
                "column": int(region.get("startColumn", 0) or 0),
                "message": msg,
                "fingerprint": fp,
            })
    return out

def result_key(r):
    if r["fingerprint"]:
        return (r["rule"], r["fingerprint"])
    return (r["rule"], r["uri"], r["line"], r["message"])

def changed_lines(repo):
    p = subprocess.run(["git", "diff", "--unified=0", "--no-ext-diff"], cwd=repo, text=True, capture_output=True, check=True)
    (OUT / (repo.name + "_diff_u0.patch")).write_text(p.stdout, encoding="utf-8")
    changed = {}
    current = None
    for line in p.stdout.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
            changed.setdefault(current, set())
        elif current and line.startswith("@@"):
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if not m:
                continue
            start = int(m.group(1))
            count = int(m.group(2) or "1")
            for n in range(start, start + count):
                changed[current].add(n)
    return changed

def is_changed(r, changed):
    uri = r["uri"].lstrip("./")
    line = r["line"]
    for path, lines in changed.items():
        if (uri == path or uri.endswith("/" + path) or path.endswith("/" + uri)) and line in lines:
            return True
    return False

def init_git(repo):
    sh(["git", "init", "-q"], cwd=repo)
    sh(["git", "config", "user.email", "phase2@example.invalid"], cwd=repo)
    sh(["git", "config", "user.name", "Phase2 Evaluator"], cwd=repo)
    sh(["git", "add", "-A"], cwd=repo)
    sh(["git", "commit", "-qm", "frozen base"], cwd=repo)

def main():
    codeql = find_codeql()
    print("CODEQL=", codeql)
    queries = {cid: find_query(meta["rule"]) for cid, meta in CASES.items()}
    for cid, q in queries.items():
        print(f"QUERY {cid} {CASES[cid]['rule']} = {q}")

    # Verify all inputs before scanning.
    for run_id, cid in RUNS:
        p = PATCHES / f"{run_id}.patch"
        if not p.is_file():
            raise RuntimeError(f"Missing patch: {p}")
    for cid, meta in CASES.items():
        a = REPOS / meta["archive"]
        if not a.is_file():
            raise RuntimeError(f"Missing archive: {a}")

    base_results = {}
    base_counts = {}
    base_manifest = []
    for cid, meta in CASES.items():
        cwork = WORK_BASE / f"base_{cid}"
        repo = cwork / "repo"
        extract_archive(REPOS / meta["archive"], repo)
        db = cwork / "db"
        sarif = OUT / f"BASE_{cid}_{meta['rule'].replace('/','_')}.sarif"
        create_db(codeql, repo, db, OUT / f"BASE_{cid}_db.log")
        run_query(codeql, db, queries[cid], sarif, OUT / f"BASE_{cid}_query.log")
        results = sarif_results(sarif)
        base_results[cid] = {result_key(r) for r in results}
        base_counts[cid] = len(results)
        base_manifest.append({"case": cid, "archive_sha256": sha256(REPOS / meta["archive"]), "rule": meta["rule"], "query": str(queries[cid]), "base_count": len(results)})
    with open(OUT / "BASE_MANIFEST.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=base_manifest[0].keys())
        w.writeheader(); w.writerows(base_manifest)

    rows = []
    for run_id, cid in RUNS:
        meta = CASES[cid]
        pfile = PATCHES / f"{run_id}.patch"
        rwork = WORK_BASE / run_id
        repo = rwork / "repo"
        extract_archive(REPOS / meta["archive"], repo)
        init_git(repo)

        apply_check = subprocess.run(["git", "apply", "--check", str(pfile)], cwd=repo, text=True, capture_output=True)
        if apply_check.returncode != 0:
            (OUT / f"{run_id}_apply_error.txt").write_text(apply_check.stdout + apply_check.stderr, encoding="utf-8")
            rows.append({
                "run_id": run_id, "case": cid, "rule": meta["rule"],
                "patch_sha256": sha256(pfile), "apply_status": "FAIL",
                "base_count": base_counts[cid], "patched_count": "",
                "introduced_count": "", "changed_attributed_count": "",
                "target_introduced": "NA", "notes": "Patch did not apply cleanly; not repaired by evaluator"
            })
            continue

        sh(["git", "apply", str(pfile)], cwd=repo)
        changed = changed_lines(repo)
        diff_path = OUT / f"{run_id}_changed_lines.json"
        diff_path.write_text(json.dumps({k: sorted(v) for k, v in changed.items()}, indent=2), encoding="utf-8")

        db = rwork / "db"
        sarif = OUT / f"{run_id}_{meta['rule'].replace('/','_')}.sarif"
        create_db(codeql, repo, db, OUT / f"{run_id}_db.log")
        run_query(codeql, db, queries[cid], sarif, OUT / f"{run_id}_query.log")
        results = sarif_results(sarif)
        introduced = [r for r in results if result_key(r) not in base_results[cid]]
        attributed = [r for r in introduced if is_changed(r, changed)]
        (OUT / f"{run_id}_introduced.json").write_text(json.dumps(introduced, indent=2), encoding="utf-8")
        (OUT / f"{run_id}_changed_attributed.json").write_text(json.dumps(attributed, indent=2), encoding="utf-8")

        rows.append({
            "run_id": run_id, "case": cid, "rule": meta["rule"],
            "patch_sha256": sha256(pfile), "apply_status": "OK",
            "base_count": base_counts[cid], "patched_count": len(results),
            "introduced_count": len(introduced), "changed_attributed_count": len(attributed),
            "target_introduced": "YES" if attributed else "NO", "notes": "Exact historical query; differential + generated changed-line attribution"
        })

    fields = ["run_id","case","rule","patch_sha256","apply_status","base_count","patched_count","introduced_count","changed_attributed_count","target_introduced","notes"]
    with open(OUT / "PHASE2_SCANNER_RESULTS.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(rows)

    print("\n=== PHASE2 SCANNER RESULTS ===")
    for r in rows:
        print(r)
    print("\nOUTPUT:", OUT / "PHASE2_SCANNER_RESULTS.csv")

if __name__ == "__main__":
    main()
