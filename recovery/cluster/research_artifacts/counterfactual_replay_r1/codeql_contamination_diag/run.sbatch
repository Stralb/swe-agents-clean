#!/bin/bash
#SBATCH --job-name=ql_contam
#SBATCH --partition=batch
#SBATCH --time=00:20:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/codeql_contamination_diag/result.txt
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/codeql_contamination_diag/error.txt

MINER="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"
RESULTS="$MINER/data/distributed_spool/codeql_security/results/imported"
cd "$MINER"

python3 - <<'PY'
import json, glob, pathlib

target = {
    ("js/file-system-race",
     "src/extension/services/commentary-jsonl-watcher.ts", 124),
    ("js/missing-origin-check",
     "src/webview/src/components/CommentaryPanel.tsx", 42),
}

print("=== ORIGINAL ARTIFACT PAYLOAD ===")
p = pathlib.Path(
    "data/distributed_spool/codeql_security/results/imported/"
    "scanner-job-600723.json"
)
d = json.loads(p.read_text())
print(json.dumps(d.get("task", {}).get("payload", {}), indent=2))

print("\n=== EXACT FINDING SIGNATURE ACROSS ALL CODEQL RESULTS ===")
matches = []

for fn in glob.glob(
    "data/distributed_spool/codeql_security/results/imported/*.json"
):
    try:
        x = json.load(open(fn))
    except Exception:
        continue

    hits = set()
    for f in x.get("result", {}).get("findings", []):
        sig = (
            f.get("rule_id") or f.get("ruleId"),
            f.get("file_path") or f.get("path"),
            f.get("line"),
        )
        if sig in target:
            hits.add(sig)

    if hits:
        r = x.get("result", {})
        payload = x.get("task", {}).get("payload", {})
        matches.append((
            pathlib.Path(fn).name,
            r.get("job_id"),
            r.get("case_id"),
            payload.get("case_id"),
            payload.get("repo_url"),
            payload.get("base_sha"),
            payload.get("head_sha"),
            sorted(hits),
        ))

for m in matches:
    print(m)

print("MATCHING_ARTIFACTS=", len(matches))
PY

echo
echo "=== TEMP / DATABASE / SARIF PATH LOGIC ==="
grep -nE \
'Temporary|mkdtemp|tempfile|tmp|database|sarif|clone|checkout|source_root|source-root|db_path|output' \
src/scanners/codeql_scanner.py | head -220

echo
echo "=== DISTRIBUTED WORKER CALL ==="
sed -n '820,960p' src/distributed/codeql_pipeline.py

echo
echo "=== STATUS ==="
echo DONE
