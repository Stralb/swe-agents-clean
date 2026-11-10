#!/bin/bash
#SBATCH --partition=batch
#SBATCH --job-name=t1_sel6_extract
#SBATCH --time=00:25:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T1_SELECTED6_EXTRACT_v1.out

set -euo pipefail

OUT="$HOME/research_artifacts/T1_SELECTED6_EXTRACT_v1"
ARCHIVE="$HOME/research_artifacts/T1_SELECTED6_EXTRACT_v1.tar.gz"

rm -rf "$OUT"
rm -f "$ARCHIVE"
mkdir -p "$OUT"

python3 - "$OUT" <<'PY'
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request

OUT = Path(sys.argv[1]).resolve()
WORK = OUT / "_work"
WORK.mkdir(parents=True, exist_ok=True)

CASES = [
    {
        "root_id": "CROOT-00608-03",
        "slot": "R1",
        "repo": "zts212653/clowder-ai",
        "issue": 1050,
        "pr": 1051,
        "rule": "js/path-injection",
        "target_files": [
            "packages/api/src/routes/agent-hooks.ts",
        ],
        "precedent_files": [
            "packages/api/src/utils/project-path.ts",
            "packages/api/src/utils/index.ts",
        ],
        "focal_mechanism": "Use the repository project-path validation mechanism around validateProjectPath(rawPath) in the MCP sync route flow.",
    },
    {
        "root_id": "CROOT-03429-01",
        "slot": "R2",
        "repo": "intellectronica/ruler",
        "issue": 570,
        "pr": 571,
        "rule": "js/insecure-temporary-file",
        "target_files": [
            "src/agents/CrushAgent.ts",
        ],
        "precedent_files": [
            "src/core/FileSystemUtils.ts",
        ],
        "focal_mechanism": "Route generated-file writes through the existing writeGeneratedFile helper.",
    },
    {
        "root_id": "CROOT-04131-01",
        "slot": "R3",
        "repo": "ruvnet/ruflo",
        "issue": 2721,
        "pr": 2725,
        "rule": "javascript.lang.security.detect-child-process.detect-child-process",
        "target_files": [
            "plugins/ruflo-core/scripts/ruflo-hook.cjs",
        ],
        "precedent_files": [
            "plugins/ruflo-core/scripts/ruflo-hook.cjs",
        ],
        "focal_mechanism": "Use a child-process command lookup based on where <cmd> on Windows or command -v <cmd> elsewhere.",
    },
    {
        "root_id": "CROOT-05355-01",
        "slot": "R4",
        "repo": "ThinkInAIXYZ/deepchat",
        "issue": 1695,
        "pr": 1697,
        "rule": "js/insecure-temporary-file",
        "target_files": [
            "src/main/presenter/filePresenter/mimeDetection.ts",
        ],
        "precedent_files": [
            "src/main/presenter/filePresenter/mime.ts",
        ],
        "focal_mechanism": "Open the candidate file with fs.open(filePath, 'r') and inspect bytes through a file handle.",
    },
    {
        "root_id": "CROOT-10339-01",
        "slot": "R5",
        "repo": "binaricat/Netcatty",
        "issue": 2337,
        "pr": 2354,
        "rule": "js/clear-text-storage-of-sensitive-data",
        "target_files": [
            "application/defaultKeyPassphrases.ts",
            "components/vault/useVaultImportHandlers.ts",
        ],
        "precedent_files": [
            "application/defaultKeyPassphrases.ts",
        ],
        "focal_mechanism": "When storing a passphrase, fall back from encryptField(passphrase) to the original passphrase via nullish coalescing.",
    },
    {
        "root_id": "CROOT-16213-01",
        "slot": "R6",
        "repo": "thomasnordquist/MQTT-Explorer",
        "issue": 941,
        "pr": 942,
        "rule": "js/clear-text-storage-of-sensitive-data",
        "target_files": [
            "app/src/browserEventBus.ts",
        ],
        "precedent_files": [
            "app/src/components/BrowserAuthWrapper.tsx",
        ],
        "focal_mechanism": "Persist the MQTT password in browser sessionStorage under mqtt-explorer-password.",
    },
]


def api_json(url: str):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "agentic-security-context-ablation-research",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def run(cmd, cwd=None, check=True):
    p = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and p.returncode != 0:
        raise RuntimeError(
            f"command failed: {cmd}\nstdout:\n{p.stdout}\nstderr:\n{p.stderr}"
        )
    return p


def git_show(repo_dir: Path, sha: str, path: str):
    p = run(["git", "show", f"{sha}:{path}"], cwd=repo_dir, check=False)
    if p.returncode != 0:
        return None
    return p.stdout


def safe_name(path: str):
    return path.replace("/", "__")

manifest = {
    "schema": "T1_SELECTED6_EXTRACT_v1",
    "selection_frozen_sha256": "571a976a6db8f9ed2e170130bde8d1bc791bc3ac2da9a0a835a7aadb87baea4c",
    "cases": [],
}

for case in CASES:
    slot = case["slot"]
    root_id = case["root_id"]
    owner_repo = case["repo"]
    issue_num = case["issue"]
    pr_num = case["pr"]

    case_out = OUT / f"{slot}__{root_id}"
    case_out.mkdir(parents=True, exist_ok=True)
    (case_out / "BASE_TARGET_FILES").mkdir()
    (case_out / "BASE_PRECEDENT_FILES").mkdir()
    (case_out / "HEAD_TARGET_FILES").mkdir()
    (case_out / "BASE_CHANGED_FILES").mkdir()

    issue = api_json(f"https://api.github.com/repos/{owner_repo}/issues/{issue_num}")
    pr = api_json(f"https://api.github.com/repos/{owner_repo}/pulls/{pr_num}")

    base_sha = pr["base"]["sha"]
    head_sha = pr["head"]["sha"]

    task = (
        "# ORIGINAL GITHUB ISSUE\n\n"
        f"Repository: {owner_repo}\n"
        f"Issue: #{issue_num}\n"
        f"Title: {issue.get('title', '')}\n\n"
        f"{issue.get('body') or ''}\n"
    )
    (case_out / "TASK_ORIGINAL.md").write_text(task, encoding="utf-8")

    repo_dir = WORK / slot
    repo_dir.mkdir(parents=True, exist_ok=True)
    run(["git", "init", "-q"], cwd=repo_dir)
    run(["git", "remote", "add", "origin", f"https://github.com/{owner_repo}.git"], cwd=repo_dir)
    run(["git", "fetch", "-q", "--no-tags", "origin", base_sha, head_sha], cwd=repo_dir)

    # Historical diff and metadata are for packet construction/audit only.
    diff = run(["git", "diff", "--find-renames", "--unified=40", base_sha, head_sha], cwd=repo_dir).stdout
    (case_out / "HISTORICAL_DIFF_AUDIT_ONLY.patch").write_text(diff, encoding="utf-8")

    changed = run(["git", "diff", "--name-only", base_sha, head_sha], cwd=repo_dir).stdout.splitlines()
    (case_out / "CHANGED_FILES.txt").write_text("\n".join(changed) + "\n", encoding="utf-8")

    # Save all reasonably sized text-like base changed files for context construction.
    saved_changed = []
    for path in changed:
        content = git_show(repo_dir, base_sha, path)
        if content is None:
            continue
        if len(content.encode("utf-8", errors="ignore")) > 1_000_000:
            continue
        outp = case_out / "BASE_CHANGED_FILES" / safe_name(path)
        outp.write_text(content, encoding="utf-8")
        saved_changed.append(path)

    saved_targets = []
    for path in case["target_files"]:
        base_content = git_show(repo_dir, base_sha, path)
        head_content = git_show(repo_dir, head_sha, path)
        if base_content is not None:
            (case_out / "BASE_TARGET_FILES" / safe_name(path)).write_text(base_content, encoding="utf-8")
            saved_targets.append(path)
        if head_content is not None:
            (case_out / "HEAD_TARGET_FILES" / safe_name(path)).write_text(head_content, encoding="utf-8")

    saved_precedents = []
    for path in case["precedent_files"]:
        base_content = git_show(repo_dir, base_sha, path)
        if base_content is not None:
            (case_out / "BASE_PRECEDENT_FILES" / safe_name(path)).write_text(base_content, encoding="utf-8")
            saved_precedents.append(path)

    # Search base for obvious mechanism anchors. This is audit support only.
    anchors = []
    anchor_terms = {
        "R1": ["validateProjectPath", "validateProjectPathDetailed"],
        "R2": ["writeGeneratedFile"],
        "R3": ["command -v", "where ${cmd}", "execSync", "spawnSync"],
        "R4": ["fs.open(filePath, 'r')", "isLikelyTextFile"],
        "R5": ["encryptField(passphrase) ?? passphrase", "encryptField(passphrase)"],
        "R6": ["mqtt-explorer-password", "sessionStorage.setItem"],
    }[slot]

    for term in anchor_terms:
        p = run(["git", "grep", "-n", "-F", term, base_sha, "--", "."], cwd=repo_dir, check=False)
        if p.stdout.strip():
            anchors.append({"term": term, "matches": p.stdout.splitlines()[:100]})

    metadata = {
        **case,
        "issue_title": issue.get("title", ""),
        "issue_url": issue.get("html_url", ""),
        "pr_url": pr.get("html_url", ""),
        "base_sha": base_sha,
        "head_sha": head_sha,
        "base_ref": pr["base"].get("ref", ""),
        "head_ref": pr["head"].get("ref", ""),
        "saved_target_files": saved_targets,
        "saved_precedent_files": saved_precedents,
        "saved_base_changed_files": saved_changed,
        "anchor_search": anchors,
    }

    (case_out / "METADATA.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    manifest["cases"].append(metadata)

# Remove temporary git repositories from export.
shutil.rmtree(WORK)

(OUT / "MANIFEST.json").write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

# Hash every exported file for auditability.
checks = []
for p in sorted(OUT.rglob("*")):
    if p.is_file() and p.name != "SHA256SUMS.txt":
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        checks.append(f"{h}  {p.relative_to(OUT)}")
(OUT / "SHA256SUMS.txt").write_text("\n".join(checks) + "\n", encoding="utf-8")

print(json.dumps({
    "status": "PASS",
    "cases": len(manifest["cases"]),
    "roots": [x["root_id"] for x in manifest["cases"]],
}, indent=2))
print("STATUS=DONE")
PY

cd "$HOME/research_artifacts"
tar -czf "$(basename "$ARCHIVE")" "$(basename "$OUT")"
sha256sum "$ARCHIVE"
ls -lh "$ARCHIVE"
