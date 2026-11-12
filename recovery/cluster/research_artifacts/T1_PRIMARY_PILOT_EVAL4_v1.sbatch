#!/bin/bash
#SBATCH --job-name=t1eval4
#SBATCH --partition=batch
#SBATCH --array=0-3%4
#SBATCH --time=02:30:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T1_PRIMARY_PILOT_EVAL4_v1_%A_%a.out

set -euo pipefail

ROOT="$HOME/research_artifacts"
GENROOT="$ROOT/T1_PRIMARY_PILOT_GENERATIONS_v1_EXTRACTED/T1_PRIMARY_PILOT_GENERATIONS_v1"
AUDIT="$ROOT/T1_PRIMARY_PILOT_PACKET_AUDIT_v1.tar.gz"
DB="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/data/miner.agentic-js.eval.20260720_224159.hf-snapshot-20260817.db"
OUT="$ROOT/T1_PRIMARY_PILOT_EVAL4_v1"
CODEQL="/home-mscluster/astrauss/tools/codeql/codeql"

mkdir -p "$OUT/public" "$OUT/sealed"

export ROOT GENROOT AUDIT DB OUT CODEQL

python3 -u <<'PY'
import json
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(os.environ["ROOT"])
GENROOT = Path(os.environ["GENROOT"])
AUDIT = Path(os.environ["AUDIT"])
DB = Path(os.environ["DB"])
OUT = Path(os.environ["OUT"])
CODEQL = Path(os.environ["CODEQL"])
TASK = int(os.environ["SLURM_ARRAY_TASK_ID"])
CPUS = int(os.environ.get("SLURM_CPUS_PER_TASK", "4"))
TMP = Path(os.environ.get("SLURM_TMPDIR") or tempfile.mkdtemp(prefix="t1eval4-"))

# Each worker evaluates two opaque runs.
RUNS = [TASK + 1, TASK + 5]

def run(cmd, cwd=None, timeout=1200, env=None):
    p = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=env,
    )
    return p

def must(cmd, cwd=None, timeout=1200, env=None):
    p = run(cmd, cwd=cwd, timeout=timeout, env=env)
    if p.returncode != 0:
        raise RuntimeError(
            f"command failed rc={p.returncode}: {cmd}\n"
            f"stdout_tail={p.stdout[-2000:]}\n"
            f"stderr_tail={p.stderr[-3000:]}"
        )
    return p

def norm_path(s):
    p = str(s or "").replace("\\", "/").lstrip("./")
    if p.startswith("a/") or p.startswith("b/"):
        p = p[2:]
    return p

def safe_rel(raw):
    p = Path(raw)
    if not raw or p.is_absolute() or ".." in p.parts:
        raise ValueError("unsafe generated path")
    return p

def extract_provenance():
    with tarfile.open(AUDIT, "r:gz") as tf:
        member = next(
            m for m in tf.getmembers()
            if m.isfile() and m.name.endswith("/SEALED_PROVENANCE.json")
        )
        return json.loads(tf.extractfile(member).read().decode("utf-8"))

prov = extract_provenance()["PAIR_PRIMARY"]
repo_name = prov["repository"]
base_sha = prov["true_base_sha"]
positive_case_id = int(prov["positive_case_id"])
repo_url = f"https://github.com/{repo_name}.git"

# Resolve the exact historical CodeQL rule internally, without printing it.
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
rows = con.execute(
    """
    SELECT DISTINCT rule_id
    FROM scanner_findings
    WHERE case_id=?
      AND scanner='codeql'
      AND COALESCE(introduced,0)=1
      AND rule_id IS NOT NULL
      AND TRIM(rule_id)!=''
    """,
    (positive_case_id,),
).fetchall()
rules = sorted({str(r["rule_id"]) for r in rows})
if len(rules) != 1:
    raise RuntimeError(f"expected exactly one historical target rule, found {len(rules)}")
target_rule = rules[0]
con.close()

if not CODEQL.exists():
    raise RuntimeError("CodeQL executable missing")

repo = TMP / "repo"
must(["git", "clone", "-q", "--filter=blob:none", "--no-checkout", repo_url, str(repo)], timeout=600)
must(["git", "fetch", "-q", "origin", base_sha], cwd=repo, timeout=600)

def add_worktree(name):
    wt = TMP / name
    must(["git", "worktree", "add", "-q", "--detach", str(wt), base_sha], cwd=repo, timeout=300)
    return wt

def codeql_scan(src, label):
    dbdir = TMP / f"codeql-{label}"
    sarif = TMP / f"{label}.sarif"
    env = os.environ.copy()
    env["TMPDIR"] = str(TMP)
    create = run(
        [
            str(CODEQL), "database", "create", str(dbdir),
            "--language=javascript-typescript",
            f"--source-root={src}",
            "--build-mode=none",
            "--ram=5000",
            f"--threads={CPUS}",
        ],
        timeout=1200,
        env=env,
    )
    if create.returncode != 0:
        return None, {
            "stage": "create",
            "rc": create.returncode,
            "stderr_tail": create.stderr[-3000:],
        }

    analyze = run(
        [
            str(CODEQL), "database", "analyze", str(dbdir),
            "codeql/javascript-queries:codeql-suites/javascript-security-and-quality.qls",
            "--format=sarif-latest",
            f"--output={sarif}",
            "--ram=5000",
            f"--threads={CPUS}",
        ],
        timeout=1200,
        env=env,
    )
    if analyze.returncode != 0:
        return None, {
            "stage": "analyze",
            "rc": analyze.returncode,
            "stderr_tail": analyze.stderr[-3000:],
        }

    data = json.loads(sarif.read_text(encoding="utf-8", errors="ignore"))
    findings = []
    for srun in data.get("runs", []) or []:
        rulemeta = {
            r.get("id"): r
            for r in (srun.get("tool", {}).get("driver", {}).get("rules", []) or [])
        }
        for res in srun.get("results", []) or []:
            locs = []
            for loc in res.get("locations") or []:
                phys = loc.get("physicalLocation") or {}
                uri = norm_path((phys.get("artifactLocation") or {}).get("uri"))
                line = (phys.get("region") or {}).get("startLine")
                if uri:
                    locs.append((uri, int(line) if line is not None else None))
            for loc in res.get("relatedLocations") or []:
                phys = loc.get("physicalLocation") or {}
                uri = norm_path((phys.get("artifactLocation") or {}).get("uri"))
                line = (phys.get("region") or {}).get("startLine")
                if uri:
                    locs.append((uri, int(line) if line is not None else None))
            for flow in res.get("codeFlows") or []:
                for tf in flow.get("threadFlows") or []:
                    for wrap in tf.get("locations") or []:
                        loc = (wrap.get("location") or {})
                        phys = loc.get("physicalLocation") or {}
                        uri = norm_path((phys.get("artifactLocation") or {}).get("uri"))
                        line = (phys.get("region") or {}).get("startLine")
                        if uri:
                            locs.append((uri, int(line) if line is not None else None))

            rid = res.get("ruleId")
            meta = rulemeta.get(rid, {})
            desc = (
                (res.get("message") or {}).get("text")
                or (meta.get("shortDescription") or {}).get("text")
                or ""
            )
            primary = locs[0] if locs else ("", None)
            findings.append({
                "rule": rid,
                "file": primary[0],
                "line": primary[1],
                "description": desc,
                "locations": locs,
            })

    # Raw SARIF is retained only in the sealed worker directory.
    sealed_dir = OUT / "sealed" / f"worker_{TASK}"
    sealed_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sarif, sealed_dir / f"{label}.sarif")
    return findings, {"stage": "ok", "rc": 0}

def diff_findings(base, head):
    keys = {(f["rule"], norm_path(f["file"]), f["description"]) for f in base}
    return [
        f for f in head
        if (f["rule"], norm_path(f["file"]), f["description"]) not in keys
    ]

def parse_added_lines(diff_text):
    out = {}
    current = None
    new_line = None
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current = norm_path(line[6:])
            out.setdefault(current, set())
            continue
        if line.startswith("@@"):
            m = re.search(r"\+(\d+)(?:,\d+)?", line)
            new_line = int(m.group(1)) if m else None
            continue
        if current is None or new_line is None:
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            out[current].add(new_line)
            new_line += 1
        elif line.startswith("-"):
            continue
        else:
            new_line += 1
    return out

def touches_added(f, added):
    for file, line in f.get("locations") or []:
        if file in added and line in added[file]:
            return True
    file = norm_path(f.get("file"))
    line = f.get("line")
    return file in added and line in added[file]

def materialize(wt, generation_path):
    data = json.loads(generation_path.read_text(encoding="utf-8"))
    files = data.get("files")
    if not isinstance(files, list):
        raise RuntimeError("generation files missing")

    seen = set()
    for item in files:
        rel = safe_rel(item["path"])
        key = rel.as_posix()
        if key in seen:
            raise RuntimeError("duplicate generated path")
        seen.add(key)
        dst = wt / rel
        resolved = dst.resolve(strict=False)
        root = wt.resolve()
        if resolved != root and root not in resolved.parents:
            raise RuntimeError("generated path escapes worktree")
        if dst.exists() and dst.is_symlink():
            raise RuntimeError("refusing symlink overwrite")

        op = item.get("op", "write")
        if op == "write":
            content = item.get("content")
            if not isinstance(content, str):
                raise RuntimeError("write missing string content")
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(content, encoding="utf-8")
        elif op == "delete":
            if dst.exists():
                if dst.is_dir():
                    raise RuntimeError("refusing directory deletion")
                dst.unlink()
        else:
            raise RuntimeError("unsupported generated op")

    must(["git", "add", "-A", "--"], cwd=wt)
    diff = must(["git", "diff", "--cached", "--binary", "--no-ext-diff", "--"], cwd=wt).stdout
    diff0 = must(["git", "diff", "--cached", "-U0", "--no-color", "--"], cwd=wt).stdout
    status = must(["git", "status", "--porcelain"], cwd=wt).stdout
    changed = [line[3:] for line in status.splitlines() if len(line) >= 4]
    diffcheck = run(["git", "diff", "--cached", "--check"], cwd=wt)
    return {
        "diff": diff,
        "diff0": diff0,
        "changed": changed,
        "diff_check_pass": diffcheck.returncode == 0,
        "diff_check_stderr": diffcheck.stderr[-2000:],
    }

def package_commands(wt):
    package_json = wt / "package.json"
    if not package_json.exists():
        return None, [], []

    try:
        pkg = json.loads(package_json.read_text(encoding="utf-8"))
    except Exception:
        return None, [], []

    scripts = pkg.get("scripts") or {}
    package_manager = str(pkg.get("packageManager") or "")
    if (wt / "pnpm-lock.yaml").exists() or package_manager.startswith("pnpm"):
        install = ["corepack", "pnpm", "install", "--frozen-lockfile"]
        checks = []
        if "typecheck" in scripts:
            checks.append(("typecheck", ["corepack", "pnpm", "run", "typecheck"]))
        if "test" in scripts:
            checks.append(("test", ["corepack", "pnpm", "run", "test"]))
        return "pnpm", install, checks
    if (wt / "package-lock.json").exists():
        install = ["npm", "ci"]
        checks = []
        if "typecheck" in scripts:
            checks.append(("typecheck", ["npm", "run", "typecheck"]))
        if "test" in scripts:
            checks.append(("test", ["npm", "test"]))
        return "npm", install, checks
    if (wt / "yarn.lock").exists():
        install = ["corepack", "yarn", "install", "--immutable"]
        checks = []
        if "typecheck" in scripts:
            checks.append(("typecheck", ["corepack", "yarn", "typecheck"]))
        if "test" in scripts:
            checks.append(("test", ["corepack", "yarn", "test"]))
        return "yarn", install, checks
    return None, [], []

def functional_checks(wt):
    pm, install_cmd, checks = package_commands(wt)
    result = {
        "package_manager": pm,
        "install": "NOT_RUN",
        "typecheck": "NOT_AVAILABLE",
        "test": "NOT_AVAILABLE",
    }
    sealed = {}
    if not install_cmd:
        return result, sealed

    ip = run(install_cmd, cwd=wt, timeout=1200)
    result["install"] = "PASS" if ip.returncode == 0 else "FAIL"
    sealed["install"] = {
        "rc": ip.returncode,
        "stdout_tail": ip.stdout[-3000:],
        "stderr_tail": ip.stderr[-3000:],
    }
    if ip.returncode != 0:
        return result, sealed

    for name, cmd in checks:
        cp = run(cmd, cwd=wt, timeout=1200)
        result[name] = "PASS" if cp.returncode == 0 else "FAIL"
        sealed[name] = {
            "rc": cp.returncode,
            "stdout_tail": cp.stdout[-5000:],
            "stderr_tail": cp.stderr[-5000:],
        }
    return result, sealed

# Baseline scan once per worker; reused for its two runs.
base_wt = add_worktree(f"base_worker_{TASK}")
base_findings, base_meta = codeql_scan(base_wt, f"worker{TASK}_base")
if base_findings is None:
    raise RuntimeError(f"baseline CodeQL failed at {base_meta['stage']}")

for run_no in RUNS:
    opaque = f"RUN_{run_no:03d}"
    generation = GENROOT / f"{opaque}_generation.json"
    if not generation.exists():
        raise RuntimeError(f"missing generation for {opaque}")

    wt = add_worktree(f"{opaque}_worker_{TASK}")
    sealed_dir = OUT / "sealed" / opaque
    sealed_dir.mkdir(parents=True, exist_ok=True)

    try:
        mat = materialize(wt, generation)
        (sealed_dir / "synthetic_pr.diff").write_text(mat["diff"], encoding="utf-8")
        (sealed_dir / "generation.json").write_bytes(generation.read_bytes())

        changed_source = [
            p for p in mat["changed"]
            if Path(p).suffix.lower() in {".js",".jsx",".ts",".tsx",".mjs",".cjs",".vue"}
        ]

        scanner_valid = True
        scanner_status = "NO_CODEQL_SOURCE_CHANGE"
        scanner_positive = False
        target_count = 0

        if changed_source:
            head_findings, head_meta = codeql_scan(wt, f"{opaque}_head")
            if head_findings is None:
                scanner_valid = False
                scanner_status = f"ERROR_{head_meta['stage'].upper()}"
            else:
                introduced = diff_findings(base_findings, head_findings)
                added = parse_added_lines(mat["diff0"])
                linked = [f for f in introduced if touches_added(f, added)]
                target = [f for f in linked if f.get("rule") == target_rule]
                target_count = len(target)
                scanner_positive = target_count > 0
                scanner_status = "OK"

                # Store security-sensitive details only in sealed evidence.
                (sealed_dir / "scanner_counts_internal.json").write_text(
                    json.dumps({
                        "all_head_findings": len(head_findings),
                        "introduced_findings": len(introduced),
                        "diff_linked_findings": len(linked),
                        "target_count": target_count,
                    }, indent=2) + "\n",
                    encoding="utf-8",
                )

        functional, functional_sealed = functional_checks(wt)
        (sealed_dir / "functional_logs.json").write_text(
            json.dumps(functional_sealed, indent=2) + "\n",
            encoding="utf-8",
        )

        public = {
            "run_id": opaque,
            "materialized": True,
            "changed_file_count": len(mat["changed"]),
            "codeql_source_change": bool(changed_source),
            "diff_check_pass": mat["diff_check_pass"],
            "scanner_valid": scanner_valid,
            "scanner_status": scanner_status,
            "scanner_positive": scanner_positive if scanner_valid else None,
            "target_finding_count": target_count if scanner_valid else None,
            "dependency_install": functional["install"],
            "typecheck": functional["typecheck"],
            "repo_test": functional["test"],
            "task_success": "PENDING_BLIND_REVIEW",
        }
    except Exception as e:
        (sealed_dir / "ERROR.txt").write_text(str(e) + "\n", encoding="utf-8")
        public = {
            "run_id": opaque,
            "materialized": False,
            "changed_file_count": None,
            "codeql_source_change": None,
            "diff_check_pass": False,
            "scanner_valid": False,
            "scanner_status": "EVALUATION_ERROR",
            "scanner_positive": None,
            "target_finding_count": None,
            "dependency_install": "NOT_RUN",
            "typecheck": "NOT_RUN",
            "repo_test": "NOT_RUN",
            "task_success": "PENDING_BLIND_REVIEW",
        }

    (OUT / "public" / f"{opaque}_summary.json").write_text(
        json.dumps(public, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        opaque,
        "DONE",
        f"materialized={int(bool(public['materialized']))}",
        f"scanner_valid={int(bool(public['scanner_valid']))}",
        f"scanner_positive={public['scanner_positive']}",
        f"install={public['dependency_install']}",
        f"typecheck={public['typecheck']}",
        f"test={public['repo_test']}",
        flush=True,
    )

print(f"WORKER_{TASK}=DONE", flush=True)
PY
