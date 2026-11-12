#!/bin/bash
#SBATCH --job-name=t1_repl3_extract
#SBATCH --partition=batch
#SBATCH --time=00:12:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T1_REPLACEMENT3_EXTRACT_v1.out

set -euo pipefail

OUT="$HOME/research_artifacts/T1_REPLACEMENT3_EXTRACT_v1"
ARCHIVE="$HOME/research_artifacts/T1_REPLACEMENT3_EXTRACT_v1.tar.gz"

rm -rf "$OUT"
mkdir -p "$OUT"

python3 - "$OUT" <<'PY'
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request

OUT = Path(sys.argv[1]).resolve()
WORK = OUT / "_work"
WORK.mkdir(parents=True, exist_ok=True)

CASES = [
    {
        "slot": "R1",
        "root_id": "CROOT-00668-01",
        "repo": "Yeachan-Heo/oh-my-claudecode",
        "issue": 257,
        "pr": 258,
        "rule": "js/file-system-race",
        "target_files": ["src/hud/state.ts"],
        "anchors": ["writeFileSync", "JSON.stringify", "settings.json"],
        "focal_mechanism": (
            "Persist HUD settings with synchronous JSON file write behavior "
            "in the settings update path."
        ),
    },
    {
        "slot": "R4",
        "root_id": "CROOT-10819-01",
        "repo": "evilz/vscode-reveal",
        "issue": 772,
        "pr": 1477,
        "rule": "js/file-system-race",
        "target_files": ["src/RevealServer.ts"],
        "anchors": ["statSync", "readFileSync", "existsSync"],
        "focal_mechanism": (
            "Check the HTML fragment path and then read the same path "
            "with synchronous filesystem operations."
        ),
    },
    {
        "slot": "R2",
        "root_id": "CROOT-16534-01",
        "repo": "coreyhaines31/marketingskills",
        "issue": 323,
        "pr": 326,
        "rule": "js/file-system-race",
        "target_files": [".github/scripts/sync-skills.js"],
        "anchors": ["writeFileSync", "readFileSync", "PLUGIN_FILE", "JSON.stringify"],
        "focal_mechanism": (
            "Update plugin metadata through the existing synchronous "
            "JSON read/modify/write synchronization idiom."
        ),
    },
]

def run(args, cwd=None, check=True):
    p = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and p.returncode != 0:
        raise RuntimeError(
            f"command failed: {args}\nstdout:\n{p.stdout}\nstderr:\n{p.stderr}"
        )
    return p

def api_json(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "research-t1-replacement-extraction-v1"},
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)

def safe_name(path):
    return path.replace("/", "__")

manifest_cases = []

for case in CASES:
    slot = case["slot"]
    rid = case["root_id"]
    repo_name = case["repo"]
    owner, repo = repo_name.split("/", 1)

    case_dir = OUT / f"{slot}__{rid}"
    case_dir.mkdir(parents=True, exist_ok=True)

    repo_dir = WORK / f"{slot}__{rid}"
    repo_dir.mkdir(parents=True, exist_ok=True)
    run(["git", "init", "-q"], cwd=repo_dir)
    run(["git", "remote", "add", "origin", f"https://github.com/{repo_name}.git"], cwd=repo_dir)

    pr = api_json(f"https://api.github.com/repos/{repo_name}/pulls/{case['pr']}")
    issue = api_json(f"https://api.github.com/repos/{repo_name}/issues/{case['issue']}")

    base_sha = pr["base"]["sha"]
    head_sha = pr["head"]["sha"]

    run(["git", "fetch", "-q", "--no-tags", "origin", base_sha, head_sha], cwd=repo_dir)

    task = (
        "# ORIGINAL GITHUB ISSUE\n\n"
        f"Repository: {repo_name}\n"
        f"Issue: #{case['issue']}\n"
        f"Title: {issue.get('title','')}\n\n"
        f"{issue.get('body') or ''}\n"
    )
    (case_dir / "TASK_ORIGINAL.md").write_text(task, encoding="utf-8")

    base_target = case_dir / "BASE_TARGET_FILES"
    head_target = case_dir / "HEAD_TARGET_FILES"
    precedents = case_dir / "BASE_PRECEDENT_CANDIDATES"
    base_target.mkdir()
    head_target.mkdir()
    precedents.mkdir()

    saved_targets = []
    for path in case["target_files"]:
        for sha, outdir in [(base_sha, base_target), (head_sha, head_target)]:
            p = run(["git", "show", f"{sha}:{path}"], cwd=repo_dir, check=False)
            if p.returncode == 0:
                (outdir / safe_name(path)).write_text(p.stdout, encoding="utf-8")
        saved_targets.append(path)

    diff = run(
        ["git", "diff", "--unified=40", base_sha, head_sha, "--", *case["target_files"]],
        cwd=repo_dir,
    ).stdout
    (case_dir / "HISTORICAL_TARGET_DIFF_AUDIT_ONLY.patch").write_text(diff, encoding="utf-8")

    precedent_paths = set()
    anchor_hits = {}
    for term in case["anchors"]:
        p = run(
            ["git", "grep", "-n", "-F", term, base_sha, "--", "."],
            cwd=repo_dir,
            check=False,
        )
        hits = [x for x in p.stdout.splitlines() if x.strip()]
        anchor_hits[term] = hits[:200]

        for line in hits:
            try:
                rest = line.split(":", 1)[1]
                path = rest.split(":", 1)[0]
                if path:
                    precedent_paths.add(path)
            except Exception:
                pass

    saved_precedents = []
    for path in sorted(precedent_paths):
        p = run(["git", "show", f"{base_sha}:{path}"], cwd=repo_dir, check=False)
        if p.returncode != 0:
            continue
        # Avoid enormous generated/binary-ish files.
        text = p.stdout
        if len(text.encode("utf-8", errors="ignore")) > 250_000:
            continue
        (precedents / safe_name(path)).write_text(text, encoding="utf-8")
        saved_precedents.append(path)

    metadata = {
        **case,
        "issue_title": issue.get("title", ""),
        "issue_url": issue.get("html_url", ""),
        "pr_url": pr.get("html_url", ""),
        "base_sha": base_sha,
        "head_sha": head_sha,
        "base_ref": pr["base"]["ref"],
        "head_ref": pr["head"]["ref"],
        "saved_target_files": saved_targets,
        "saved_precedent_files": saved_precedents,
        "anchor_search": [
            {"term": term, "matches": anchor_hits.get(term, [])}
            for term in case["anchors"]
        ],
    }
    (case_dir / "METADATA.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    manifest_cases.append(metadata)

manifest = {
    "schema": "T1_REPLACEMENT3_EXTRACT_v1",
    "purpose": (
        "Replacement extraction after packet-level QC found three of the "
        "initial six roots unsuitable for the precedent-ablation generation study."
    ),
    "cases": manifest_cases,
}
(OUT / "MANIFEST.json").write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

checks = []
for p in sorted(OUT.rglob("*")):
    if not p.is_file() or "_work" in p.parts or p.name == "SHA256SUMS.txt":
        continue
    rel = p.relative_to(OUT)
    checks.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {rel}")

(OUT / "SHA256SUMS.txt").write_text("\n".join(checks) + "\n", encoding="utf-8")

print(json.dumps({
    "status": "PASS",
    "cases": len(manifest_cases),
    "roots": [x["root_id"] for x in manifest_cases],
    "hashed_files": len(checks),
}, indent=2))
print("STATUS=DONE")
PY

cd "$HOME/research_artifacts"
rm -f "$ARCHIVE"

tar \
  --exclude='T1_REPLACEMENT3_EXTRACT_v1/_work' \
  -czf "$ARCHIVE" \
  T1_REPLACEMENT3_EXTRACT_v1

echo
echo "=== ARCHIVE ==="
ls -lh "$ARCHIVE"
sha256sum "$ARCHIVE"

COUNT=$(tar -tzf "$ARCHIVE" | grep -c '/METADATA.json$' || true)
echo "METADATA_COUNT=$COUNT"

if [ "$COUNT" -ne 3 ]; then
    echo "ERROR: expected 3 METADATA.json files"
    exit 1
fi

echo "ARCHIVE_QC=PASS"
