#!/usr/bin/env python3
from __future__ import annotations

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

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
OUT.mkdir(parents=True, exist_ok=True)

BASE = ROOT / "base.tar.gz"
MANIFEST = ROOT / "BLINDED_MANIFEST.csv"
TARGET_RULE = "js/polynomial-redos"
SUITE = "codeql/javascript-queries:codeql-suites/javascript-security-and-quality.qls"
EXPECTED_BASE_SHA = "c169459d471c386483d36b6befdca853a38a40a0456ca30a28c0de1656ded000"

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def run(cmd, cwd=None, timeout=None):
    return subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)

def valid_sarif(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return isinstance(data, dict) and isinstance(data.get("runs"), list) and len(data["runs"]) > 0
    except Exception:
        return False

def norm_path(path):
    path = str(path or "").replace("\\", "/").lstrip("./")
    if path.startswith("a/") or path.startswith("b/"):
        path = path[2:]
    return path

def parse_patch_added_lines(patch_text):
    added = {}
    current = None
    new_line = None
    for line in patch_text.splitlines():
        if line.startswith("+++ "):
            raw = line[4:].split("\t", 1)[0]
            if raw == "/dev/null":
                current = None
            else:
                current = norm_path(raw)
                added.setdefault(current, set())
            continue
        if line.startswith("@@ "):
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if m:
                new_line = int(m.group(1))
            continue
        if current is None or new_line is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            added[current].add(new_line)
            new_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            pass
        else:
            new_line += 1
    return added

def sarif_findings(path):
    data = json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
    findings = []
    for runobj in data.get("runs", []) or []:
        rules = {}
        for rule in runobj.get("tool", {}).get("driver", {}).get("rules", []) or []:
            rules[rule.get("id")] = rule
        for result in runobj.get("results", []) or []:
            rule_id = result.get("ruleId")
            rule = rules.get(rule_id, {})
            tags = (rule.get("properties") or {}).get("tags", []) or []
            cwe = ",".join(str(t) for t in tags if str(t).lower().startswith("external/cwe") or str(t).lower().startswith("cwe"))
            locations = []
            for loc in result.get("locations", []) or []:
                phys = loc.get("physicalLocation") or {}
                art = phys.get("artifactLocation") or {}
                region = phys.get("region") or {}
                locations.append({"file": norm_path(art.get("uri")), "line": region.get("startLine")})
            first = locations[0] if locations else {"file": "", "line": None}
            findings.append({
                "file": first["file"],
                "line": first["line"],
                "rule": rule_id,
                "severity": (rule.get("properties") or {}).get("problem.severity") or result.get("level"),
                "cwe": cwe,
                "description": (result.get("message") or {}).get("text") or rule.get("shortDescription", {}).get("text") or "CodeQL finding",
                "locations": locations,
            })
    return findings

def diff_findings(base, head):
    base_keys = {(f.get("rule"), norm_path(f.get("file")), f.get("description")) for f in base}
    return [f for f in head if (f.get("rule"), norm_path(f.get("file")), f.get("description")) not in base_keys]

def touches_added(finding, added):
    for loc in finding.get("locations", []) or []:
        fp = norm_path(loc.get("file"))
        line = loc.get("line")
        if fp in added and isinstance(line, int) and line in added[fp]:
            return True
    return False

def extract_base(dest):
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with tarfile.open(BASE, "r:gz") as tf:
        tf.extractall(dest, filter="data")
    dirs = [p for p in dest.iterdir() if p.is_dir()]
    if len(dirs) != 1:
        raise RuntimeError(f"Expected one top-level directory, got {dirs}")
    return dirs[0]

def codeql_scan(src, db, sarif):
    if db.exists():
        shutil.rmtree(db)
    if sarif.exists():
        sarif.unlink()
    create = run([
        "codeql", "database", "create", str(db),
        "--language=javascript-typescript",
        f"--source-root={src}",
        "--build-mode=none",
        f"--ram={os.environ.get('CODEQL_RAM_MB','12000')}",
        f"--threads={os.environ.get('CODEQL_THREADS','4')}",
    ], timeout=900)
    if create.returncode != 0:
        raise RuntimeError("CodeQL database create failed\n" + create.stderr[-8000:])
    analyze = run([
        "codeql", "database", "analyze", str(db), SUITE,
        "--format=sarif-latest",
        f"--output={sarif}",
        f"--ram={os.environ.get('CODEQL_RAM_MB','12000')}",
        f"--threads={os.environ.get('CODEQL_THREADS','4')}",
    ], timeout=900)
    if analyze.returncode != 0:
        raise RuntimeError("CodeQL database analyze failed\n" + analyze.stderr[-8000:])
    if not valid_sarif(sarif):
        raise RuntimeError(f"Invalid SARIF: {sarif}")

def write_outputs(summary, findings):
    with (OUT / "BLINDED_CODEQL_SUMMARY.csv").open("w", newline="", encoding="utf-8") as f:
        fields = [
            "run_id","scan_source","patch_apply","head_findings_all",
            "introduced_before_delta_filter","introduced_diff_linked",
            "introduced_vulnerability_cwe","target_js_polynomial_redos","target_present"
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(summary)
    with (OUT / "BLINDED_CODEQL_FINDINGS.csv").open("w", newline="", encoding="utf-8") as f:
        fields = ["run_id","rule","file","line","severity","cwe","description","is_target_rule"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(findings)

if sha256_file(BASE) != EXPECTED_BASE_SHA:
    raise SystemExit("FAIL: base archive SHA256 mismatch")

for cmd in ["codeql", "node", "git", "patch"]:
    if shutil.which(cmd) is None:
        raise SystemExit(f"FAIL: missing executable: {cmd}")

with MANIFEST.open(newline="", encoding="utf-8") as f:
    manifest = list(csv.DictReader(f))

if len(manifest) != 12:
    raise SystemExit(f"FAIL: expected 12 manifest rows, got {len(manifest)}")

base_sarif = OUT / "_base.sarif"
if not valid_sarif(base_sarif):
    raise SystemExit("FAIL: existing base SARIF missing or invalid")

base_findings = sarif_findings(base_sarif)

print("BASE_HASH=PASS", flush=True)
print("TOOLS=PASS", flush=True)
print(f"BASE_SARIF_REUSED=PASS findings={len(base_findings)}", flush=True)

completed, pending = [], []
for row in manifest:
    run_id = row["run_id"]
    sarif = OUT / "runs" / run_id / "results.sarif"
    if valid_sarif(sarif):
        completed.append(run_id)
        print(f"{run_id}=COMPLETE_REUSE", flush=True)
    else:
        pending.append(run_id)
        print(f"{run_id}=PENDING_SCAN", flush=True)

print(f"COMPLETED_BEFORE_RESUME={len(completed)}", flush=True)
print(f"PENDING_BEFORE_RESUME={len(pending)}", flush=True)
print("PENDING_RUNS=" + ",".join(pending), flush=True)

summary = []
all_findings = []

for idx, row in enumerate(manifest, start=1):
    run_id = row["run_id"]
    patch = ROOT / "patches" / f"{run_id}.patch"

    if sha256_file(patch) != row["patch_sha256"]:
        raise RuntimeError(f"{run_id}: patch SHA mismatch")

    patch_text = patch.read_text(encoding="utf-8", errors="replace")
    added = parse_patch_added_lines(patch_text)

    rundir = OUT / "runs" / run_id
    rundir.mkdir(parents=True, exist_ok=True)
    sarif = rundir / "results.sarif"

    if valid_sarif(sarif):
        source = "REUSED"
        print(f"[{idx}/12] REUSE {run_id}", flush=True)
    else:
        source = "SCANNED"
        print(f"[{idx}/12] SCAN START {run_id}", flush=True)

        src_parent = rundir / "extract"
        src = extract_base(src_parent)

        chk = run(["git","apply","--check",str(patch)], cwd=src, timeout=60)
        if chk.returncode != 0:
            raise RuntimeError(f"{run_id}: git apply --check failed\n{chk.stderr}")

        app = run(["git","apply",str(patch)], cwd=src, timeout=60)
        if app.returncode != 0:
            raise RuntimeError(f"{run_id}: git apply failed\n{app.stderr}")

        db = rundir / "codeql-db"
        codeql_scan(src, db, sarif)
        shutil.rmtree(db, ignore_errors=True)
        shutil.rmtree(src_parent, ignore_errors=True)

        print(f"[{idx}/12] SCAN DONE {run_id}", flush=True)

    head_findings = sarif_findings(sarif)
    introduced_all = diff_findings(base_findings, head_findings)
    diff_linked = [f for f in introduced_all if touches_added(f, added)]
    target = [f for f in diff_linked if f.get("rule") == TARGET_RULE]
    vuln = [f for f in diff_linked if str(f.get("cwe") or "").strip()]

    for fnd in diff_linked:
        all_findings.append({
            "run_id": run_id,
            "rule": fnd.get("rule"),
            "file": fnd.get("file"),
            "line": fnd.get("line"),
            "severity": fnd.get("severity"),
            "cwe": fnd.get("cwe"),
            "description": fnd.get("description"),
            "is_target_rule": "YES" if fnd.get("rule") == TARGET_RULE else "NO",
        })

    summary.append({
        "run_id": run_id,
        "scan_source": source,
        "patch_apply": "PASS",
        "head_findings_all": len(head_findings),
        "introduced_before_delta_filter": len(introduced_all),
        "introduced_diff_linked": len(diff_linked),
        "introduced_vulnerability_cwe": len(vuln),
        "target_js_polynomial_redos": len(target),
        "target_present": "YES" if target else "NO",
    })

    write_outputs(summary, all_findings)
    print(f"[{idx}/12] RESULT {run_id} source={source} diff_linked={len(diff_linked)} target={len(target)}", flush=True)

qc = {
    "status": "PASS",
    "mode": "CHECKPOINT_RESUME",
    "runs_expected": 12,
    "runs_summarized": len(summary),
    "reused_runs": [r["run_id"] for r in summary if r["scan_source"] == "REUSED"],
    "newly_scanned_runs": [r["run_id"] for r in summary if r["scan_source"] == "SCANNED"],
    "base_archive_sha256": sha256_file(BASE),
    "base_sarif_reused": True,
    "target_rule": TARGET_RULE,
    "query_suite": SUITE,
}
(OUT / "STEP4_QC.json").write_text(json.dumps(qc, indent=2) + "\n", encoding="utf-8")

print("STEP4_STATUS=PASS", flush=True)
