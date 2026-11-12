#!/bin/bash
#SBATCH --job-name=cf_hist_val
#SBATCH --partition=batch
#SBATCH --array=0-3%4
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/calibration_medium/historical_validation/logs/%A_%a.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/calibration_medium/historical_validation/logs/%A_%a.err
set -euo pipefail

CAL="$HOME/research_artifacts/counterfactual_replay_r1/calibration_medium"
HV="$CAL/historical_validation"
BUNDLE="$HV/bundle"
MAN="$BUNDLE/HISTORICAL_VALIDATION_MANIFEST.csv"
RESULTS="$HV/results"
SUITES="$HV/suites"
mkdir -p "$RESULTS" "$SUITES" "$HV/logs"

IFS=$'\t' read -r PAIR REPO URL BASE HEAD REPOFILE TARGET PR < <(
python3 - "$MAN" "$SLURM_ARRAY_TASK_ID" <<'PY'
import csv,sys
r=list(csv.DictReader(open(sys.argv[1],encoding='utf-8')))[int(sys.argv[2])]
print('\t'.join(r[k] for k in ['pair_id','repository','repository_url','base_sha','head_sha','repo_file','target_rule','pr_number']))
PY
)

echo "PAIR=$PAIR REPO=$REPO PR=$PR TARGET=$TARGET"
CODEQL="$(command -v codeql || true)"
if [ -z "$CODEQL" ]; then
  for c in "$HOME/codeql/codeql" "$HOME/tools/codeql/codeql"; do [ -x "$c" ] && CODEQL="$c" && break; done
fi
[ -n "$CODEQL" ] || { echo 'ERROR: codeql not found'; exit 2; }

SAFE_RULE="${TARGET//\//_}"
QLS="$SUITES/${SAFE_RULE}.qls"
if [ ! -s "$QLS" ]; then
  cat > "$QLS.tmp.$$" <<QEOF
- qlpack: codeql/javascript-queries
- include:
    id: $TARGET
QEOF
  mv "$QLS.tmp.$$" "$QLS"
fi
RESOLVED="$($CODEQL resolve queries "$QLS" 2>&1)" || { echo "$RESOLVED"; exit 3; }
echo "$RESOLVED" | grep -q '\.ql' || { echo "ERROR: target suite resolved no query for $TARGET"; exit 4; }

ARCH="$CAL/dedup/repos/$REPOFILE"
[ -s "$ARCH" ] || { echo "ERROR: missing existing base archive $ARCH"; exit 5; }

WORK="${SLURM_TMPDIR:-/tmp}/${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}"
rm -rf "$WORK"; mkdir -p "$WORK/base_unpack" "$WORK/repo"
tar -xzf "$ARCH" -C "$WORK/base_unpack"
BASE_ROOT="$WORK/base_unpack"
TOPS=("$WORK/base_unpack"/*)
if [ "${#TOPS[@]}" -eq 1 ] && [ -d "${TOPS[0]}" ]; then BASE_ROOT="${TOPS[0]}"; fi

# Fetch only the two exact historical commits. No full repository clone.
git -C "$WORK/repo" init -q
git -C "$WORK/repo" remote add origin "$URL"
git -C "$WORK/repo" fetch -q --depth=1 origin "$BASE"
git -C "$WORK/repo" fetch -q --depth=1 origin "$HEAD"
git -C "$WORK/repo" cat-file -e "$BASE^{commit}"
git -C "$WORK/repo" cat-file -e "$HEAD^{commit}"
git -C "$WORK/repo" diff --unified=0 "$BASE" "$HEAD" > "$WORK/historical.diff"
git -C "$WORK/repo" checkout -q --detach "$HEAD"

BDB="$WORK/base-db"
HDB="$WORK/head-db"
"$CODEQL" database create "$BDB" --language=javascript --source-root="$BASE_ROOT" --overwrite
"$CODEQL" database analyze "$BDB" "$QLS" --format=sarif-latest --output="$WORK/base.sarif" --rerun
"$CODEQL" database create "$HDB" --language=javascript --source-root="$WORK/repo" --overwrite
"$CODEQL" database analyze "$HDB" "$QLS" --format=sarif-latest --output="$WORK/head.sarif" --rerun

python3 "$BUNDLE/summarize_pair.py" \
  "$WORK/base.sarif" "$WORK/head.sarif" "$WORK/historical.diff" \
  "$PAIR" "$REPO" "$BASE" "$HEAD" "$TARGET" "$RESULTS/$PAIR.csv"
cp "$WORK/base.sarif" "$RESULTS/$PAIR.base.sarif"
cp "$WORK/head.sarif" "$RESULTS/$PAIR.head.sarif"
cp "$WORK/historical.diff" "$RESULTS/$PAIR.diff"
echo "DONE=$PAIR"
