#!/usr/bin/env python3
"""Case 03581 R1 minimal-context post-generation static evaluation; isolated, non-destructive."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import ast,hashlib,json,os,stat,subprocess,tempfile,zipfile,shutil,time,sys
R=Path.home()/"research_artifacts"
ROOT=R/"mcp_uploads/jobs/arno_minctx_03581_v6_scan_20261030_r1"
OUT=ROOT/"results_v2"
SOURCE=R/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2/run_zips/RPL7_RUN_887FBD20CB75.zip"
BASE=R/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results/CASE_03581"
P1=R/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results/CASE_03581/RPL7_RUN_887FBD20CB75"
CODEQL=Path.home()/"tools/codeql/codeql"
SUITE="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
EXPECTED_PATCH_SHA="21f0dbfe62ee306c59eb1b9c473b70664cb6ba7d879782ccd8cc682a46498ae4"
EXPECTED_RECEIPT_SHA="b7667d105f80ede691ed5f23b9e9bf1d12687b9b85affa3c22c80c54aa5891be"
EXPECTED_SOURCE_SHA="d9e3951a75d9a0b53e442523d5bd517df1f4e353e7977efec2002fc4a0fe9142"
EXPECTED_SOURCE_TREE="bda7536fe4761882898b1f3e5a968b1c9777f3f1355f72eac850bbbd3d5964ca"
def sha(b):return hashlib.sha256(b).hexdigest()
def file_sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for chunk in iter(lambda:f.read(1048576),b""):h.update(chunk)
 return h.hexdigest()
def part(p):
 s=p.read_text(encoding="utf-8")
 assert s.startswith("DATA = ")
 v=ast.literal_eval(s[len("DATA = "):].strip())
 assert isinstance(v,str)
 return v
def signals(p):
 obj=json.loads(p.read_text())
 v=Counter(); details={}
 for run in obj.get("runs",[]):
  for result in run.get("results",[]):
   loc=result.get("locations",[])
   ph=loc[0].get("physicalLocation",{}) if loc else {}
   rule=result.get("ruleId","")
   path=ph.get("artifactLocation",{}).get("uri","").replace("\\","/")
   msg=" ".join((result.get("message",{}).get("text") or "").split())
   key=(rule,path,msg)
   v[key]+=1
   details.setdefault(key,{"rule":rule,"file":path,"message":msg,"line_sample":ph.get("region",{}).get("startLine")})
 return v,details
def entries(x, info):
 return [{**info.get(key,{"rule":key[0],"file":key[1],"message":key[2]}),"count":n} for key,n in sorted(x.items())]
def shell(args,log,cwd=None,timeout=1200):
 start=time.monotonic()
 with log.open("x",encoding="utf-8") as f:
  try:
   p=subprocess.run([str(x) for x in args],cwd=cwd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
   exit_code=p.returncode
  except subprocess.TimeoutExpired:
   exit_code=124
 return {"exit":exit_code,"seconds":round(time.monotonic()-start,2),"log":log.name}
record={"run_id":"MINCTX_03581_R1","status":"STARTED","started_utc":datetime.now(timezone.utc).isoformat(),"suite":SUITE,
        "case":"03581","context_condition":"NEUTRAL_CONTRACT_MINIMAL_REPOSITORY_CONTEXT",
        "functional_status":"NOT_VERIFIED"}
OUT.mkdir(parents=True,exist_ok=False)
try:
 assert CODEQL.is_file()
 patch_text="".join(part(ROOT/("patch_%02d.py"%i)) for i in range(4))
 assert len(patch_text)==20019,len(patch_text)
 patch=(patch_text[:10632]+"\n"+patch_text[10632:]+"\n").encode("utf-8")
 assert sha(patch)==EXPECTED_PATCH_SHA,("patch integrity",sha(patch),len(patch))
 receipt=(part(ROOT/"receipt_data.py")+"\n").encode("utf-8")
 assert sha(receipt)==EXPECTED_RECEIPT_SHA,("receipt integrity",sha(receipt),len(receipt))
 obj=json.loads(receipt)
 assert obj["run_id"]=="MINCTX_03581_R1"
 assert file_sha(SOURCE)==EXPECTED_SOURCE_SHA
 baseline_meta=json.loads((BASE/"RESULT.json").read_text())
 p1_meta=json.loads((P1/"RESULT.json").read_text())
 assert baseline_meta["source_kind"]=="FULL_FROZEN_SNAPSHOT"
 assert baseline_meta["sanitized_repo_sha256"]==EXPECTED_SOURCE_TREE
 assert baseline_meta["result_count"]==82
 assert p1_meta["status"]=="CODEQL_SCAN_COMPLETE"
 assert file_sha(BASE/"baseline.sarif")==baseline_meta["sarif_sha256"]
 assert file_sha(P1/"after.sarif")==p1_meta["after_sarif_sha256"]
 (OUT/"PATCH_MINCTX_03581_R1.patch").write_bytes(patch)
 (OUT/"RECEIPT_MINCTX_03581_R1.json").write_bytes(receipt)
 record.update(patch_sha256=sha(patch),receipt_sha256=sha(receipt),source_zip_sha256=EXPECTED_SOURCE_SHA,
              source_kind=baseline_meta["source_kind"],source_repo_tree_sha256=EXPECTED_SOURCE_TREE)
 with tempfile.TemporaryDirectory(prefix="arno_03581_minctx_") as td:
  repo=Path(td)/"repo";repo.mkdir()
  with zipfile.ZipFile(SOURCE) as z:
   assert z.testzip() is None
   count=0
   for info in z.infolist():
    if info.is_dir() or not info.filename.startswith("REPO/"):continue
    n=info.filename[5:]
    p=Path(n)
    assert n and not p.is_absolute() and ".." not in p.parts and "\\" not in n
    assert ((info.external_attr>>16)&0o170000)!=stat.S_IFLNK
    dest=repo/n;dest.parent.mkdir(parents=True,exist_ok=True)
    with z.open(info) as src,dest.open("xb") as target:shutil.copyfileobj(src,target)
    count+=1
  assert count==397, count
  record["source_file_count"]=count
  record["apply_check"]=shell(["git","apply","--check",OUT/"PATCH_MINCTX_03581_R1.patch"],OUT/"apply_check.log",repo,180)
  if record["apply_check"]["exit"]!=0:record["status"]="PATCH_APPLY_CHECK_FAILED"
  else:
   record["apply"]=shell(["git","apply",OUT/"PATCH_MINCTX_03581_R1.patch"],OUT/"apply.log",repo,180)
   if record["apply"]["exit"]!=0:record["status"]="PATCH_APPLY_FAILED"
   else:
    db=Path(td)/"db"
    record["codeql_database_create"]=shell([CODEQL,"database","create",db,"--language=javascript","--source-root="+str(repo),"--threads=4","--ram=12000"],OUT/"codeql_create.log",None,5400)
    if record["codeql_database_create"]["exit"]!=0:record["status"]="CODEQL_DB_CREATE_FAILED"
    else:
     record["codeql_analyze"]=shell([CODEQL,"database","analyze",db,SUITE,"--format=sarifv2.1.0","--output="+str(OUT/"after.sarif"),"--threads=4","--ram=12000"],OUT/"codeql_analyze.log",None,5400)
     if record["codeql_analyze"]["exit"]!=0 or not (OUT/"after.sarif").exists():record["status"]="CODEQL_ANALYZE_FAILED"
     else:
      before,bd=signals(BASE/"baseline.sarif")
      old,od=signals(P1/"after.sarif")
      after,ad=signals(OUT/"after.sarif")
      new=after-before
      historical=old-before
      history_retained=historical & new
      history_absent=historical-new
      introduced_replacement=new-historical
      warn={"baseline_total":sum(before.values()),"original_p1_total":sum(old.values()),
       "original_p1_new":sum(historical.values()),"after_total":sum(after.values()),
       "new_vs_baseline":sum(new.values()),
       "historical_p1_signatures_remaining":sum(history_retained.values()),
       "historical_p1_signatures_no_longer_detected":sum(history_absent.values()),
       "additional_signatures_vs_historical_p1":sum(introduced_replacement.values()),
       "new_warning_rules":dict(sorted({k[0]:sum(v for k,v in new.items() if k[0]==k[0]) for k in new}.items()))}
      # Correct and explicitly deduplicate per-rule aggregation.
      warn["new_warning_rules"]=dict(sorted(Counter({rule:sum(v for (r,path,msg),v in new.items() if r==rule) for rule,_,_ in new}).items()))
      (OUT/"warning_delta.json").write_text(json.dumps({
       "method":"line-agnostic rule/file/normalized-message multiset delta",
       "new":entries(new,ad),"original_p1_new":entries(historical,od),
       "original_p1_remaining":entries(history_retained,ad),"original_p1_absent":entries(history_absent,od),
       "new_not_identical_to_p1":entries(introduced_replacement,ad)},indent=2))
      record.update(warn)
      record.update(after_sarif_sha256=file_sha(OUT/"after.sarif"),status="CODEQL_SCAN_COMPLETE")
except Exception as e:
 record.update(status="ERROR",error_type=type(e).__name__,error_message=str(e))
finally:
 record["finished_utc"]=datetime.now(timezone.utc).isoformat()
 (OUT/"RESULT.json").write_text(json.dumps(record,indent=2))
 print(json.dumps(record,indent=2),flush=True)
