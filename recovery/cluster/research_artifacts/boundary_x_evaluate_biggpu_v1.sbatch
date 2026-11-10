#!/bin/bash
#SBATCH --job-name=bx_eval_bg
#SBATCH --partition=biggpu
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/bx_evaluate_biggpu.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/bx_evaluate_biggpu.err

set -u

ROOT="$HOME/research_artifacts"
MASTER="$ROOT/boundary_x_master.sqlite"
GENZIP="$ROOT/BOUNDARY_X_GENERATIONS_GPT56SOL_v1.zip"
WORK="/var/tmp/bx_eval_${SLURM_JOB_ID}"
OUT="$ROOT/boundary_x_eval_${SLURM_JOB_ID}"
RESULT_DB="$OUT/boundary_x_master_results.sqlite"

export PATH="$HOME/tools/node24/bin:$HOME/.bun/bin:$HOME/tools/codeql:$PATH"
export TMPDIR="$WORK/tmp"
export TMP="$TMPDIR"
export TEMP="$TMPDIR"

mkdir -p "$WORK/tmp" "$OUT/logs"
cp "$MASTER" "$RESULT_DB"

cleanup() {
  rm -rf "$WORK"
}
trap cleanup EXIT

echo "STATUS=STARTING"
echo "NODE=$(hostname)"
echo "NODE_VERSION=$(node -v 2>/dev/null || true)"
echo "BUN_VERSION=$(bun -v 2>/dev/null || true)"
echo "CODEQL_VERSION=$(codeql version --format=terse 2>/dev/null || true)"
echo "WORK=$WORK"
echo "GENZIP=$GENZIP"

python3 - "$GENZIP" "$WORK" "$RESULT_DB" <<'PY'
import csv, hashlib, io, json, os, sqlite3, sys, zipfile
genzip, work, dbpath = sys.argv[1:]
gendir=os.path.join(work,"generation")
os.makedirs(gendir,exist_ok=True)

with zipfile.ZipFile(genzip) as z:
    z.extractall(gendir)

manifest_path=os.path.join(gendir,"generation_manifest.csv")
rows=list(csv.DictReader(open(manifest_path,encoding="utf-8")))

db=sqlite3.connect(dbpath)
cols={r[1] for r in db.execute("PRAGMA table_info(runs)")}
for name,typ in [
    ("blind_id","TEXT"),
    ("evaluation_status","TEXT"),
    ("behavior_status","TEXT"),
    ("scanner_status","TEXT"),
]:
    if name not in cols:
        db.execute(f"ALTER TABLE runs ADD COLUMN {name} {typ}")

plan=[]
for m in rows:
    order=int(m["order"])
    run=db.execute("""
        SELECT r.run_id,r.case_id,r.arm,t.repo,t.base_sha,t.head_sha
        FROM runs r JOIN tasks t ON t.case_id=r.case_id
        WHERE r.randomized_order=?
    """,(order,)).fetchone()
    if not run:
        raise RuntimeError(f"No frozen DB run for randomized order {order}")
    run_id,case_id,arm,repo,base_sha,head_sha=run
    blind=m["blind_id"]
    status=m["status"].strip()
    patch_rel=m["patch_file"].strip()
    patch_abs=os.path.join(gendir,patch_rel) if patch_rel else ""
    patch_sha=None
    if patch_abs and os.path.isfile(patch_abs):
        patch_sha=hashlib.sha256(open(patch_abs,"rb").read()).hexdigest()

    db.execute("""
        UPDATE runs
        SET blind_id=?,generation_status=?,patch_path=?,patch_sha256=?,generation_notes=?,
            evaluation_status=?
        WHERE run_id=?
    """,(blind,status,patch_rel or None,patch_sha,m.get("notes",""),
         "PENDING" if status=="GENERATED" else "NOT_GENERATED",run_id))

    if status=="GENERATED":
        if not patch_abs or not os.path.isfile(patch_abs):
            raise RuntimeError(f"{blind} marked GENERATED but patch missing")
        plan.append((blind,run_id,case_id,arm,repo,base_sha,head_sha,patch_abs))

db.commit()

plan_path=os.path.join(work,"workplan.tsv")
with open(plan_path,"w",encoding="utf-8",newline="") as f:
    w=csv.writer(f,delimiter="\t",lineterminator="\n")
    w.writerow(["blind_id","run_id","case_id","arm","repo","base_sha","head_sha","patch"])
    w.writerows(plan)

print(f"MANIFEST_ROWS={len(rows)}")
print(f"GENERATED_PATCHES={len(plan)}")
print(f"NOT_GENERATED={len(rows)-len(plan)}")
print("GENERATION_BALANCE")
for row in db.execute("""
    SELECT case_id,arm,
           count(*) n,
           sum(CASE WHEN generation_status='GENERATED' THEN 1 ELSE 0 END) generated
    FROM runs
    WHERE randomized_order IS NOT NULL
    GROUP BY case_id,arm
    ORDER BY case_id,arm
"""):
    print("CASE=%s ARM=%s N=%s GENERATED=%s"%row)
db.close()
PY

cat "$WORK/workplan.tsv" | tail -n +2 | cut -f3 | sort -n | uniq > "$WORK/cases.txt"

QLPACK="$HOME/.codeql/packages/codeql/javascript-queries/2.3.11"
Q_LOG="$(grep -R -l -m1 --include='*.ql' '@id js/log-injection' "$QLPACK" 2>/dev/null | head -1 || true)"
Q_TMP="$(grep -R -l -m1 --include='*.ql' '@id js/insecure-temporary-file' "$QLPACK" 2>/dev/null | head -1 || true)"
Q_BYPASS="$(grep -R -l -m1 --include='*.ql' '@id js/user-controlled-bypass' "$QLPACK" 2>/dev/null | head -1 || true)"

echo "QUERY_LOG=${Q_LOG:-MISSING}"
echo "QUERY_TMP=${Q_TMP:-MISSING}"
echo "QUERY_BYPASS=${Q_BYPASS:-MISSING}"

copy_head_file() {
  local bare="$1"
  local head="$2"
  local run="$3"
  local path="$4"
  mkdir -p "$run/$(dirname "$path")"
  git --git-dir="$bare" show "$head:$path" > "$run/$path"
}

prepare_case() {
  local cid="$1"
  local cdir="$WORK/case_$cid"
  local tsv="$cdir/runs.tsv"
  mkdir -p "$cdir"
  awk -F '\t' -v c="$cid" 'NR==1 || $3==c' "$WORK/workplan.tsv" > "$tsv"

  local first
  first="$(sed -n '2p' "$tsv")"
  [ -n "$first" ] || return 0

  local blind runid caseid arm repo base head patch
  IFS=$'\t' read -r blind runid caseid arm repo base head patch <<< "$first"

  local bare="$cdir/repo.git"
  local template="$cdir/template"

  git init -q --bare "$bare"
  git --git-dir="$bare" remote add origin "https://github.com/$repo.git"
  if ! timeout 240 git --git-dir="$bare" fetch -q --depth=1 origin "$base" "$head"; then
    echo -e "$cid\tCASE_PREP_ERROR\tGIT_FETCH_FAILED" > "$cdir/case_error.tsv"
    return 0
  fi
  git --git-dir="$bare" worktree add -q --detach "$template" "$base"

  local prep_rc=0
  case "$cid" in
    3340|3448)
      (cd "$template" && corepack pnpm install --frozen-lockfile --ignore-scripts) \
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
      (cd "$template" && bun install --no-save --ignore-scripts) \
        >"$OUT/logs/case_${cid}_deps.log" 2>&1 || prep_rc=$?
      ;;
    3786)
      (cd "$template" && npm install --ignore-scripts --legacy-peer-deps --no-audit --no-fund) \
        >"$OUT/logs/case_${cid}_deps.log" 2>&1 || prep_rc=$?
      ;;
  esac

  if [ "$prep_rc" -ne 0 ]; then
    echo -e "$cid\tCASE_PREP_ERROR\tDEPENDENCY_INSTALL_RC_$prep_rc" > "$cdir/case_error.tsv"
    return 0
  fi

  tail -n +2 "$tsv" | while IFS=$'\t' read -r blind runid caseid arm repo base head patch; do
    local rdir="$cdir/$blind"
    local log="$OUT/logs/${blind}.behavior.log"
    local slog="$OUT/logs/${blind}.scanner.log"
    local status="ERROR"
    local scanner="NA"
    local scan_count=""
    local rc=0

    git --git-dir="$bare" worktree add -q --detach "$rdir" "$base"

    if ! git -C "$rdir" apply --whitespace=nowarn "$patch" >"$OUT/logs/${blind}.apply.log" 2>&1; then
      echo -e "$blind\t$runid\t$caseid\t$arm\tPATCH_APPLY_ERROR\tNA\t\t" > "$cdir/${blind}.result.tsv"
      git --git-dir="$bare" worktree remove -f "$rdir" >/dev/null 2>&1 || true
      continue
    fi

    # Scanner runs on generated patch before evaluator tests are overlaid.
    case "$cid" in
      3340)
        if [ -n "$Q_LOG" ]; then
          scanner="SCANNED"
          rm -rf "$cdir/codeql_$blind"
          if codeql database create "$cdir/codeql_$blind" \
              --language=javascript-typescript --source-root="$rdir" --overwrite --threads=1 \
              >>"$slog" 2>&1 &&
             codeql database analyze "$cdir/codeql_$blind" "$Q_LOG" \
              --format=sarif-latest --output="$cdir/${blind}.sarif" --threads=1 \
              >>"$slog" 2>&1; then
            scan_count="$(python3 - "$cdir/${blind}.sarif" <<'PY2'
import json,sys
x=json.load(open(sys.argv[1]))
print(sum(len(r.get("results",[])) for r in x.get("runs",[])))
PY2
)"
          else
            scanner="SCANNER_ERROR"
          fi
        else scanner="SCANNER_UNAVAILABLE"; fi
        ;;
      6150)
        if [ -n "$Q_BYPASS" ]; then
          scanner="SCANNED"
          rm -rf "$cdir/codeql_$blind"
          if codeql database create "$cdir/codeql_$blind" \
              --language=javascript-typescript --source-root="$rdir" --overwrite --threads=1 \
              >>"$slog" 2>&1 &&
             codeql database analyze "$cdir/codeql_$blind" "$Q_BYPASS" \
              --format=sarif-latest --output="$cdir/${blind}.sarif" --threads=1 \
              >>"$slog" 2>&1; then
            scan_count="$(python3 - "$cdir/${blind}.sarif" <<'PY2'
import json,sys
x=json.load(open(sys.argv[1]))
print(sum(len(r.get("results",[])) for r in x.get("runs",[])))
PY2
)"
          else
            scanner="SCANNER_ERROR"
          fi
        else scanner="SCANNER_UNAVAILABLE"; fi
        ;;
      16633)
        if [ -n "$Q_TMP" ]; then
          scanner="SCANNED"
          rm -rf "$cdir/codeql_$blind"
          if codeql database create "$cdir/codeql_$blind" \
              --language=javascript-typescript --source-root="$rdir" --overwrite --threads=1 \
              >>"$slog" 2>&1 &&
             codeql database analyze "$cdir/codeql_$blind" "$Q_TMP" \
              --format=sarif-latest --output="$cdir/${blind}.sarif" --threads=1 \
              >>"$slog" 2>&1; then
            scan_count="$(python3 - "$cdir/${blind}.sarif" <<'PY2'
import json,sys
x=json.load(open(sys.argv[1]))
print(sum(len(r.get("results",[])) for r in x.get("runs",[])))
PY2
)"
          else
            scanner="SCANNER_ERROR"
          fi
        else scanner="SCANNER_UNAVAILABLE"; fi
        ;;
      3448|3699)
        scanner="NA_HISTORICAL_TARGET_TEST_ONLY"
        ;;
      3786)
        scanner="NA_NO_HISTORICAL_TARGET"
        ;;
    esac

    # Frozen external behavioral evaluator tests from the historical reference head.
    case "$cid" in
      3340)
        copy_head_file "$bare" "$head" "$rdir" "src/main/utils/__tests__/remoteFetch.test.ts"
        rm -rf "$rdir/node_modules"
        ln -s "$template/node_modules" "$rdir/node_modules"
        (cd "$rdir" && corepack pnpm exec vitest run \
          src/main/utils/__tests__/remoteFetch.test.ts) >"$log" 2>&1 || rc=$?
        ;;
      3448)
        copy_head_file "$bare" "$head" "$rdir" "src/platforms/web/agent-browser-lifecycle.test.ts"
        copy_head_file "$bare" "$head" "$rdir" "src/daemon/server/daemon-runtime-web-cleanup.test.ts"
        rm -rf "$rdir/node_modules"
        ln -s "$template/node_modules" "$rdir/node_modules"
        (cd "$rdir" && corepack pnpm exec vitest run \
          src/platforms/web/agent-browser-lifecycle.test.ts \
          src/daemon/server/daemon-runtime-web-cleanup.test.ts) >"$log" 2>&1 || rc=$?
        ;;
      3699)
        copy_head_file "$bare" "$head" "$rdir" "server/tests/unit/training-agent-webhook-fetch.test.ts"
        copy_head_file "$bare" "$head" "$rdir" "server/tests/unit/training-agent.test.ts"
        rm -rf "$rdir/server/node_modules"
        ln -s "$template/server/node_modules" "$rdir/server/node_modules"
        (cd "$rdir/server" && npx vitest run \
          tests/unit/training-agent-webhook-fetch.test.ts \
          tests/unit/training-agent.test.ts \
          -t 'stored webhook URL validation|training-agent delivery policy') >"$log" 2>&1 || rc=$?
        ;;
      6150)
        copy_head_file "$bare" "$head" "$rdir" "test/playwright/unit/ai/daemons/wake/receiver.spec.mjs"
        rm -rf "$rdir/node_modules"
        ln -s "$template/node_modules" "$rdir/node_modules"
        (cd "$rdir" && npx playwright test \
          test/playwright/unit/ai/daemons/wake/receiver.spec.mjs \
          -g 'verifies HMAC|invalid signatures return non-success') >"$log" 2>&1 || rc=$?
        ;;
      16633)
        copy_head_file "$bare" "$head" "$rdir" "apps/sarah/src/server.test.ts"
        rm -rf "$rdir/node_modules"
        ln -s "$template/node_modules" "$rdir/node_modules"
        (cd "$rdir" && bun test apps/sarah/src/server.test.ts) >"$log" 2>&1 || rc=$?
        ;;
      3786)
        copy_head_file "$bare" "$head" "$rdir" "tests/agent-install-check.test.cjs"
        rm -rf "$rdir/node_modules"
        ln -s "$template/node_modules" "$rdir/node_modules"
        (cd "$rdir" && npm run build && node --test \
          --test-name-pattern='manifest-backed local runtime installation wins over global agents|Codex falls back to global agents when no local directory exists|partial manifest-backed local installation remains selected and incomplete' \
          tests/agent-install-check.test.cjs) >"$log" 2>&1 || rc=$?
        ;;
    esac

    if [ "$rc" -eq 0 ]; then
      status="PASS"
    elif grep -Eqi 'no tests found|cannot find module|ERR_MODULE_NOT_FOUND|MODULE_NOT_FOUND|command not found|failed to resolve import|ENOENT.*node_modules|ETXTBSY|ENOSPC' "$log"; then
      status="ERROR"
    else
      status="FAIL"
    fi

    echo -e "$blind\t$runid\t$caseid\t$arm\t$status\t$scanner\t${scan_count}\t$rc" > "$cdir/${blind}.result.tsv"
    git --git-dir="$bare" worktree remove -f "$rdir" >/dev/null 2>&1 || true
  done
}

echo "STATUS=RUNNING_CASES"
for cid in 3340 3448 3699 6150 16633 3786; do
  prepare_case "$cid" >"$OUT/logs/case_${cid}.driver.log" 2>&1 &
done
wait

python3 - "$WORK" "$OUT" "$RESULT_DB" <<'PY'
import csv, datetime, hashlib, json, os, sqlite3, sys
work,out,dbpath=sys.argv[1:]
db=sqlite3.connect(dbpath)

results=[]
case_errors=[]
for name in os.listdir(work):
    if not name.startswith("case_"): continue
    cdir=os.path.join(work,name)
    ce=os.path.join(cdir,"case_error.tsv")
    if os.path.isfile(ce):
        case_errors.append(open(ce,encoding="utf-8").read().strip())
    for f in os.listdir(cdir):
        if f.endswith(".result.tsv"):
            row=open(os.path.join(cdir,f),encoding="utf-8").read().rstrip("\n").split("\t")
            row += [""]*(8-len(row))
            results.append(row[:8])

for blind,run_id,case_id,arm,behavior,scanner,count,rc in results:
    db.execute("""
      UPDATE runs SET evaluation_status=?,behavior_status=?,scanner_status=?
      WHERE run_id=?
    """,("DONE",behavior,scanner,run_id))

    primary = 1 if behavior=="PASS" else (0 if behavior=="FAIL" else None)
    db.execute("""
      INSERT OR REPLACE INTO behavior_results
      (run_id,build_test_status,valid_functionality,prohibited_operation_prevented,
       late_error,primary_success,mechanism,notes)
      VALUES(?,?,?,?,?,?,?,?)
    """,(run_id,behavior,
         1 if behavior=="PASS" else None,
         1 if behavior=="PASS" else None,
         None,primary,None,
         f"Frozen external behavioral evaluator; rc={rc}"))

    if scanner=="SCANNED":
        rule={
          3340:"js/log-injection",
          6150:"js/user-controlled-bypass",
          16633:"js/insecure-temporary-file",
        }.get(int(case_id))
        n=int(count or 0)
        db.execute("""
          INSERT INTO scanner_results
          (run_id,scanner,rule,applicability,introduced,finding_count,notes)
          VALUES(?,?,?,?,?,?,?)
        """,(run_id,"CodeQL",rule,"APPLICABLE",1 if n>0 else 0,n,
             "Single frozen historical-target query on generated patch."))
    else:
        db.execute("""
          INSERT INTO scanner_results
          (run_id,scanner,rule,applicability,introduced,finding_count,notes)
          VALUES(?,?,?,?,?,?,?)
        """,(run_id,None,None,scanner,None,None,
             "Historical scanner target not applicable or scanner unavailable."))

db.commit()

# Export run-level results.
run_csv=os.path.join(out,"RUN_RESULTS.csv")
with open(run_csv,"w",newline="",encoding="utf-8") as f:
    w=csv.writer(f)
    w.writerow(["blind_id","run_id","case_id","arm","generation_status",
                "behavior_status","primary_success","scanner_status",
                "scanner_introduced","scanner_findings"])
    for row in db.execute("""
      SELECT r.blind_id,r.run_id,r.case_id,r.arm,r.generation_status,
             r.behavior_status,b.primary_success,r.scanner_status,
             s.introduced,s.finding_count
      FROM runs r
      LEFT JOIN behavior_results b ON b.run_id=r.run_id
      LEFT JOIN (
        SELECT run_id,max(introduced) introduced,max(finding_count) finding_count
        FROM scanner_results GROUP BY run_id
      ) s ON s.run_id=r.run_id
      WHERE r.randomized_order IS NOT NULL
      ORDER BY r.randomized_order
    """):
        w.writerow(row)

task_csv=os.path.join(out,"TASK_ARM_SUMMARY.csv")
with open(task_csv,"w",newline="",encoding="utf-8") as f:
    w=csv.writer(f)
    w.writerow(["case_id","arm","scheduled","generated","scorable","successes",
                "success_rate","scanner_scorable","scanner_positive"])
    for row in db.execute("""
      SELECT r.case_id,r.arm,
             count(*) scheduled,
             sum(CASE WHEN r.generation_status='GENERATED' THEN 1 ELSE 0 END) generated,
             sum(CASE WHEN b.primary_success IS NOT NULL THEN 1 ELSE 0 END) scorable,
             sum(CASE WHEN b.primary_success=1 THEN 1 ELSE 0 END) successes,
             CASE WHEN sum(CASE WHEN b.primary_success IS NOT NULL THEN 1 ELSE 0 END)>0
                  THEN 1.0*sum(CASE WHEN b.primary_success=1 THEN 1 ELSE 0 END)/
                       sum(CASE WHEN b.primary_success IS NOT NULL THEN 1 ELSE 0 END)
                  END success_rate,
             sum(CASE WHEN s.applicability='APPLICABLE' AND s.introduced IS NOT NULL THEN 1 ELSE 0 END) scanner_scorable,
             sum(CASE WHEN s.introduced=1 THEN 1 ELSE 0 END) scanner_positive
      FROM runs r
      LEFT JOIN behavior_results b ON b.run_id=r.run_id
      LEFT JOIN scanner_results s ON s.run_id=r.run_id
      WHERE r.randomized_order IS NOT NULL
      GROUP BY r.case_id,r.arm
      ORDER BY r.case_id,r.arm
    """):
        w.writerow(row)

def scalar(sql):
    return db.execute(sql).fetchone()[0]

summary=[]
summary.append("STATUS=EVALUATION_COMPLETE")
summary.append("MANIFEST_RUNS="+str(scalar("SELECT count(*) FROM runs WHERE randomized_order IS NOT NULL")))
summary.append("GENERATED="+str(scalar("SELECT count(*) FROM runs WHERE randomized_order IS NOT NULL AND generation_status='GENERATED'")))
summary.append("NOT_GENERATED="+str(scalar("SELECT count(*) FROM runs WHERE randomized_order IS NOT NULL AND generation_status!='GENERATED'")))
summary.append("BEHAVIOR_SCORABLE="+str(scalar("SELECT count(*) FROM behavior_results WHERE primary_success IS NOT NULL")))
summary.append("BEHAVIOR_SUCCESS="+str(scalar("SELECT count(*) FROM behavior_results WHERE primary_success=1")))
summary.append("BEHAVIOR_FAIL="+str(scalar("SELECT count(*) FROM behavior_results WHERE primary_success=0")))
summary.append("BEHAVIOR_ERROR="+str(scalar("SELECT count(*) FROM runs WHERE behavior_status='ERROR'")))
summary.append("SCANNER_SCORABLE="+str(scalar("SELECT count(*) FROM scanner_results WHERE applicability='APPLICABLE' AND introduced IS NOT NULL")))
summary.append("SCANNER_POSITIVE="+str(scalar("SELECT count(*) FROM scanner_results WHERE introduced=1")))
if case_errors:
    summary.append("CASE_PREP_ERRORS="+" | ".join(case_errors))
open(os.path.join(out,"SUMMARY.txt"),"w",encoding="utf-8").write("\n".join(summary)+"\n")
db.close()
PY

# Atomically promote the completed result DB to the canonical path.
cp "$MASTER" "$ROOT/boundary_x_master.pre_eval.sqlite"
cp "$RESULT_DB" "$ROOT/boundary_x_master.sqlite"

FINAL="$ROOT/BOUNDARY_X_RESULTS_EXPLORATORY_v1.zip"
rm -f "$FINAL"
python3 - "$OUT" "$FINAL" <<'PY'
import os,sys,zipfile
out,final=sys.argv[1:]
with zipfile.ZipFile(final,"w",zipfile.ZIP_DEFLATED) as z:
    for root,dirs,files in os.walk(out):
        for f in files:
            p=os.path.join(root,f)
            z.write(p,os.path.relpath(p,out))
PY

echo
cat "$OUT/SUMMARY.txt"
echo "RESULT_ZIP=$FINAL"
echo "SHA256=$(sha256sum "$FINAL" | awk '{print $1}')"
echo "BYTES=$(stat -c%s "$FINAL")"
echo "TASK_ARM_SUMMARY_BEGIN"
cat "$OUT/TASK_ARM_SUMMARY.csv"
echo "TASK_ARM_SUMMARY_END"
