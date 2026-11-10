#!/bin/bash
#SBATCH --job-name=t1_histfix
#SBATCH --partition=bigbatch
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T1_HISTORICAL_REPLAY_FIX_v2.out

ROOT="$HOME/research_artifacts"
V1="$ROOT/T1_VALIDATE30_BIGBATCH_v1"
OUT="$ROOT/T1_HISTORICAL_REPLAY_FIX_v2"
ARCHIVE="$ROOT/T1_HISTORICAL_REPLAY_FIX_v2_RESULTS.tar.gz"

rm -rf "$OUT"
mkdir -p "$OUT"

python3 - "$V1" "$OUT" <<'PY'
from pathlib import Path
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

V1 = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()

ROOTS = {
    "R1": {
        "root_id": "CROOT-00668-01",
        "repo": "Yeachan-Heo/oh-my-claudecode",
        "pr": 258,
        "scanner": "codeql",
        "rule": "js/file-system-race",
        "target_files": ["src/hud/state.ts"],
    },
    "R2": {
        "root_id": "CROOT-16534-01",
        "repo": "coreyhaines31/marketingskills",
        "pr": 326,
        "scanner": "codeql",
        "rule": "js/file-system-race",
        "target_files": [".github/scripts/sync-skills.js"],
    },
    "R3": {
        "root_id": "CROOT-04131-01",
        "repo": "ruvnet/ruflo",
        "pr": 2725,
        "scanner": "semgrep",
        "rule": "javascript.lang.security.detect-child-process.detect-child-process",
        "target_files": ["plugins/ruflo-core/scripts/ruflo-hook.cjs"],
    },
    "R4": {
        "root_id": "CROOT-10819-01",
        "repo": "evilz/vscode-reveal",
        "pr": 1477,
        "scanner": "codeql",
        "rule": "js/file-system-race",
        "target_files": ["src/RevealServer.ts"],
    },
    "R5": {
        "root_id": "CROOT-10339-01",
        "repo": "binaricat/Netcatty",
        "pr": 2354,
        "scanner": "codeql",
        "rule": "js/clear-text-storage-of-sensitive-data",
        "target_files": [
            "application/defaultKeyPassphrases.ts",
            "components/vault/useVaultImportHandlers.ts",
        ],
    },
    "R6": {
        "root_id": "CROOT-16213-01",
        "repo": "thomasnordquist/MQTT-Explorer",
        "pr": 942,
        "scanner": "codeql",
        "rule": "js/clear-text-storage-of-sensitive-data",
        "target_files": [
            "app/src/browserEventBus.ts",
            "app/src/components/BrowserAuthWrapper.tsx",
        ],
    },
}

def run(args, cwd=None, timeout=None):
    p = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return p.returncode, p.stdout, p.stderr

def path_norm(p):
    p = urllib.parse.unquote(str(p or "")).replace("\\", "/")
    if p.startswith("file://"):
        p = p[7:]
    return p.lstrip("./")

def parse_added_lines(diff_text):
    changed = {}
    cur = None
    new_line = None

    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
            changed.setdefault(cur, set())
            continue

        m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
        if m:
            new_line = int(m.group(1))
            continue

        if cur is None or new_line is None:
            continue

        if line.startswith("+") and not line.startswith("+++"):
            changed[cur].add(new_line)
            new_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            pass
        elif line.startswith(" "):
            new_line += 1

    return changed

def load_sarif_exact(path, exact_rule):
    data = json.loads(path.read_text(errors="replace"))
    results = []

    for run_obj in data.get("runs", []):
        for result in run_obj.get("results", []):
            if result.get("ruleId") != exact_rule:
                continue

            locs = []

            for loc in result.get("locations", []):
                pl = loc.get("physicalLocation", {})
                region = pl.get("region", {})
                locs.append({
                    "path": pl.get("artifactLocation", {}).get("uri", ""),
                    "start": region.get("startLine"),
                    "end": region.get("endLine", region.get("startLine")),
                    "kind": "primary",
                })

            for flow in result.get("codeFlows", []):
                for thread in flow.get("threadFlows", []):
                    for flow_loc in thread.get("locations", []):
                        loc = flow_loc.get("location", {})
                        pl = loc.get("physicalLocation", {})
                        region = pl.get("region", {})
                        locs.append({
                            "path": pl.get("artifactLocation", {}).get("uri", ""),
                            "start": region.get("startLine"),
                            "end": region.get("endLine", region.get("startLine")),
                            "kind": "codeflow",
                        })

            results.append({
                "message": result.get("message", {}).get("text", ""),
                "locations": locs,
            })

    return results

def location_hits_changed(loc, changed):
    p = path_norm(loc.get("path"))

    matched_path = None
    for cp in changed:
        if p == cp or p.endswith("/" + cp):
            matched_path = cp
            break

    if not matched_path:
        return False

    a = loc.get("start")
    b = loc.get("end") or a

    if a is None:
        return False

    return any(
        line in changed[matched_path]
        for line in range(int(a), int(b) + 1)
    )

def result_hits_changed(result, changed):
    return any(location_hits_changed(loc, changed) for loc in result["locations"])

def resolve_repo(slot, cfg, commits):
    existing = V1 / "_work" / "repos" / slot
    if (existing / ".git").exists():
        return existing

    repo_dir = OUT / "_repos" / slot
    if repo_dir.exists():
        shutil.rmtree(repo_dir)
    repo_dir.mkdir(parents=True)

    run(["git", "init", "-q"], cwd=repo_dir)
    run(["git", "remote", "add", "origin", f"https://github.com/{cfg['repo']}.git"], cwd=repo_dir)

    wanted = [commits["base_sha"], commits["head_sha"]]
    for sha in wanted:
        rc, so, se = run(
            ["git", "fetch", "-q", "--no-tags", "origin", sha],
            cwd=repo_dir,
            timeout=900,
        )
        if rc != 0:
            raise RuntimeError(f"fetch failed for {slot} {sha}: {se[-2000:]}")

    return repo_dir

def checkout(repo_dir, sha, dst):
    if dst.exists():
        shutil.rmtree(dst)
    rc, so, se = run(["git", "clone", "-q", "--shared", str(repo_dir), str(dst)])
    if rc != 0:
        raise RuntimeError(se[-2000:])
    rc, so, se = run(["git", "checkout", "-q", "--detach", sha], cwd=dst)
    if rc != 0:
        raise RuntimeError(se[-2000:])

def find_semgrep():
    candidates = [
        shutil.which("semgrep"),
        str(Path.home() / ".local" / "bin" / "semgrep"),
        str(Path.home() / "new" / "malicious-issue-miner-rate-smart" / ".venv" / "bin" / "semgrep"),
        str(Path.home() / "new" / "malicious-issue-miner-rate-smart" / "venv" / "bin" / "semgrep"),
        str(Path.home() / "malicious-issue-miner-rate-smart" / ".venv" / "bin" / "semgrep"),
    ]
    for c in candidates:
        if c and Path(c).exists() and os.access(c, os.X_OK):
            return c, "existing"

    tmp = Path(os.environ.get("SLURM_TMPDIR", "/tmp")) / "t1_semgrep_venv"
    rc, so, se = run([sys.executable, "-m", "venv", str(tmp)], timeout=300)
    if rc != 0:
        return None, f"venv_create_failed:{se[-1000:]}"

    pip = tmp / "bin" / "pip"
    semgrep = tmp / "bin" / "semgrep"

    rc, so, se = run(
        [str(pip), "install", "--quiet", "semgrep"],
        timeout=1200,
    )
    (OUT / "semgrep_install.stdout.txt").write_text(so, encoding="utf-8")
    (OUT / "semgrep_install.stderr.txt").write_text(se, encoding="utf-8")

    if rc == 0 and semgrep.exists():
        return str(semgrep), "installed_in_slurm_tmp"

    return None, f"pip_install_failed_rc={rc}"

def semgrep_scan(semgrep, snapshot, target_files, exact_rule, out_json):
    targets = [str(snapshot / p) for p in target_files if (snapshot / p).exists()]
    if not targets:
        return {
            "status": "TARGET_FILES_MISSING",
            "count": None,
            "results": [],
        }

    rc, so, se = run(
        [semgrep, "scan", "--config", "p/javascript", "--json", *targets],
        cwd=snapshot,
        timeout=1800,
    )

    out_json.write_text(so, encoding="utf-8", errors="replace")
    out_json.with_suffix(".stderr.txt").write_text(se, encoding="utf-8", errors="replace")

    try:
        data = json.loads(so)
    except Exception as e:
        return {
            "status": f"JSON_PARSE_FAILED:{e}",
            "count": None,
            "results": [],
        }

    results = []
    for r in data.get("results", []):
        if r.get("check_id") != exact_rule:
            continue

        results.append({
            "message": r.get("extra", {}).get("message", ""),
            "locations": [{
                "path": r.get("path", ""),
                "start": r.get("start", {}).get("line"),
                "end": r.get("end", {}).get("line"),
                "kind": "primary",
            }],
        })

    return {
        "status": "OK",
        "count": len(results),
        "results": results,
        "semgrep_rc": rc,
    }

rows = []
semgrep_bin = None
semgrep_source = None

for slot, cfg in ROOTS.items():
    slot_out = OUT / slot
    slot_out.mkdir(parents=True, exist_ok=True)

    try:
        commits_path = V1 / "roots" / slot / "RESOLVED_COMMITS.json"
        commits = json.loads(commits_path.read_text())

        repo_dir = resolve_repo(slot, cfg, commits)

        rc, diff_text, diff_err = run(
            [
                "git", "diff", "--unified=0", "--no-ext-diff",
                commits["base_sha"], commits["head_sha"], "--"
            ],
            cwd=repo_dir,
            timeout=300,
        )
        if rc != 0:
            raise RuntimeError(f"historical git diff failed: {diff_err[-2000:]}")

        (slot_out / "BASE_TO_HEAD.diff").write_text(diff_text, encoding="utf-8")
        changed = parse_added_lines(diff_text)
        (slot_out / "CHANGED_ADDED_LINES.json").write_text(
            json.dumps({k: sorted(v) for k, v in changed.items()}, indent=2) + "\n",
            encoding="utf-8",
        )

        if cfg["scanner"] == "codeql":
            base_sarif = V1 / "roots" / slot / "scan_base" / "result.sarif"
            head_sarif = V1 / "roots" / slot / "scan_head" / "result.sarif"

            if not base_sarif.exists() or not head_sarif.exists():
                raise RuntimeError("v1 CodeQL SARIF missing")

            base_results = load_sarif_exact(base_sarif, cfg["rule"])
            head_results = load_sarif_exact(head_sarif, cfg["rule"])
            attributed = [r for r in head_results if result_hits_changed(r, changed)]

            (slot_out / "HEAD_EXACT_RULE_RESULTS.json").write_text(
                json.dumps(head_results, indent=2) + "\n",
                encoding="utf-8",
            )
            (slot_out / "HEAD_ATTRIBUTED_RESULTS.json").write_text(
                json.dumps(attributed, indent=2) + "\n",
                encoding="utf-8",
            )

            rows.append({
                "root_slot": slot,
                "root_id": cfg["root_id"],
                "repository": cfg["repo"],
                "scanner": cfg["scanner"],
                "rule": cfg["rule"],
                "base_sha": commits["base_sha"],
                "head_sha": commits["head_sha"],
                "base_rule_count": len(base_results),
                "head_rule_count": len(head_results),
                "head_changed_attributed_count": len(attributed),
                "historical_rule_replayed": "YES" if attributed else "NO",
                "tool_status": "OK",
                "note": "",
            })

        else:
            if semgrep_bin is None:
                semgrep_bin, semgrep_source = find_semgrep()

            if semgrep_bin is None:
                rows.append({
                    "root_slot": slot,
                    "root_id": cfg["root_id"],
                    "repository": cfg["repo"],
                    "scanner": cfg["scanner"],
                    "rule": cfg["rule"],
                    "base_sha": commits["base_sha"],
                    "head_sha": commits["head_sha"],
                    "base_rule_count": "",
                    "head_rule_count": "",
                    "head_changed_attributed_count": "",
                    "historical_rule_replayed": "NO",
                    "tool_status": "SEMGREP_UNAVAILABLE",
                    "note": semgrep_source or "",
                })
                continue

            base_snapshot = OUT / "_snapshots" / slot / "base"
            head_snapshot = OUT / "_snapshots" / slot / "head"
            checkout(repo_dir, commits["base_sha"], base_snapshot)
            checkout(repo_dir, commits["head_sha"], head_snapshot)

            base_scan = semgrep_scan(
                semgrep_bin,
                base_snapshot,
                cfg["target_files"],
                cfg["rule"],
                slot_out / "semgrep_base.json",
            )
            head_scan = semgrep_scan(
                semgrep_bin,
                head_snapshot,
                cfg["target_files"],
                cfg["rule"],
                slot_out / "semgrep_head.json",
            )

            attributed = [
                r for r in head_scan.get("results", [])
                if result_hits_changed(r, changed)
            ]

            (slot_out / "HEAD_ATTRIBUTED_RESULTS.json").write_text(
                json.dumps(attributed, indent=2) + "\n",
                encoding="utf-8",
            )

            rows.append({
                "root_slot": slot,
                "root_id": cfg["root_id"],
                "repository": cfg["repo"],
                "scanner": cfg["scanner"],
                "rule": cfg["rule"],
                "base_sha": commits["base_sha"],
                "head_sha": commits["head_sha"],
                "base_rule_count": base_scan.get("count", ""),
                "head_rule_count": head_scan.get("count", ""),
                "head_changed_attributed_count": len(attributed),
                "historical_rule_replayed": (
                    "YES"
                    if head_scan.get("status") == "OK" and attributed
                    else "NO"
                ),
                "tool_status": f"base={base_scan.get('status')};head={head_scan.get('status')}",
                "note": f"semgrep_source={semgrep_source}",
            })

    except Exception as e:
        rows.append({
            "root_slot": slot,
            "root_id": cfg["root_id"],
            "repository": cfg["repo"],
            "scanner": cfg["scanner"],
            "rule": cfg["rule"],
            "base_sha": "",
            "head_sha": "",
            "base_rule_count": "",
            "head_rule_count": "",
            "head_changed_attributed_count": "",
            "historical_rule_replayed": "NO",
            "tool_status": "ERROR",
            "note": str(e)[:3000],
        })

csv_path = OUT / "HISTORICAL_RULE_REPLAY_FIXED.csv"
with csv_path.open("w", newline="", encoding="utf-8") as f:
    fields = [
        "root_slot",
        "root_id",
        "repository",
        "scanner",
        "rule",
        "base_sha",
        "head_sha",
        "base_rule_count",
        "head_rule_count",
        "head_changed_attributed_count",
        "historical_rule_replayed",
        "tool_status",
        "note",
    ]
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)

summary = {
    "schema": "T1_HISTORICAL_REPLAY_FIX_v2",
    "root_count": len(rows),
    "replayed_yes": sum(r["historical_rule_replayed"] == "YES" for r in rows),
    "replayed_no": sum(r["historical_rule_replayed"] == "NO" for r in rows),
    "semgrep_binary": semgrep_bin,
    "semgrep_source": semgrep_source,
    "bug_fixed": (
        "v1 computed changed lines with plain `git diff` inside a clean detached "
        "HEAD checkout, yielding an empty changed-line map. v2 computes "
        "`git diff BASE_SHA HEAD_SHA` in the source repository."
    ),
}

(OUT / "SUMMARY.json").write_text(
    json.dumps(summary, indent=2) + "\n",
    encoding="utf-8",
)

print(json.dumps(summary, indent=2))
print()
print("=== ROOT RESULTS ===")
for r in rows:
    print(
        r["root_slot"],
        r["scanner"],
        r["rule"],
        f"base={r['base_rule_count']}",
        f"head={r['head_rule_count']}",
        f"attributed={r['head_changed_attributed_count']}",
        f"replay={r['historical_rule_replayed']}",
        f"tool={r['tool_status']}",
    )
    if r["note"]:
        print("  note:", r["note"][:1000])

print()
print("STATUS=DONE")
PY

cd "$ROOT"

rm -f "$ARCHIVE"
tar \
  --exclude='T1_HISTORICAL_REPLAY_FIX_v2/_repos' \
  --exclude='T1_HISTORICAL_REPLAY_FIX_v2/_snapshots' \
  -czf "$ARCHIVE" \
  T1_HISTORICAL_REPLAY_FIX_v2

echo
echo "=== ARCHIVE ==="
ls -lh "$ARCHIVE"
sha256sum "$ARCHIVE"
echo "STATUS=ARCHIVED"
