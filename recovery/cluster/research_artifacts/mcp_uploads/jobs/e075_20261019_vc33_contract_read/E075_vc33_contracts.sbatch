#!/bin/bash
#SBATCH --job-name=E075_vc33_source_audit
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:06:00
set -euo pipefail
ROOT=/home-mscluster/astrauss/RL-ARC-AGI-3-Project
echo "==== RECENT E035 NOTES ===="
sed -n '1,220p' "$ROOT/E035_NOTES.md" 2>/dev/null || true
echo "==== E035 RUNNER CLI AND CONTRACT ===="
sed -n '1,220p' "$ROOT/scripts/e035/run_candidate.py"
echo "==== E037 RUNNER CLI AND CONTRACT ===="
sed -n '1,190p' "$ROOT/scripts/e037/run_candidate.py"
echo "==== E035 CONTROL/PROCEDURE CONFIG ===="
for f in "$ROOT/results/e035/systems/e035_e033_control.json" "$ROOT/results/e035/systems/e035_guarded_full.json" "$ROOT/results/e034/systems/e034_full.json" "$ROOT/results/e034/systems/e034_e033_control.json";do
 echo "FILE $f";sed -n '1,75p' "$f";done
echo "==== EXISTING E035-E037 SCORES/SUMMARIES ===="
find "$ROOT/results/e035" "$ROOT/results/e036" "$ROOT/results/e037" -maxdepth 3 -type f \( -name '*SUMMARY*.json' -o -name '*DECISION*.json' -o -name '*REPORT*.md' -o -name '*evidence*.json' \) -printf '%p\n' 2>/dev/null | head -n 85
echo "E075_VC33_AUDIT_END"