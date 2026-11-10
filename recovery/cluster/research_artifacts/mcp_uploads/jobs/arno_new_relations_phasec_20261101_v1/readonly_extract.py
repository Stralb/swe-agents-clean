#!/usr/bin/env python3
"""Read-only historical O/W/P patch and SARIF inspection. Never writes source."""
from pathlib import Path
import sqlite3,hashlib,zlib,json,csv,re,collections,statistics
ROOT=Path.home()/"research_artifacts"
DB=ROOT/"mcp_uploads/jobs/arno_unified_evidence_20261031_v1/output/ARNO_UNIFIED_FULL_EVIDENCE_DB.sqlite"
OUT=ROOT/"mcp_uploads/jobs/arno_new_relations_phasec_20261101_v1/results"
OUT.mkdir(parents=True,exist_ok=True)
names=["HISTORICAL_OWP_PATCH_FEATURES.csv","HISTORICAL_OWP_FILE_OVERLAP.csv","HISTORICAL_OWP_SARIF_RULE_COUNTS.csv","READONLY_EXTRACTION_QA.json"]
if any((OUT/n).exists() for n in names):raise FileExistsError("No output overwrite")
c=sqlite3.connect(f"file:{DB}?mode=ro&immutable=1",uri=True)
c.execute("PRAGMA query_only=ON")
p=[];bycase={};scan=[]
query="""SELECT b.case_id,b.arm,b.original_filename,b.patch_sha256,b.original_patch_bytes,b.patch_zlib,
s.new_strong_count,s.target_new_strong,s.source_snapshot_type,s.functional_status
FROM arno_rq3_owp14_verified_patch_bytes b JOIN arno_rq3_owp14_run_scans s
ON s.case_id=b.case_id AND s.arm=b.arm ORDER BY b.case_id,b.arm"""
for case,arm,name,sha,size,blob,new,target,source,func in c.execute(query):
 raw=zlib.decompress(blob)
 if len(raw)!=size or hashlib.sha256(raw).hexdigest()!=sha:raise RuntimeError(f"Patch hash or bytes mismatch: {case}/{arm}")
 text=raw.decode("utf-8",errors="replace")
 paths=[];added=removed=hunks=0
 for line in text.splitlines():
  if line.startswith("diff --git a/"):
   m=re.match(r"diff --git a/(.*?) b/(.*)",line)
   if m:paths.append(m.group(2))
  elif line.startswith("@@"):hunks+=1
  elif line.startswith("+") and not line.startswith("+++"):added+=1
  elif line.startswith("-") and not line.startswith("---"):removed+=1
 paths=sorted(set(paths))
 tests=sum(bool(re.search(r"(^|/)(__tests__|tests?|fixtures?|mocks?)(/|\.)|\.(test|spec)\.[cm]?[jt]sx?$",x,re.I)) for x in paths)
 deps=sum("lock" in Path(x).name.lower() or Path(x).name.lower() in ("package.json","requirements.txt","pyproject.toml","pom.xml") for x in paths)
 row=dict(case_id=case,arm=arm,patch_sha256=sha,patch_bytes=size,file_count=len(paths),files=";".join(paths),added_diff_lines=added,removed_diff_lines=removed,hunk_count=hunks,test_file_count=tests,dependency_file_count=deps,new_warning_count_recorded=new,historical_target_count_recorded=target,source_snapshot_type=source,functional_status=func)
 p.append(row);bycase.setdefault(case,{})[arm]=row
if len(p)!=40:raise RuntimeError(f"Expected 40, got {len(p)}")
def writecsv(name,rows,cols=None):
 with (OUT/name).open("w",newline="") as f:
  w=csv.DictWriter(f,fieldnames=cols or list(rows[0]));w.writeheader();w.writerows(rows)
writecsv(names[0],p)
cmp=[]
for case,arms in sorted(bycase.items()):
 if not all(arm in arms for arm in ("O","W","P")):continue
 a=arms["O"];sa=set(a["files"].split(";")) if a["files"] else set()
 for arm in ("W","P"):
  b=arms[arm];sb=set(b["files"].split(";")) if b["files"] else set()
  shared=len(sa&sb);union=len(sa|sb)
  cmp.append(dict(case_id=case,arm=arm,source_snapshot_type=a["source_snapshot_type"],O_files=len(sa),intervention_files=len(sb),shared_files=shared,file_jaccard=round(shared/union,6) if union else 1,
      intervention_only_files=len(sb-sa),O_only_files=len(sa-sb),O_added_lines=a["added_diff_lines"],intervention_added_lines=b["added_diff_lines"],
      O_removed_lines=a["removed_diff_lines"],intervention_removed_lines=b["removed_diff_lines"],O_test_files=a["test_file_count"],intervention_test_files=b["test_file_count"],
      O_dependency_files=a["dependency_file_count"],intervention_dependency_files=b["dependency_file_count"],O_new_warnings=a["new_warning_count_recorded"],
      intervention_new_warnings=b["new_warning_count_recorded"],O_target=a["historical_target_count_recorded"],intervention_target=b["historical_target_count_recorded"]))
if len(cmp)!=24:raise RuntimeError(f"Expected 24 comparisons, got {len(cmp)}")
writecsv(names[1],cmp)
for case,arm,path,blob in c.execute("SELECT case_id,arm,source_path,source_zlib FROM arno_rq3_owp14_original_artifacts WHERE source_role='CODEQL_AFTER_SARIF' ORDER BY case_id,arm"):
 try:
  obj=json.loads(zlib.decompress(blob))
  counts=collections.Counter(str(x.get("ruleId","UNSPECIFIED")) for r in obj.get("runs",[]) for x in r.get("results",[]))
  for rule,n in sorted(counts.items()):scan.append(dict(case_id=case,arm=arm,after_sarif_rule=rule,after_count=n,error=""))
  if not counts:scan.append(dict(case_id=case,arm=arm,after_sarif_rule="NONE",after_count=0,error=""))
 except Exception as e:scan.append(dict(case_id=case,arm=arm,after_sarif_rule="",after_count=0,error=str(e)))
writecsv(names[2],scan,["case_id","arm","after_sarif_rule","after_count","error"])
qa=dict(status="PASS",source=str(DB),source_open_mode="immutable_readonly",source_changes=0,verified_patch_hashes=len(p),historical_complete_cases=12,matched_comparisons=len(cmp),
    sarif_rule_entries=len(scan),sarif_parse_errors=sum(bool(r["error"]) for r in scan),
    warning_note="after SARIF rules are all after results; do NOT equate with introduced warnings",
    arms={arm:{"n":sum(x["arm"]==arm for x in p),"new_reported_all_available":sum(x["new_warning_count_recorded"] for x in p if x["arm"]==arm)} for arm in ("O","W","P")},
    paired={arm:{"zero_shared_file_pairs":sum(x["shared_files"]==0 for x in cmp if x["arm"]==arm),
                 "median_file_jaccard":statistics.median(x["file_jaccard"] for x in cmp if x["arm"]==arm),
                 "intervention_only_file_pairs":sum(x["intervention_only_files"]>0 for x in cmp if x["arm"]==arm),
                 "smaller_added_lines_pairs":sum(x["intervention_added_lines"]<x["O_added_lines"] for x in cmp if x["arm"]==arm)} for arm in ("W","P")})
(OUT/names[3]).write_text(json.dumps(qa,indent=2))
print(json.dumps(qa,indent=2),flush=True)
