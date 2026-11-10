#!/bin/bash
#SBATCH --job-name=bx_behav2
#SBATCH --partition=biggpu
#SBATCH --time=03:00:00
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/bx_behavior_recovery_v2.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/bx_behavior_recovery_v2.err

set -u

ROOT="$HOME/research_artifacts"
DB="$ROOT/boundary_x_master.sqlite"
GENZIP="$ROOT/BOUNDARY_X_GENERATIONS_GPT56SOL_v1.zip"
WORK="/var/tmp/bx_behavior_recovery_${SLURM_JOB_ID}"
OUT="$ROOT/bx_behavior_recovery_${SLURM_JOB_ID}"

export PATH="$HOME/tools/node24/bin:$HOME/.bun/bin:$PATH"
export CI=true
export TMPDIR="$WORK/tmp"
export TMP="$TMPDIR"
export TEMP="$TMPDIR"

mkdir -p "$WORK/tmp" "$WORK/gen" "$OUT/logs"
trap 'rm -rf "$WORK"' EXIT

python3 - "$GENZIP" "$WORK/gen" "$DB" "$WORK/workplan.tsv" <<'PY'
import csv, os, sqlite3, sys, zipfile
zpath,gdir,dbpath,out=sys.argv[1:]
with zipfile.ZipFile(zpath) as z:
    z.extractall(gdir)
rows=list(csv.DictReader(open(os.path.join(gdir,'generation_manifest.csv'),encoding='utf-8')))
db=sqlite3.connect(dbpath)
with open(out,'w',encoding='utf-8',newline='') as f:
    w=csv.writer(f,delimiter='\t',lineterminator='\n')
    w.writerow(['blind_id','run_id','case_id','arm','repo','base_sha','patch'])
    for m in rows:
        if m['status']!='GENERATED':
            continue
        r=db.execute('''
          SELECT r.run_id,r.case_id,r.arm,t.repo,t.base_sha
          FROM runs r JOIN tasks t ON t.case_id=r.case_id
          WHERE r.randomized_order=?
        ''',(int(m['order']),)).fetchone()
        if not r or int(r[1])==3786:
            continue
        patch=os.path.join(gdir,m['patch_file'])
        w.writerow([m['blind_id'],*r,patch])
db.close()
PY

echo "STATUS=STARTING"
echo "NODE=$(hostname)"
echo "NODE_VERSION=$(node -v)"
echo "BUN_VERSION=$(bun -v)"
echo "RECOVERY_RUNS=$(($(wc -l < "$WORK/workplan.tsv")-1))"
echo "CASES=3340,3448,3699,6150,16633"

changed_tests() {
  local patch="$1"
  awk '/^diff --git a\// {p=$3; sub(/^a\//,"",p); if (p ~ /(^|\/)test.*\.(ts|tsx|js|mjs|cjs)$/ || p ~ /\.test\.(ts|tsx|js|mjs|cjs)$/ || p ~ /\.spec\.(ts|tsx|js|mjs|cjs)$/) print p}' "$patch" | sort -u
}

prepare_case() {
  local cid="$1"
  local cdir="$WORK/case_$cid"
  mkdir -p "$cdir"
  awk -F '\t' -v c="$cid" 'NR==1 || $3==c' "$WORK/workplan.tsv" > "$cdir/runs.tsv"
  local first
  first="$(sed -n '2p' "$cdir/runs.tsv")"
  [ -n "$first" ] || return 0

  local blind runid caseid arm repo base patch
  IFS=$'\t' read -r blind runid caseid arm repo base patch <<< "$first"

  local bare="$cdir/repo.git"
  local template="$cdir/template"
  git init -q --bare "$bare"
  git --git-dir="$bare" remote add origin "https://github.com/$repo.git"
  if ! timeout 300 git --git-dir="$bare" fetch -q --depth=1 origin "$base"; then
    echo -e "$cid\tCASE_PREP_ERROR\tFETCH_FAILED" > "$cdir/case_error.tsv"
    return 0
  fi
  git --git-dir="$bare" worktree add -q --detach "$template" "$base"

  # Install the unmodified base dependency tree once for cases whose generated
  # patches do not alter package manifests. Test runners are called directly,
  # avoiding package-manager auto-install / non-TTY behavior.
  local prep_rc=0
  case "$cid" in
    3340|3448)
      (cd "$template" && CI=true corepack pnpm install --frozen-lockfile --ignore-scripts --prefer-offline) \
        >"$OUT/logs/case_${cid}_deps.log" 2>&1 || prep_rc=$?
      ;;
    3699)
      (cd "$template/server" && npm ci --ignore-scripts --no-audit --no-fund) \
        >"$OUT/logs/case_${cid}_deps.log" 2>&1 || prep_rc=$?
      ;;
    6150)
      (cd "$template" && npm ci --ignore-scripts --no-audit --no-fund) \
        >"$OUT/logs/case_${cid}_deps.log" 2>&1 || prep_rc=$?
      ;;
    16633)
      # package.json changes in generated patches; install per-run below.
      ;;
  esac
  if [ "$prep_rc" -ne 0 ]; then
    echo -e "$cid\tCASE_PREP_ERROR\tDEPENDENCY_INSTALL_RC_$prep_rc" > "$cdir/case_error.tsv"
    return 0
  fi

  tail -n +2 "$cdir/runs.tsv" | while IFS=$'\t' read -r blind runid caseid arm repo base patch; do
    local rdir="$cdir/$blind"
    local log="$OUT/logs/${blind}.verify.log"
    local ilog="$OUT/logs/${blind}.install.log"
    local testlist="$OUT/logs/${blind}.tests.txt"
    local status="INFRA_ERROR"
    local rc=0

    git --git-dir="$bare" worktree add -q --detach "$rdir" "$base"
    if ! git -C "$rdir" apply --whitespace=nowarn "$patch" >"$OUT/logs/${blind}.apply.log" 2>&1; then
      echo -e "$blind\t$runid\t$caseid\t$arm\tPATCH_APPLY_ERROR\t\t1" > "$cdir/${blind}.result.tsv"
      git --git-dir="$bare" worktree remove -f "$rdir" >/dev/null 2>&1 || true
      continue
    fi

    changed_tests "$patch" > "$testlist"

    case "$cid" in
      3340)
        rm -rf "$rdir/node_modules"
        ln -s "$template/node_modules" "$rdir/node_modules"
        mapfile -t tests < <(grep -E '^src/main/(utils|services/webSearch/utils)/__tests__/.*\.test\.ts$' "$testlist")
        # BX018 added no tests; use the existing consumer tests as a compatibility smoke.
        if [ ${#tests[@]} -eq 0 ]; then
          [ -f "$rdir/src/main/ai/mcp/servers/__tests__/fetch.test.ts" ] && tests+=("src/main/ai/mcp/servers/__tests__/fetch.test.ts")
          [ -f "$rdir/src/main/services/webSearch/utils/__tests__/fetchContent.test.ts" ] && tests+=("src/main/services/webSearch/utils/__tests__/fetchContent.test.ts")
        fi
        printf '%s\n' "${tests[@]}" > "$testlist"
        if [ ${#tests[@]} -eq 0 ]; then rc=97; else
          (cd "$rdir" && "$template/node_modules/.bin/vitest" run "${tests[@]}") >"$log" 2>&1 || rc=$?
        fi
        ;;
      3448)
        rm -rf "$rdir/node_modules"
        ln -s "$template/node_modules" "$rdir/node_modules"
        tests=("src/platforms/web/agent-browser-lifecycle.test.ts")
        printf '%s\n' "${tests[@]}" > "$testlist"
        (cd "$rdir" && "$template/node_modules/.bin/vitest" run "${tests[@]}") >"$log" 2>&1 || rc=$?
        ;;
      3699)
        rm -rf "$rdir/server/node_modules" "$rdir/node_modules"
        if [ -d "$template/server/node_modules" ]; then ln -s "$template/server/node_modules" "$rdir/server/node_modules"; fi
        if [ -d "$template/node_modules" ]; then ln -s "$template/node_modules" "$rdir/node_modules"; fi
        mapfile -t tests < <(grep -E '^server/tests/unit/training-agent-.*\.test\.ts$' "$testlist")
        printf '%s\n' "${tests[@]}" > "$testlist"
        runner=""
        [ -x "$template/server/node_modules/.bin/vitest" ] && runner="$template/server/node_modules/.bin/vitest"
        [ -z "$runner" ] && [ -x "$template/node_modules/.bin/vitest" ] && runner="$template/node_modules/.bin/vitest"
        if [ ${#tests[@]} -eq 0 ] || [ -z "$runner" ]; then rc=97; else
          rel=(); for t in "${tests[@]}"; do rel+=("${t#server/}"); done
          (cd "$rdir/server" && "$runner" run "${rel[@]}") >"$log" 2>&1 || rc=$?
        fi
        ;;
      6150)
        rm -rf "$rdir/node_modules"
        ln -s "$template/node_modules" "$rdir/node_modules"
        mapfile -t node_tests < <(grep -E '^test/node/ai/daemons/wake/.*\.test\.mjs$' "$testlist")
        mapfile -t pw_tests < <(grep -E '^test/playwright/unit/ai/daemons/wake/.*\.spec\.mjs$' "$testlist")
        # One variant keeps its unit test next to the implementation.
        mapfile -t local_tests < <(grep -E '^ai/daemons/wake-shape-b/test/.*\.test\.mjs$' "$testlist")
        printf '%s\n' "${node_tests[@]}" "${local_tests[@]}" "${pw_tests[@]}" | sed '/^$/d' > "$testlist"
        : > "$log"
        if [ ${#node_tests[@]} -eq 0 ] && [ ${#local_tests[@]} -eq 0 ] && [ ${#pw_tests[@]} -eq 0 ]; then rc=97
        else
          if [ ${#node_tests[@]} -gt 0 ]; then (cd "$rdir" && node --test "${node_tests[@]}") >>"$log" 2>&1 || rc=$?; fi
          if [ "$rc" -eq 0 ] && [ ${#local_tests[@]} -gt 0 ]; then (cd "$rdir" && node --test "${local_tests[@]}") >>"$log" 2>&1 || rc=$?; fi
          if [ "$rc" -eq 0 ] && [ ${#pw_tests[@]} -gt 0 ]; then (cd "$rdir" && "$template/node_modules/.bin/playwright" test "${pw_tests[@]}") >>"$log" 2>&1 || rc=$?; fi
        fi
        ;;
      16633)
        # Generated Sarah patches alter package.json, so install the patched dependency graph.
        (cd "$rdir" && bun install --no-save --ignore-scripts) >"$ilog" 2>&1 || rc=$?
        if [ "$rc" -eq 0 ]; then
          mapfile -t tests < <(grep -E '^apps/sarah/src/services/(.*coding.*fleet.*|relationship-policy)\.test\.ts$' "$testlist")
          # Include server.test only when the generation itself changed it.
          grep -qx 'apps/sarah/src/server.test.ts' "$testlist" && tests+=("apps/sarah/src/server.test.ts")
          printf '%s\n' "${tests[@]}" > "$testlist"
          if [ ${#tests[@]} -eq 0 ]; then rc=97; else
            (cd "$rdir" && bun test "${tests[@]}") >"$log" 2>&1 || rc=$?
          fi
        fi
        ;;
    esac

    if [ "$rc" -eq 0 ]; then
      status="VERIFY_PASS"
    elif [ "$rc" -eq 97 ]; then
      status="NO_TARGET_TEST"
    elif grep -Eqi 'Cannot find module|Cannot find package|ERR_MODULE_NOT_FOUND|MODULE_NOT_FOUND|command not found|No such file|ENOENT|ETXTBSY|ENOSPC|failed to load config|Startup Error' "$log" "$ilog" 2>/dev/null; then
      status="INFRA_ERROR"
    else
      status="VERIFY_FAIL"
    fi

    tests_compact="$(paste -sd ';' "$testlist" 2>/dev/null || true)"
    echo -e "$blind\t$runid\t$caseid\t$arm\t$status\t$tests_compact\t$rc" > "$cdir/${blind}.result.tsv"
    git --git-dir="$bare" worktree remove -f "$rdir" >/dev/null 2>&1 || true
  done
}

for cid in 3340 3448 3699 6150 16633; do
  prepare_case "$cid" >"$OUT/logs/case_${cid}.driver.log" 2>&1 &
done
wait

python3 - "$WORK" "$OUT" <<'PY'
import csv, os, sys, zipfile, collections
work,out=sys.argv[1:]
rows=[]; errors=[]
for name in os.listdir(work):
    if not name.startswith('case_'): continue
    cdir=os.path.join(work,name)
    ce=os.path.join(cdir,'case_error.tsv')
    if os.path.isfile(ce): errors.append(open(ce,encoding='utf-8').read().strip())
    for f in os.listdir(cdir):
        if f.endswith('.result.tsv'):
            x=open(os.path.join(cdir,f),encoding='utf-8').read().rstrip('\n').split('\t')
            x += ['']*(7-len(x)); rows.append(x[:7])
rows.sort(key=lambda r:r[0])
with open(os.path.join(out,'RECOVERY_RESULTS.csv'),'w',newline='',encoding='utf-8') as f:
    w=csv.writer(f); w.writerow(['blind_id','run_id','case_id','arm','verification_status','tests','rc']); w.writerows(rows)

c=collections.Counter(r[4] for r in rows)
lines=['STATUS=BEHAVIOR_RECOVERY_COMPLETE',f'RUNS={len(rows)}']
for k in ['VERIFY_PASS','VERIFY_FAIL','INFRA_ERROR','NO_TARGET_TEST','PATCH_APPLY_ERROR']:
    lines.append(f'{k}={c[k]}')
if errors: lines.append('CASE_PREP_ERRORS='+' | '.join(errors))
lines.append('BY_CASE_ARM')
for key in sorted(set((r[2],r[3]) for r in rows), key=lambda x:(int(x[0]),x[1])):
    subset=[r for r in rows if (r[2],r[3])==key]
    cc=collections.Counter(r[4] for r in subset)
    lines.append(f'CASE={key[0]} ARM={key[1]} N={len(subset)} PASS={cc["VERIFY_PASS"]} FAIL={cc["VERIFY_FAIL"]} INFRA={cc["INFRA_ERROR"]} NO_TEST={cc["NO_TARGET_TEST"]}')
open(os.path.join(out,'SUMMARY.txt'),'w',encoding='utf-8').write('\n'.join(lines)+'\n')

final='/home-mscluster/astrauss/research_artifacts/BOUNDARY_X_BEHAVIOR_RECOVERY_v2.zip'
with zipfile.ZipFile(final,'w',zipfile.ZIP_DEFLATED) as z:
    for root,dirs,files in os.walk(out):
        for fn in files:
            p=os.path.join(root,fn); z.write(p,os.path.relpath(p,out))
print('\n'.join(lines))
print('RESULT_ZIP='+final)
PY

echo "SHA256=$(sha256sum "$ROOT/BOUNDARY_X_BEHAVIOR_RECOVERY_v2.zip" | awk '{print $1}')"
echo "BYTES=$(stat -c%s "$ROOT/BOUNDARY_X_BEHAVIOR_RECOVERY_v2.zip")"
