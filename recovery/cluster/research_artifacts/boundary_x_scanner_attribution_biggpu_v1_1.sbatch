#!/bin/bash
#SBATCH --job-name=bx_scan_attr
#SBATCH --partition=biggpu
#SBATCH --time=03:00:00
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/bx_scanner_attr.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/bx_scanner_attr.err

set -euo pipefail

ROOT="$HOME/research_artifacts"
MASTER="$ROOT/boundary_x_master.sqlite"
GENZIP="$ROOT/BOUNDARY_X_GENERATIONS_GPT56SOL_v1.zip"
WORK="/var/tmp/bx_scan_attr_${SLURM_JOB_ID}"
OUT="$ROOT/boundary_x_scanner_attr_${SLURM_JOB_ID}"

CODEQL="$HOME/tools/codeql/codeql"
QLROOT="$HOME/.codeql/packages/codeql/javascript-queries/2.3.11"
Q3340="$QLROOT/experimental/heuristics/ql/src/Security/CWE-117/LogInjection.ql"
Q6150="$QLROOT/experimental/heuristics/ql/src/Security/CWE-807/ConditionalBypass.ql"
Q16633="$QLROOT/Security/CWE-377/InsecureTemporaryFile.ql"

mkdir -p "$WORK/gen" "$OUT/logs" "$OUT/sarif"
trap 'rm -rf "$WORK"' EXIT

echo "STATUS=STARTING"
echo "NODE=$(hostname)"
echo "CODEQL=$("$CODEQL" version --format=terse)"
echo "WORK=$WORK"

python3 - "$GENZIP" "$WORK/gen" "$MASTER" "$WORK/plan.tsv" <<'PY'
import csv, os, sqlite3, sys, zipfile
zpath,gdir,dbpath,out=sys.argv[1:]
with zipfile.ZipFile(zpath) as z:
    z.extractall(gdir)
manifest={r["blind_id"]:r for r in csv.DictReader(open(os.path.join(gdir,"generation_manifest.csv"),encoding="utf-8"))}
db=sqlite3.connect(dbpath)
rows=[]
for blind,run_id,case_id,arm,repo,base_sha in db.execute("""
 SELECT r.blind_id,r.run_id,r.case_id,r.arm,t.repo,t.base_sha
 FROM runs r JOIN tasks t ON t.case_id=r.case_id
 WHERE r.generation_status='GENERATED'
   AND r.case_id IN (3340,6150,16633)
 ORDER BY r.case_id,r.blind_id
"""):
    m=manifest.get(blind)
    if not m or m["status"]!="GENERATED":
        continue
    patch=os.path.join(gdir,m["patch_file"])
    rows.append((blind,run_id,case_id,arm,repo,base_sha,patch))
with open(out,"w",newline="",encoding="utf-8") as f:
    w=csv.writer(f,delimiter="\t",lineterminator="\n")
    w.writerow(["blind_id","run_id","case_id","arm","repo","base_sha","patch"])
    w.writerows(rows)
print("SCANNER_RUNS="+str(len(rows)))
for cid in (3340,6150,16633):
    s=[r for r in rows if r[2]==cid]
    print(f"CASE={cid} RUNS={len(s)}")
PY

scan_case() {
  local cid="$1"
  local query="$2"
  local cdir="$WORK/case_$cid"
  mkdir -p "$cdir"
  awk -F '\t' -v c="$cid" 'NR==1 || $3==c' "$WORK/plan.tsv" > "$cdir/plan.tsv"

  local first
  first="$(sed -n '2p' "$cdir/plan.tsv")"
  [ -n "$first" ] || return 0

  local blind runid caseid arm repo base patch
  IFS=$'\t' read -r blind runid caseid arm repo base patch <<< "$first"

  local bare="$cdir/repo.git"
  git init -q --bare "$bare"
  git --git-dir="$bare" remote add origin "https://github.com/$repo.git"
  timeout 300 git --git-dir="$bare" fetch -q --depth=1 origin "$base"

  local basewt="$cdir/base"
  git --git-dir="$bare" worktree add -q --detach "$basewt" "$base"

  echo "CASE=$cid BASE_SCAN_START"
  "$CODEQL" database create "$cdir/base-db" \
    --language=javascript-typescript \
    --source-root="$basewt" \
    --threads=4 \
    --overwrite >"$OUT/logs/${cid}_base_create.log" 2>&1

  "$CODEQL" database analyze "$cdir/base-db" "$query" \
    --format=sarif-latest \
    --output="$OUT/sarif/${cid}_BASE.sarif" \
    --threads=4 >"$OUT/logs/${cid}_base_analyze.log" 2>&1

  tail -n +2 "$cdir/plan.tsv" | while IFS=$'\t' read -r blind runid caseid arm repo base patch; do
    local wt="$cdir/$blind"
    local db="$cdir/db_$blind"
    echo "CASE=$cid RUN=$blind SCAN_START"
    git --git-dir="$bare" worktree add -q --detach "$wt" "$base"
    if ! git -C "$wt" apply --whitespace=nowarn "$patch" >"$OUT/logs/${blind}_apply.log" 2>&1; then
      echo -e "$blind\t$runid\t$caseid\t$arm\tPATCH_APPLY_ERROR" > "$cdir/${blind}.error"
      git --git-dir="$bare" worktree remove -f "$wt" >/dev/null 2>&1 || true
      continue
    fi

    if "$CODEQL" database create "$db" \
       --language=javascript-typescript \
       --source-root="$wt" \
       --threads=2 \
       --overwrite >"$OUT/logs/${blind}_create.log" 2>&1 &&
       "$CODEQL" database analyze "$db" "$query" \
       --format=sarif-latest \
       --output="$OUT/sarif/${blind}.sarif" \
       --threads=2 >"$OUT/logs/${blind}_analyze.log" 2>&1; then
      echo "CASE=$cid RUN=$blind SCAN_DONE"
    else
      echo -e "$blind\t$runid\t$caseid\t$arm\tSCANNER_ERROR" > "$cdir/${blind}.error"
    fi

    rm -rf "$db"
    git --git-dir="$bare" worktree remove -f "$wt" >/dev/null 2>&1 || true
  done
}

scan_case 3340 "$Q3340" >"$OUT/logs/case_3340_driver.log" 2>&1 &
P1=$!
scan_case 6150 "$Q6150" >"$OUT/logs/case_6150_driver.log" 2>&1 &
P2=$!
scan_case 16633 "$Q16633" >"$OUT/logs/case_16633_driver.log" 2>&1 &
P3=$!
wait "$P1" "$P2" "$P3"

python3 - "$WORK/plan.tsv" "$OUT" <<'PY'
import csv, json, os, re, sys
plan,out=sys.argv[1:]
rows=list(csv.DictReader(open(plan,encoding="utf-8"),delimiter="\t"))

def added_lines(patch_path):
    outmap={}
    cur=None
    new_line=None
    hunk=re.compile(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@')
    with open(patch_path,encoding="utf-8",errors="replace") as f:
        for line in f:
            if line.startswith('+++ b/'):
                cur=line[6:].rstrip('\n')
                outmap.setdefault(cur,set())
                continue
            m=hunk.match(line)
            if m:
                new_line=int(m.group(1))
                continue
            if cur is None or new_line is None:
                continue
            if line.startswith('+') and not line.startswith('+++'):
                outmap[cur].add(new_line)
                new_line+=1
            elif line.startswith('-') and not line.startswith('---'):
                pass
            elif line.startswith('\\'):
                pass
            else:
                new_line+=1
    return outmap

def sarif_locations(path):
    if not os.path.isfile(path):
        return [],0
    x=json.load(open(path,encoding="utf-8"))
    findings=[]
    total=0
    for run in x.get("runs",[]):
        for r in run.get("results",[]):
            total+=1
            locs=[]
            def take(loc):
                p=loc.get("physicalLocation",{})
                art=p.get("artifactLocation",{}).get("uri")
                reg=p.get("region",{})
                if art and reg.get("startLine"):
                    locs.append((art.lstrip("./"),int(reg["startLine"])))
            for loc in r.get("locations",[]): take(loc)
            for cf in r.get("codeFlows",[]):
                for tf in cf.get("threadFlows",[]):
                    for tfl in tf.get("locations",[]):
                        take(tfl.get("location",{}))
            findings.append(locs)
    return findings,total

base={}
for cid in (3340,6150,16633):
    _,n=sarif_locations(os.path.join(out,"sarif",f"{cid}_BASE.sarif"))
    base[cid]=n

result=[]
for r in rows:
    blind=r["blind_id"]; cid=int(r["case_id"])
    sp=os.path.join(out,"sarif",f"{blind}.sarif")
    if not os.path.isfile(sp):
        result.append({**r,"status":"SCANNER_ERROR","base_findings":base.get(cid),
                       "patch_findings":None,"attributable_findings":None,"introduced":None})
        continue
    adds=added_lines(r["patch"])
    findings,total=sarif_locations(sp)
    attrib=0
    for locs in findings:
        if any(line in adds.get(file,set()) for file,line in locs):
            attrib+=1
    result.append({**r,"status":"OK","base_findings":base.get(cid),
                   "patch_findings":total,"attributable_findings":attrib,
                   "introduced":1 if attrib>0 else 0})

csvpath=os.path.join(out,"PATCH_ATTRIBUTABLE_SCANNER_RESULTS.csv")
with open(csvpath,"w",newline="",encoding="utf-8") as f:
    fields=["blind_id","run_id","case_id","arm","status","base_findings",
            "patch_findings","attributable_findings","introduced"]
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
    for r in result: w.writerow({k:r.get(k) for k in fields})

summary=[]
summary.append("STATUS=SCANNER_ATTRIBUTION_COMPLETE")
summary.append(f"RUNS={len(result)}")
summary.append(f"SCORABLE={sum(r['status']=='OK' for r in result)}")
summary.append(f"ERRORS={sum(r['status']!='OK' for r in result)}")
summary.append(f"ATTRIBUTABLE_POSITIVE={sum(r.get('introduced')==1 for r in result)}")
summary.append("BY_CASE_ARM")
keys=sorted(set((r["case_id"],r["arm"]) for r in result),key=lambda x:(int(x[0]),x[1]))
for cid,arm in keys:
    s=[r for r in result if r["case_id"]==cid and r["arm"]==arm and r["status"]=="OK"]
    pos=sum(r["introduced"]==1 for r in s)
    summary.append(f"CASE={cid} ARM={arm} N={len(s)} POS={pos}")
open(os.path.join(out,"SUMMARY.txt"),"w",encoding="utf-8").write("\n".join(summary)+"\n")
print("\n".join(summary))
PY

FINAL="$ROOT/BOUNDARY_X_SCANNER_ATTRIBUTION_v1.zip"
rm -f "$FINAL"
python3 - "$OUT" "$FINAL" <<'PY'
import os,sys,zipfile
out,final=sys.argv[1:]
with zipfile.ZipFile(final,"w",zipfile.ZIP_DEFLATED) as z:
    for fn in ["PATCH_ATTRIBUTABLE_SCANNER_RESULTS.csv","SUMMARY.txt"]:
        z.write(os.path.join(out,fn),fn)
    for root,dirs,files in os.walk(os.path.join(out,"sarif")):
        for f in files:
            p=os.path.join(root,f)
            z.write(p,os.path.relpath(p,out))
PY

cat "$OUT/SUMMARY.txt"
echo "RESULT_ZIP=$FINAL"
echo "SHA256=$(sha256sum "$FINAL" | awk '{print $1}')"
echo "BYTES=$(stat -c%s "$FINAL")"
