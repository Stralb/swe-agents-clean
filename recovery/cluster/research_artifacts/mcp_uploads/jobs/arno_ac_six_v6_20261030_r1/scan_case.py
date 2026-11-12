#!/usr/bin/env python3
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import hashlib,json,zipfile,subprocess,tempfile,shutil,stat,re,os,sys,time
ROOT=Path.home()/"research_artifacts"
SRC=ROOT/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2"
PRE=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results"
BASE=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results"
DEST=ROOT/"mcp_uploads/jobs/arno_ac_six_v6_20261030_r1"
EVIDENCE=DEST/"evidence"
CODEQL=Path.home()/"tools/codeql/codeql"
SUITE="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
CASES=["03429","03581","08152","12344","31207","32759"]
ARMS={"A":"MECHANISM","C":"PROSPECTIVE_BUILD"}
def hash_file(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(1048576),b""):h.update(b)
 return h.hexdigest()
def run(argv,log,cwd=None,timeout=10800):
 start=time.monotonic()
 with log.open("x",encoding="utf-8") as f:
  try:
   p=subprocess.run([str(v) for v in argv],cwd=cwd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
   code=p.returncode
  except subprocess.TimeoutExpired:code=124
 return {"exit":code,"seconds":round(time.monotonic()-start,2),"log":log.name}
def extract(zip_path,dest):
 dest.mkdir(parents=True)
 count=0
 with zipfile.ZipFile(zip_path) as z:
  for info in z.infolist():
   if info.is_dir() or not info.filename.startswith("REPO/"):continue
   name=info.filename[5:];parts=Path(name).parts
   assert parts and not Path(name).is_absolute() and ".." not in parts and "\\" not in name
   assert ((info.external_attr>>16)&0o170000)!=stat.S_IFLNK
   target=dest.joinpath(*parts);target.parent.mkdir(parents=True,exist_ok=True)
   with z.open(info) as source,target.open("xb") as output:shutil.copyfileobj(source,output)
   count+=1
 assert count>0
 return count
def signals(file):
 doc=json.loads(file.read_text())
 stable=Counter();strict=Counter();samples={}
 for job in doc.get("runs",[]):
  for item in job.get("results",[]):
   loc=item.get("locations",[])
   ph=loc[0].get("physicalLocation",{}) if loc else {}
   uri=ph.get("artifactLocation",{}).get("uri","").replace("\\","/")
   msg=" ".join((item.get("message",{}).get("text") or "").split())
   rule=item.get("ruleId","")
   key=(rule,uri,msg);stable[key]+=1
   line=ph.get("region",{}).get("startLine") or 0
   strict[(*key,line)]+=1
   samples.setdefault(key,{"rule":rule,"path":uri,"message":msg,"line_sample":line})
 return stable,strict,samples
def rows(counter,samples):
 return [{**samples[k],"count":v} for k,v in sorted(counter.items())]
def main(case,arm):
 assert case in CASES and arm in ARMS
 out=DEST/"results"/("CASE_"+case)/arm
 out.mkdir(parents=True,exist_ok=False)
 rid="PILOT"+case+"_"+ARMS[arm]+"_R1"
 record={"case":case,"arm":arm,"run_id":rid,"status":"STARTED","functional_status":"NOT_TESTED",
         "suite":SUITE,"started_utc":datetime.now(timezone.utc).isoformat(),"checks":{}}
 try:
  manifest=json.loads((SRC/"MANIFEST.json").read_text())
  source=next(x for x in manifest["runs"] if x["case_id"]==case and x["condition"]=="P1")
  zip_path=SRC/"run_zips"/(source["run_id"]+".zip")
  assert hash_file(zip_path)==source["sha256"]
  record.update(source_kind=source["source_kind"],source_zip_sha256=source["sha256"],
                source_repo_tree_sha256=source["repo_tree_sha256"],historical_p1_id=source["run_id"])
  base=BASE/("CASE_"+case)
  baseline=json.loads((base/"RESULT.json").read_text())
  assert baseline["status"]=="BASELINE_CODEQL_COMPLETE"
  baseline_sarif=base/"baseline.sarif"
  assert hash_file(baseline_sarif)==baseline["sarif_sha256"]
  historical=PRE/("CASE_"+case)/source["run_id"]
  historical_report=json.loads((historical/"RESULT.json").read_text())
  assert historical_report["status"]=="CODEQL_SCAN_COMPLETE"
  old_sarif=historical/"after.sarif"
  assert hash_file(old_sarif)==historical_report["after_sarif_sha256"]
  bn,bs,bmeta=signals(baseline_sarif)
  oldn,olds,oldmeta=signals(old_sarif)
  patch=EVIDENCE/("PATCH_"+rid+".patch")
  receipt=EVIDENCE/("RECEIPT_"+rid+".json")
  rec=json.loads(receipt.read_text())
  assert rec["run_id"]==rid
  record.update(patch_sha256=hash_file(patch),receipt_sha256=hash_file(receipt),
                receipt_generation_status=rec.get("generation_status","UNSPECIFIED"))
  if arm=="C":
   risk=EVIDENCE/("RISKS_PILOT"+case+"_PROSPECTIVE_PREDICT_R1.json")
   assert rec["prediction_report_sha256"]==hash_file(risk)
   record["prediction_report_sha256"]=hash_file(risk)
  for left,right in re.findall(rb"^diff --git a/([^\s]+) b/([^\s]+)\s*$",patch.read_bytes(),re.M):
   for x in (left,right):
    s=x.decode("utf-8","replace")
    assert s and not s.startswith("/") and ".." not in s.split("/") and "\\" not in s and "\x00" not in s
  with tempfile.TemporaryDirectory(prefix="arno_ac_"+case+"_"+arm+"_") as td:
   repo=Path(td)/"repo"
   record["source_file_count"]=extract(zip_path,repo)
   record["checks"]["apply_check"]=run(["git","apply","--check",patch],out/"apply_check.log",repo,180)
   if record["checks"]["apply_check"]["exit"]!=0:
    record["status"]="PATCH_APPLY_CHECK_FAILED"
   else:
    record["checks"]["apply"]=run(["git","apply",patch],out/"apply.log",repo,180)
    if record["checks"]["apply"]["exit"]!=0:record["status"]="PATCH_APPLY_FAILED"
    else:
     db=Path(td)/"db"
     record["checks"]["database_create"]=run([CODEQL,"database","create",db,"--language=javascript","--source-root="+str(repo),"--threads=4","--ram=12000"],out/"codeql_create.log")
     if record["checks"]["database_create"]["exit"]!=0:record["status"]="CODEQL_DB_CREATE_FAILED"
     else:
      sarif=out/"after.sarif"
      record["checks"]["analysis"]=run([CODEQL,"database","analyze",db,SUITE,"--format=sarifv2.1.0","--output="+str(sarif),"--threads=4","--ram=12000"],out/"codeql_analyze.log")
      if record["checks"]["analysis"]["exit"]!=0 or not sarif.exists():record["status"]="CODEQL_ANALYSIS_FAILED"
      else:
       after,after_strict,meta=signals(sarif)
       new=after-bn;old_new=oldn-bn
       resolved=old_new-(after-bn)
       record.update(status="CODEQL_SCAN_COMPLETE",baseline_total=sum(bn.values()),historical_p1_total=sum(oldn.values()),
        historical_p1_new=sum(old_new.values()),after_total=sum(after.values()),new_conservative_line_agnostic=sum(new.values()),
        new_strict_line_including=sum((after_strict-bs).values()),
        new_by_rule=dict(sorted(Counter({rule:sum(v for (r,p,m),v in new.items() if r==rule) for rule,_,_ in new}).items())),
        newly_absent_p1_warning_count=sum(resolved.values()),previous_p1_warning_matches_remaining=sum((old_new & (after-bn)).values()),
        baseline_sarif_sha256=baseline["sarif_sha256"],historical_p1_sarif_sha256=historical_report["after_sarif_sha256"],
        after_sarif_sha256=hash_file(sarif))
       trace={"baseline_total":sum(bn.values()),"original_p1_new":rows(old_new,oldmeta),"new_arm_warnings":rows(new,meta),
              "p1_new_no_longer_detected":rows(resolved,oldmeta),
              "counting_rule":"Conservative line-agnostic rule/path/normalized message multiset delta; not proof of vulnerability absence."}
       (out/"WARNING_TRACE.json").write_text(json.dumps(trace,indent=2))
 except Exception as err:
  record.update(status="VALIDATION_OR_RUNTIME_ERROR",error_type=type(err).__name__,error_message=str(err)[:400])
 finally:
  record["finished_utc"]=datetime.now(timezone.utc).isoformat()
  (out/"RESULT.json").write_text(json.dumps(record,indent=2))
  print(json.dumps({k:record.get(k) for k in ["case","arm","status","baseline_total","historical_p1_new","new_conservative_line_agnostic","new_by_rule","after_total","error_message"]}),flush=True)
if __name__=="__main__":
 assert len(sys.argv)==3
 main(sys.argv[1],sys.argv[2])
