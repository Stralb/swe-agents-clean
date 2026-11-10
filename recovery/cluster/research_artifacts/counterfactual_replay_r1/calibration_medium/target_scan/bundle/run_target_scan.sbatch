#!/bin/bash
#SBATCH --job-name=cf_cal_tgt
#SBATCH --partition=batch
#SBATCH --array=0-15%8
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=01:00:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/calibration_medium/target_scan/logs/%A_%a.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/calibration_medium/target_scan/logs/%A_%a.err
set -euo pipefail

CAL="$HOME/research_artifacts/counterfactual_replay_r1/calibration_medium"
BUNDLE="$CAL/target_scan/bundle"
MAN="$BUNDLE/SCAN_MANIFEST.csv"
RESULTS="$CAL/target_scan/results"
CACHE="$CAL/target_scan/base_cache"
SUITES="$CAL/target_scan/suites"
mkdir -p "$RESULTS" "$CACHE" "$SUITES" "$CAL/target_scan/logs"

IFS=$'\t' read -r RUN PAIR ROLE REPL REPOSITORY BASESHA REPOFILE TARGET < <(
python3 - "$MAN" "$SLURM_ARRAY_TASK_ID" <<'PY'
import csv,sys
r=list(csv.DictReader(open(sys.argv[1],encoding='utf-8')))[int(sys.argv[2])]
print('\t'.join(r[k] for k in ['run_id','pair_id','role','replicate','repository','base_sha','repo_file','target_rule']))
PY
)

echo "RUN=$RUN PAIR=$PAIR ROLE=$ROLE TARGET=$TARGET REPOFILE=$REPOFILE"
CODEQL="$(command -v codeql || true)"
if [ -z "$CODEQL" ]; then
  for c in "$HOME/codeql/codeql" "$HOME/tools/codeql/codeql"; do [ -x "$c" ] && CODEQL="$c" && break; done
fi
[ -n "$CODEQL" ] || { echo 'ERROR: codeql not found'; exit 2; }

SAFE_RULE="${TARGET//\//_}"
QLS="$SUITES/${SAFE_RULE}.qls"
if [ ! -s "$QLS" ]; then
  cat > "$QLS.tmp.$$" <<EOF
- qlpack: codeql/javascript-queries
- include:
    id: $TARGET
EOF
  mv "$QLS.tmp.$$" "$QLS"
fi
# Cheap preflight: exact suite must resolve at least one query before any DB work.
RESOLVED="$($CODEQL resolve queries "$QLS" 2>&1)" || { echo "$RESOLVED"; exit 3; }
echo "$RESOLVED" | grep -q '\.ql' || { echo "ERROR: target suite resolved no .ql query for $TARGET"; echo "$RESOLVED"; exit 4; }

ARCH="$CAL/dedup/repos/$REPOFILE"
[ -s "$ARCH" ] || { echo "ERROR: missing repo archive $ARCH"; exit 5; }
PATCH="$BUNDLE/patches/$RUN.patch"
[ -f "$PATCH" ] || { echo "ERROR: missing patch $PATCH"; exit 6; }

WORK="${SLURM_TMPDIR:-/tmp}/${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}"
rm -rf "$WORK"; mkdir -p "$WORK/unpack" "$WORK/head"

tar -xzf "$ARCH" -C "$WORK/unpack"
ROOT="$WORK/unpack"
if [ ! -d "$ROOT/.git" ]; then
  GITDIR="$(find "$WORK/unpack" -mindepth 1 -maxdepth 3 -type d -name .git -print -quit || true)"
  if [ -n "$GITDIR" ]; then ROOT="$(dirname "$GITDIR")"; else
    TOPS=("$WORK/unpack"/*)
    if [ "${#TOPS[@]}" -eq 1 ] && [ -d "${TOPS[0]}" ]; then ROOT="${TOPS[0]}"; fi
  fi
fi

# Cache exact-target base SARIF once per unique base archive + target rule.
BASEKEY="${REPOFILE%.tar.gz}__${SAFE_RULE}"
BASESARIF="$CACHE/${BASEKEY}.sarif"
LOCK="$CACHE/${BASEKEY}.lock"
if [ ! -s "$BASESARIF" ]; then
  if mkdir "$LOCK" 2>/dev/null; then
    trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT
    BDB="$WORK/base-db"
    "$CODEQL" database create "$BDB" --language=javascript --source-root="$ROOT" --overwrite
    "$CODEQL" database analyze "$BDB" "$QLS" --format=sarif-latest --output="$WORK/base.sarif" --rerun
    cp "$WORK/base.sarif" "$BASESARIF.tmp.$$"
    mv "$BASESARIF.tmp.$$" "$BASESARIF"
    rmdir "$LOCK" || true
    trap - EXIT
  else
    for _ in $(seq 1 240); do
      [ -s "$BASESARIF" ] && break
      sleep 5
    done
    [ -s "$BASESARIF" ] || { echo "ERROR: timed out waiting for base cache $BASEKEY"; exit 7; }
  fi
fi

cp -a "$ROOT/." "$WORK/head/"
cd "$WORK/head"
if [ -d .git ]; then git apply --check "$PATCH" && git apply "$PATCH"; else patch -p1 --dry-run < "$PATCH" && patch -p1 < "$PATCH"; fi
HDB="$WORK/head-db"
"$CODEQL" database create "$HDB" --language=javascript --source-root="$WORK/head" --overwrite
"$CODEQL" database analyze "$HDB" "$QLS" --format=sarif-latest --output="$WORK/head.sarif" --rerun

python3 "$BUNDLE/summarize_sarif.py" "$BASESARIF" "$WORK/head.sarif" "$PATCH" "$TARGET" "$RUN" "$PAIR" "$ROLE" "$RESULTS/$RUN.csv"
cp "$WORK/head.sarif" "$RESULTS/$RUN.head.sarif"
echo "DONE=$RUN"
