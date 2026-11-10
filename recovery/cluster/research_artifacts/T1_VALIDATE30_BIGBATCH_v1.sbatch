#!/bin/bash
#SBATCH --job-name=t1v30
#SBATCH --partition=bigbatch
#SBATCH --time=06:00:00
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T1_VALIDATE30_BIGBATCH_v1.out

ROOT="$HOME/research_artifacts"
INZIP="$ROOT/T1_VALIDATE30_INPUT_v1.zip"
OUT="$ROOT/T1_VALIDATE30_BIGBATCH_v1"
ARCHIVE="$ROOT/T1_VALIDATE30_BIGBATCH_v1_RESULTS.tar.gz"

rm -rf "$OUT"
mkdir -p "$OUT"

python3 - "$INZIP" "$OUT" <<'PY'
from __future__ import annotations

from pathlib import Path
import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

INZIP = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
WORK = OUT / "_work"
WORK.mkdir(parents=True, exist_ok=True)

def sh(args, cwd=None, timeout=None):
    p = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return p.returncode, p.stdout, p.stderr

def write_log(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", errors="replace")

def which_candidates(name, extras=()):
    cands = []
    rc, out, _ = sh(["bash", "-lc", f"command -v {name} || true"])
    if out.strip():
        cands.append(out.strip().splitlines()[0])
    cands.extend(extras)
    for c in cands:
        if c and Path(c).exists() and os.access(c, os.X_OK):
            return c
    return None

CODEQL = which_candidates(
    "codeql",
    [
        str(Path.home() / "codeql" / "codeql"),
        str(Path.home() / ".local" / "bin" / "codeql"),
        str(Path.home() / "bin" / "codeql"),
    ],
)
SEMGREP = which_candidates(
    "semgrep",
    [
        str(Path.home() / ".local" / "bin" / "semgrep"),
    ],
)
NODE = which_candidates("node")

env_report = {
    "python": sys.version,
    "codeql": CODEQL,
    "semgrep": SEMGREP,
    "node": NODE,
}
for tool_name, tool_path in [("codeql", CODEQL), ("semgrep", SEMGREP), ("node", NODE)]:
    if tool_path:
        rc, out, err = sh([tool_path, "--version"])
        env_report[f"{tool_name}_version_rc"] = rc
        env_report[f"{tool_name}_version"] = (out + err).strip()[:4000]

(OUT / "ENVIRONMENT.json").write_text(
    json.dumps(env_report, indent=2) + "\n",
    encoding="utf-8",
)

with zipfile.ZipFile(INZIP, "r") as z:
    z.extractall(WORK / "input")

manifest = json.loads((WORK / "input" / "MANIFEST.json").read_text())
roots = manifest["roots"]
run_ids = manifest["run_ids"]

def git_fetch_pr(repo_dir: Path, repo: str, pr: int):
    url = f"https://github.com/{repo}.git"
    repo_dir.mkdir(parents=True, exist_ok=True)
    sh(["git", "init", "-q"], cwd=repo_dir)
    sh(["git", "remote", "add", "origin", url], cwd=repo_dir)

    # Fetch head and merge refs if GitHub exposes them.
    rc_h, out_h, err_h = sh(
        ["git", "fetch", "-q", "--no-tags", "origin",
         f"+refs/pull/{pr}/head:refs/remotes/origin/pr-head"],
        cwd=repo_dir, timeout=900,
    )
    rc_m, out_m, err_m = sh(
        ["git", "fetch", "-q", "--no-tags", "origin",
         f"+refs/pull/{pr}/merge:refs/remotes/origin/pr-merge"],
        cwd=repo_dir, timeout=900,
    )

    if rc_h != 0:
        raise RuntimeError(f"PR head fetch failed: {err_h[-4000:]}")

    rc, head, err = sh(["git", "rev-parse", "refs/remotes/origin/pr-head"], cwd=repo_dir)
    if rc != 0:
        raise RuntimeError(f"Cannot resolve PR head: {err}")
    head = head.strip()

    base = None
    source = None
    merge_sha = None

    if rc_m == 0:
        rc, merge_sha, _ = sh(["git", "rev-parse", "refs/remotes/origin/pr-merge"], cwd=repo_dir)
        merge_sha = merge_sha.strip() if rc == 0 else None
        if merge_sha:
            rc, parents, _ = sh(["git", "show", "-s", "--format=%P", merge_sha], cwd=repo_dir)
            plist = parents.strip().split()
            if len(plist) >= 2:
                p1 = plist[0]
                p2 = plist[1]
                # Ensure both parent objects are local.
                sh(["git", "fetch", "-q", "--no-tags", "origin", p1, p2], cwd=repo_dir, timeout=900)
                # Prefer the actual PR head when one merge parent matches it.
                candidate_head = head
                if p2 != head and p1 == head:
                    p1, p2 = p2, p1
                rc, mb, err = sh(["git", "merge-base", p1, candidate_head], cwd=repo_dir)
                if rc == 0 and mb.strip():
                    base = mb.strip()
                    source = "github_pr_merge_ref_merge_base"

    if base is None:
        # Fallback: GitHub API merge_commit_sha, then first parent versus PR head.
        api = f"https://api.github.com/repos/{repo}/pulls/{pr}"
        req = urllib.request.Request(api, headers={"User-Agent": "t1-validate30-v1"})
        with urllib.request.urlopen(req, timeout=60) as r:
            prj = json.load(r)
        merge_commit_sha = prj.get("merge_commit_sha")
        if merge_commit_sha:
            sh(["git", "fetch", "-q", "--no-tags", "origin", merge_commit_sha], cwd=repo_dir, timeout=900)
            rc, parents, _ = sh(["git", "show", "-s", "--format=%P", merge_commit_sha], cwd=repo_dir)
            plist = parents.strip().split()
            if plist:
                p1 = plist[0]
                sh(["git", "fetch", "-q", "--no-tags", "origin", p1], cwd=repo_dir, timeout=900)
                rc, mb, err = sh(["git", "merge-base", p1, head], cwd=repo_dir)
                if rc == 0 and mb.strip():
                    base = mb.strip()
                    source = "github_api_merge_commit_merge_base"
                    merge_sha = merge_commit_sha

    if base is None:
        raise RuntimeError("Could not resolve historical merge-base")

    return {
        "repo": repo,
        "pr": pr,
        "base_sha": base,
        "head_sha": head,
        "merge_sha": merge_sha,
        "resolution_source": source,
    }

def checkout_snapshot(source_repo: Path, sha: str, dst: Path):
    if dst.exists():
        shutil.rmtree(dst)
    rc, out, err = sh(["git", "clone", "-q", "--shared", str(source_repo), str(dst)])
    if rc != 0:
        raise RuntimeError(err)
    rc, out, err = sh(["git", "checkout", "-q", "--detach", sha], cwd=dst)
    if rc != 0:
        raise RuntimeError(err)

def find_codeql_query(rule: str):
    roots = [
        Path.home() / ".codeql" / "packages" / "codeql" / "javascript-queries",
        Path.home() / ".codeql" / "packages",
    ]
    needle = f"@id {rule}"
    candidates = []
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*.ql"):
            try:
                txt = p.read_text(errors="ignore")
            except Exception:
                continue
            if needle in txt:
                candidates.append(p)
    if not candidates:
        return None
    candidates.sort(key=lambda p: str(p))
    return str(candidates[-1])

CODEQL_QUERY_CACHE = {}

def codeql_scan(repo_dir: Path, rule: str, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    if not CODEQL:
        return {"status": "TOOL_UNAVAILABLE"}

    q = CODEQL_QUERY_CACHE.get(rule)
    if q is None:
        q = find_codeql_query(rule)
        CODEQL_QUERY_CACHE[rule] = q
    if not q:
        return {"status": "QUERY_NOT_FOUND", "rule": rule}

    db = out_dir / "db"
    sarif = out_dir / "result.sarif"

    rc, so, se = sh(
        [
            CODEQL, "database", "create", str(db),
            "--language=javascript-typescript",
            f"--source-root={repo_dir}",
            "--overwrite",
            "--threads=8",
        ],
        cwd=repo_dir,
        timeout=3600,
    )
    write_log(out_dir / "database_create.stdout.txt", so)
    write_log(out_dir / "database_create.stderr.txt", se)
    if rc != 0:
        return {"status": "DB_CREATE_FAILED", "rc": rc, "query": q}

    rc, so, se = sh(
        [
            CODEQL, "database", "analyze", str(db), q,
            "--format=sarifv2.1.0",
            f"--output={sarif}",
            "--threads=8",
        ],
        cwd=repo_dir,
        timeout=3600,
    )
    write_log(out_dir / "database_analyze.stdout.txt", so)
    write_log(out_dir / "database_analyze.stderr.txt", se)
    if rc != 0:
        return {"status": "ANALYZE_FAILED", "rc": rc, "query": q}

    try:
        data = json.loads(sarif.read_text(errors="replace"))
    except Exception as e:
        return {"status": "SARIF_PARSE_FAILED", "error": str(e), "query": q}

    results = []
    for run in data.get("runs", []):
        for r in run.get("results", []):
            rid = r.get("ruleId", "")
            # A single exact query normally emits the desired rule. Keep only exact ID.
            if rid != rule:
                continue
            locs = []
            for loc in r.get("locations", []):
                pl = loc.get("physicalLocation", {})
                art = pl.get("artifactLocation", {}).get("uri", "")
                reg = pl.get("region", {})
                locs.append({
                    "path": art,
                    "startLine": reg.get("startLine"),
                    "endLine": reg.get("endLine", reg.get("startLine")),
                    "kind": "primary",
                })
            for cf in r.get("codeFlows", []):
                for tf in cf.get("threadFlows", []):
                    for tfl in tf.get("locations", []):
                        loc = tfl.get("location", {})
                        pl = loc.get("physicalLocation", {})
                        art = pl.get("artifactLocation", {}).get("uri", "")
                        reg = pl.get("region", {})
                        locs.append({
                            "path": art,
                            "startLine": reg.get("startLine"),
                            "endLine": reg.get("endLine", reg.get("startLine")),
                            "kind": "codeflow",
                        })
            results.append({
                "ruleId": rid,
                "message": r.get("message", {}).get("text", ""),
                "locations": locs,
            })

    return {
        "status": "OK",
        "query": q,
        "count": len(results),
        "results": results,
        "sarif": str(sarif.relative_to(OUT)),
    }

def semgrep_scan(repo_dir: Path, rule: str, target_files, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    if not SEMGREP:
        return {"status": "TOOL_UNAVAILABLE"}

    targets = [str(repo_dir / p) for p in target_files if (repo_dir / p).exists()]
    if not targets:
        targets = [str(repo_dir)]

    jsout = out_dir / "result.json"
    # Use the same public JavaScript ruleset family; filter to the frozen exact rule ID.
    rc, so, se = sh(
        [SEMGREP, "scan", "--config", "p/javascript", "--json", *targets],
        cwd=repo_dir,
        timeout=1800,
    )
    write_log(out_dir / "semgrep.stdout.txt", so)
    write_log(out_dir / "semgrep.stderr.txt", se)

    # Semgrep can return nonzero when findings exist depending on flags/version.
    try:
        data = json.loads(so)
        jsout.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except Exception as e:
        return {"status": "JSON_PARSE_FAILED", "rc": rc, "error": str(e)}

    results = []
    for r in data.get("results", []):
        if r.get("check_id") != rule:
            continue
        results.append({
            "ruleId": r.get("check_id"),
            "message": r.get("extra", {}).get("message", ""),
            "locations": [{
                "path": r.get("path", ""),
                "startLine": r.get("start", {}).get("line"),
                "endLine": r.get("end", {}).get("line"),
                "kind": "primary",
            }],
        })
    return {
        "status": "OK",
        "count": len(results),
        "results": results,
        "json": str(jsout.relative_to(OUT)),
    }

def scan(repo_dir: Path, cfg, out_dir: Path):
    if cfg["scanner"] == "codeql":
        return codeql_scan(repo_dir, cfg["rule"], out_dir)
    if cfg["scanner"] == "semgrep":
        return semgrep_scan(repo_dir, cfg["rule"], cfg["target_files"], out_dir)
    return {"status": "UNKNOWN_SCANNER"}

def parse_changed_added_lines(repo_dir: Path):
    rc, out, err = sh(["git", "diff", "--unified=0", "--no-ext-diff"], cwd=repo_dir)
    changed = {}
    cur = None
    new_line = None
    for line in out.splitlines():
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
    return changed, out

def path_norm(p):
    p = (p or "").replace("\\\\", "/")
    if p.startswith("file://"):
        p = p[7:]
    return p.lstrip("./")

def result_attributed(result, changed):
    for loc in result.get("locations", []):
        p = path_norm(loc.get("path"))
        # SARIF may use absolute or encoded paths. Suffix-match repository paths.
        matching = None
        for cp in changed:
            if p == cp or p.endswith("/" + cp):
                matching = cp
                break
        if not matching:
            continue
        a = loc.get("startLine")
        b = loc.get("endLine") or a
        if a is None:
            continue
        if any(line in changed[matching] for line in range(int(a), int(b) + 1)):
            return True
    return False

def summarize_scan(scan_result, changed=None):
    if scan_result.get("status") != "OK":
        return {
            "scan_status": scan_result.get("status"),
            "rule_count": None,
            "attributed_count": None,
        }
    rs = scan_result.get("results", [])
    attributed = None
    if changed is not None:
        attributed = sum(1 for r in rs if result_attributed(r, changed))
    return {
        "scan_status": "OK",
        "rule_count": len(rs),
        "attributed_count": attributed,
    }

def patch_file_for_run(run_id):
    d = WORK / "input" / "runs" / run_id
    files = list(d.glob("*_submission.patch"))
    return files[0] if files else None

def normalize_patch_strict(text: str, repo_dir: Path):
    """
    Only repairs syntactic unified-diff damage.
    - Recounts existing hunk line counts.
    - For bare @@ headers, infer a start only when the complete old hunk sequence
      matches exactly and uniquely in the exact base file.
    No fuzzy/semantic transplant.
    """
    lines = text.splitlines()
    out = []
    i = 0
    current_file = None
    failures = []

    while i < len(lines):
        line = lines[i]
        if line.startswith("+++ b/"):
            current_file = line[6:]
            out.append(line)
            i += 1
            continue

        if line.startswith("@@"):
            j = i + 1
            h = []
            while j < len(lines):
                if lines[j].startswith("@@") or lines[j].startswith("diff --git "):
                    break
                # A new file header may begin without diff --git in some proposals.
                if lines[j].startswith("--- a/") and h:
                    break
                h.append(lines[j])
                j += 1

            old = []
            new = []
            clean_h = []
            for x in h:
                if x.startswith("\\ No newline"):
                    clean_h.append(x)
                    continue
                if x.startswith("+"):
                    new.append(x[1:])
                    clean_h.append(x)
                elif x.startswith("-"):
                    old.append(x[1:])
                    clean_h.append(x)
                elif x.startswith(" "):
                    old.append(x[1:])
                    new.append(x[1:])
                    clean_h.append(x)
                else:
                    # Unprefixed content is not silently reinterpreted.
                    failures.append(f"unprefixed_hunk_line:{current_file}:{x[:120]}")
                    clean_h.append(x)

            m = re.match(
                r"@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@(.*)",
                line,
            )
            if m:
                old_start = int(m.group(1))
                new_start = int(m.group(3))
                suffix = m.group(5)
            else:
                if not current_file:
                    failures.append("bare_hunk_without_file")
                    old_start = new_start = 1
                    suffix = ""
                else:
                    fp = repo_dir / current_file
                    if not fp.exists():
                        failures.append(f"bare_hunk_missing_file:{current_file}")
                        old_start = new_start = 1
                        suffix = ""
                    else:
                        base_lines = fp.read_text(errors="replace").splitlines()
                        if not old:
                            failures.append(f"bare_hunk_insert_only_no_anchor:{current_file}")
                            old_start = new_start = 1
                            suffix = ""
                        else:
                            hits = []
                            n = len(old)
                            for k in range(0, len(base_lines) - n + 1):
                                if base_lines[k:k+n] == old:
                                    hits.append(k + 1)
                            if len(hits) != 1:
                                failures.append(
                                    f"bare_hunk_old_sequence_hits={len(hits)}:{current_file}"
                                )
                                old_start = new_start = 1
                                suffix = ""
                            else:
                                old_start = new_start = hits[0]
                                suffix = ""

            out.append(
                f"@@ -{old_start},{len(old)} +{new_start},{len(new)} @@{suffix}"
            )
            out.extend(clean_h)
            i = j
            continue

        out.append(line)
        i += 1

    return "\n".join(out) + "\n", failures

def try_apply_generated(base_repo: Path, run_id: str, run_dir: Path):
    patch = patch_file_for_run(run_id)
    if not patch:
        return {"status": "NO_PATCH"}

    raw = patch.read_text(errors="replace")
    raw_copy = run_dir / "generated_raw.patch"
    raw_copy.write_text(raw, encoding="utf-8")

    # Attempt 1: exact raw patch, recount allowed.
    rc, so, se = sh(
        ["git", "apply", "--check", "--recount", "--whitespace=nowarn", str(raw_copy)],
        cwd=base_repo,
    )
    write_log(run_dir / "raw_apply_check.txt", so + "\n" + se)
    if rc == 0:
        rc2, so2, se2 = sh(
            ["git", "apply", "--recount", "--whitespace=nowarn", str(raw_copy)],
            cwd=base_repo,
        )
        write_log(run_dir / "raw_apply.txt", so2 + "\n" + se2)
        if rc2 == 0:
            return {"status": "APPLIED_RAW_EXACT", "patch": str(raw_copy.relative_to(OUT))}

    # Attempt 2: repair only hunk syntax/counts, never fuzzy content.
    normalized, norm_failures = normalize_patch_strict(raw, base_repo)
    norm = run_dir / "generated_syntax_normalized.patch"
    norm.write_text(normalized, encoding="utf-8")
    (run_dir / "normalization_notes.json").write_text(
        json.dumps(norm_failures, indent=2) + "\n", encoding="utf-8"
    )

    if norm_failures:
        return {
            "status": "NOT_MATERIALIZABLE_STRICT",
            "reason": ";".join(norm_failures[:20]),
            "patch": str(norm.relative_to(OUT)),
        }

    rc, so, se = sh(
        ["git", "apply", "--check", "--recount", "--whitespace=nowarn", str(norm)],
        cwd=base_repo,
    )
    write_log(run_dir / "normalized_apply_check.txt", so + "\n" + se)
    if rc != 0:
        return {
            "status": "NOT_MATERIALIZABLE_STRICT",
            "reason": (so + "\n" + se)[-4000:],
            "patch": str(norm.relative_to(OUT)),
        }

    rc2, so2, se2 = sh(
        ["git", "apply", "--recount", "--whitespace=nowarn", str(norm)],
        cwd=base_repo,
    )
    write_log(run_dir / "normalized_apply.txt", so2 + "\n" + se2)
    if rc2 != 0:
        return {
            "status": "APPLY_FAILED_AFTER_CHECK",
            "reason": (so2 + "\n" + se2)[-4000:],
        }

    return {"status": "APPLIED_SYNTAX_NORMALIZED_EXACT", "patch": str(norm.relative_to(OUT))}

# Resolve the six historical repositories and run historical scanner replay.
resolved = {}
historical_rows = []

for slot, cfg in roots.items():
    slot_dir = OUT / "roots" / slot
    slot_dir.mkdir(parents=True, exist_ok=True)
    source_repo = WORK / "repos" / slot

    try:
        r = git_fetch_pr(source_repo, cfg["repo"], int(cfg["pr"]))
        resolved[slot] = r
        (slot_dir / "RESOLVED_COMMITS.json").write_text(
            json.dumps(r, indent=2) + "\n", encoding="utf-8"
        )
    except Exception as e:
        resolved[slot] = {"error": str(e)}
        historical_rows.append({
            "root_slot": slot,
            "root_id": cfg["root_id"],
            "repository": cfg["repo"],
            "pr": cfg["pr"],
            "scanner": cfg["scanner"],
            "rule": cfg["rule"],
            "base_sha": "",
            "head_sha": "",
            "resolution_source": "",
            "base_scan_status": "BASE_RESOLUTION_FAILED",
            "base_rule_count": "",
            "head_scan_status": "BASE_RESOLUTION_FAILED",
            "head_rule_count": "",
            "historical_changed_attributed_count": "",
            "historical_exact_rule_replayed": "NO",
            "note": str(e)[:2000],
        })
        continue

    base_dir = WORK / "snapshots" / slot / "base"
    head_dir = WORK / "snapshots" / slot / "head"

    try:
        checkout_snapshot(source_repo, r["base_sha"], base_dir)
        checkout_snapshot(source_repo, r["head_sha"], head_dir)

        base_scan = scan(base_dir, cfg, slot_dir / "scan_base")
        head_scan = scan(head_dir, cfg, slot_dir / "scan_head")
        changed, hdiff = parse_changed_added_lines(head_dir)
        write_log(slot_dir / "historical_base_to_head.diff", hdiff)
        head_sum = summarize_scan(head_scan, changed)
        base_sum = summarize_scan(base_scan)

        historical_rows.append({
            "root_slot": slot,
            "root_id": cfg["root_id"],
            "repository": cfg["repo"],
            "pr": cfg["pr"],
            "scanner": cfg["scanner"],
            "rule": cfg["rule"],
            "base_sha": r["base_sha"],
            "head_sha": r["head_sha"],
            "resolution_source": r["resolution_source"],
            "base_scan_status": base_sum["scan_status"],
            "base_rule_count": base_sum["rule_count"],
            "head_scan_status": head_sum["scan_status"],
            "head_rule_count": head_sum["rule_count"],
            "historical_changed_attributed_count": head_sum["attributed_count"],
            "historical_exact_rule_replayed":
                "YES"
                if head_sum["scan_status"] == "OK"
                and (head_sum["attributed_count"] or 0) > 0
                else "NO",
            "note": "",
        })
    except Exception as e:
        historical_rows.append({
            "root_slot": slot,
            "root_id": cfg["root_id"],
            "repository": cfg["repo"],
            "pr": cfg["pr"],
            "scanner": cfg["scanner"],
            "rule": cfg["rule"],
            "base_sha": r.get("base_sha", ""),
            "head_sha": r.get("head_sha", ""),
            "resolution_source": r.get("resolution_source", ""),
            "base_scan_status": "ERROR",
            "base_rule_count": "",
            "head_scan_status": "ERROR",
            "head_rule_count": "",
            "historical_changed_attributed_count": "",
            "historical_exact_rule_replayed": "NO",
            "note": str(e)[:2000],
        })

hist_csv = OUT / "HISTORICAL_RULE_REPLAY.csv"
with hist_csv.open("w", newline="", encoding="utf-8") as f:
    fields = list(historical_rows[0].keys()) if historical_rows else []
    w = csv.DictWriter(f, fieldnames=fields)
    if fields:
        w.writeheader()
        w.writerows(historical_rows)

# Evaluate all 30 generated proposals strictly, without manual repair.
run_rows = []

for run_id in run_ids:
    slot = run_id.split("_")[-1]
    cfg = roots[slot]
    rd = OUT / "runs" / run_id
    rd.mkdir(parents=True, exist_ok=True)

    r = resolved.get(slot, {})
    if "error" in r or not r.get("base_sha"):
        run_rows.append({
            "run_id": run_id,
            "root_slot": slot,
            "root_id": cfg["root_id"],
            "repository": cfg["repo"],
            "scanner": cfg["scanner"],
            "rule": cfg["rule"],
            "base_sha": "",
            "materialization_status": "BASE_RESOLUTION_FAILED",
            "git_diff_check": "",
            "syntax_check": "",
            "scan_status": "NOT_RUN",
            "rule_count": "",
            "changed_attributed_count": "",
            "target_rule_introduced": "",
            "note": r.get("error", ""),
        })
        continue

    source_repo = WORK / "repos" / slot
    repo_dir = WORK / "generated" / run_id
    try:
        checkout_snapshot(source_repo, r["base_sha"], repo_dir)
        mat = try_apply_generated(repo_dir, run_id, rd)

        if not str(mat.get("status", "")).startswith("APPLIED_"):
            run_rows.append({
                "run_id": run_id,
                "root_slot": slot,
                "root_id": cfg["root_id"],
                "repository": cfg["repo"],
                "scanner": cfg["scanner"],
                "rule": cfg["rule"],
                "base_sha": r["base_sha"],
                "materialization_status": mat.get("status"),
                "git_diff_check": "",
                "syntax_check": "",
                "scan_status": "NOT_RUN",
                "rule_count": "",
                "changed_attributed_count": "",
                "target_rule_introduced": "",
                "note": str(mat.get("reason", ""))[:3000],
            })
            continue

        # Patch cleanliness.
        rc, so, se = sh(["git", "diff", "--check"], cwd=repo_dir)
        diff_check = "PASS" if rc == 0 else "FAIL"
        write_log(rd / "git_diff_check.txt", so + "\n" + se)

        changed, generated_diff = parse_changed_added_lines(repo_dir)
        write_log(rd / "materialized.diff", generated_diff)

        # Lightweight JS/CJS syntax only; TS syntax is covered indirectly by CodeQL extraction.
        syntax_statuses = []
        if NODE:
            for fp in sorted(changed):
                if fp.endswith((".js", ".cjs", ".mjs")) and (repo_dir / fp).exists():
                    rc, so, se = sh([NODE, "--check", str(repo_dir / fp)], cwd=repo_dir)
                    syntax_statuses.append(f"{fp}:{'PASS' if rc == 0 else 'FAIL'}")
                    write_log(rd / ("node_check_" + re.sub(r"[^A-Za-z0-9_.-]+", "_", fp) + ".txt"), so + "\n" + se)
        syntax_check = ";".join(syntax_statuses) if syntax_statuses else "NOT_APPLICABLE_OR_NOT_RUN"

        s = scan(repo_dir, cfg, rd / "scan_generated")
        sm = summarize_scan(s, changed)

        target_intro = ""
        if sm["scan_status"] == "OK":
            target_intro = "YES" if (sm["attributed_count"] or 0) > 0 else "NO"

        run_rows.append({
            "run_id": run_id,
            "root_slot": slot,
            "root_id": cfg["root_id"],
            "repository": cfg["repo"],
            "scanner": cfg["scanner"],
            "rule": cfg["rule"],
            "base_sha": r["base_sha"],
            "materialization_status": mat.get("status"),
            "git_diff_check": diff_check,
            "syntax_check": syntax_check,
            "scan_status": sm["scan_status"],
            "rule_count": sm["rule_count"],
            "changed_attributed_count": sm["attributed_count"],
            "target_rule_introduced": target_intro,
            "note": "",
        })

    except Exception as e:
        run_rows.append({
            "run_id": run_id,
            "root_slot": slot,
            "root_id": cfg["root_id"],
            "repository": cfg["repo"],
            "scanner": cfg["scanner"],
            "rule": cfg["rule"],
            "base_sha": r.get("base_sha", ""),
            "materialization_status": "ERROR",
            "git_diff_check": "",
            "syntax_check": "",
            "scan_status": "NOT_RUN",
            "rule_count": "",
            "changed_attributed_count": "",
            "target_rule_introduced": "",
            "note": str(e)[:3000],
        })

run_csv = OUT / "GENERATED30_SCANNER_VALIDATION.csv"
with run_csv.open("w", newline="", encoding="utf-8") as f:
    fields = list(run_rows[0].keys())
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(run_rows)

summary = {
    "schema": "T1_VALIDATE30_BIGBATCH_v1",
    "runs_total": len(run_rows),
    "materialized": sum(str(r["materialization_status"]).startswith("APPLIED_") for r in run_rows),
    "not_materialized": sum(not str(r["materialization_status"]).startswith("APPLIED_") for r in run_rows),
    "scanned_ok": sum(r["scan_status"] == "OK" for r in run_rows),
    "target_rule_introduced_yes": sum(r["target_rule_introduced"] == "YES" for r in run_rows),
    "target_rule_introduced_no": sum(r["target_rule_introduced"] == "NO" for r in run_rows),
    "historical_roots_replayed": sum(r.get("historical_exact_rule_replayed") == "YES" for r in historical_rows),
    "important_interpretation": (
        "NOT_MATERIALIZABLE_STRICT and scanner failures are evaluation failures, "
        "not scanner-negative outcomes."
    ),
}
(OUT / "SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

# Integrity checksums excluding transient _work.
checks = []
for p in sorted(OUT.rglob("*")):
    if not p.is_file() or "_work" in p.parts or p.name == "SHA256SUMS.txt":
        continue
    rel = p.relative_to(OUT)
    checks.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {rel}")
(OUT / "SHA256SUMS.txt").write_text("\n".join(checks) + "\n", encoding="utf-8")

print(json.dumps(summary, indent=2))
print("STATUS=DONE")
PY

cd "$ROOT"
rm -f "$ARCHIVE"

tar \
  --exclude='T1_VALIDATE30_BIGBATCH_v1/_work' \
  -czf "$ARCHIVE" \
  T1_VALIDATE30_BIGBATCH_v1

echo
echo "=== RESULT ARCHIVE ==="
ls -lh "$ARCHIVE"
sha256sum "$ARCHIVE"
echo
echo "STATUS=ARCHIVED"
