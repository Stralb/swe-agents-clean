#!/usr/bin/env python3
"""Independent seven-case A/C patch scanning; no target code execution or DB mutation."""
from collections import Counter
from pathlib import Path
import argparse,datetime,hashlib,json,os,re,shutil,stat,subprocess,tempfile,time,zipfile
R=Path.home()/"research_artifacts"
D=R/"mcp_uploads/jobs/arno_ac6_v6_20261030"
ARCH=D/"ARNO_A_C_ALL12_EVIDENCE_INPUT.zip"
ARCH_SHA="d0319135b633c5c0d949e705af4ad99f7a415bd2cd6357d9fbe101bebf3e27b1"
SOURCE=R/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2"
OLD=R/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results"
BASE=R/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results"
OUT=D/"results"
CODEQL=Path.home()/"tools/codeql/codeql"
SUITE="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
CASES=("03429","03581","08152","12344","31207","32759")
ARMS=("MECHANISM","PROSPECTIVE_BUILD")
def sha(data):return hashlib.sha256(data).hexdigest()
def filehash(path):
 h=hashlib.sha256()
 with Path(path).open("rb") as f:
  for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
 return h.hexdigest()
def ensure(condition,msg):
 if not condition:raise ValueError(msg)
def signals(file):
 doc=json.loads(file.read_text())
 stable=Counter();strict=Counter();locations={}
 for run in doc.get("runs",[]):
  for item in run.get("results",[]):
   rule=item.get("ruleId") or ""
   msg=" ".join(str(item.get("message",{}).get("text") or "").split())
   loc=item.get("locations",[])
   physical=(loc[0].get("physicalLocation") or {}) if loc else {}
   source=((physical.get("artifactLocation") or {}).get("uri") or "").replace("\\","/")
   region=physical.get("region") or {}
   line=region.get("startLine") or 0
   k=(rule,source,msg)
   stable[k]+=1;strict[(rule,source,msg,line)]+=1
   locations.setdefault(k,{"rule":rule,"file":source,"message":msg,"line":line})
 return stable,strict,locations
def extract_repo(zip_file,dest):
 count=0;dest.mkdir(parents=True)
 with zipfile.ZipFile(zip_file) as zin:
  ensure(zin.testzip() is None,"invalid frozen source zip")
  for item in zin.infolist():
   if item.is_dir() or not item.filename.startswith("REPO/"):continue
   name=item.filename[5:]
   parts=Path(name).parts
   ensure(bool(parts) and not Path(name).is_absolute() and ".." not in parts and "\\" not in name,"unsafe repo path")
   ensure(((item.external_attr>>16)&0o170000)!=stat.S_IFLNK,"symlink input blocked")
   target=dest.joinpath(*parts);target.parent.mkdir(parents=True,exist_ok=True)
   with zin.open(item) as src,target.open("xb") as dst:shutil.copyfileobj(src,dst,1024*1024)
   count+=1
 ensure(count>0,"no source files")
 return count
def cmd(argv,cwd,log,timeout=14400):
 start=time.monotonic()
 with log.open("x") as f:
  try:
   r=subprocess.run(list(map(str,argv)),cwd=cwd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
   ec=r.returncode
  except subprocess.TimeoutExpired:ec=124
 return {"exit":ec,"seconds":round(time.monotonic()-start,2),"log":log.name}
def eval_task(index):
 ensure(0<=index<12,"invalid task")
 case=CASES[index//2];arm=ARMS[index%2]
 out=OUT/("CASE_"+case)/arm;out.mkdir(parents=True,exist_ok=False)
 result={"case_id":case,"arm":arm,"status":"STARTED","functional_status":"NOT_TESTED",
  "started_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
  "suite":SUITE,"original_scan_comparison":"line-agnostic (rule,path,message) multiset",
  "source_integrity_verified":False,"checks":{}}
 try:
  ensure(ARCH.is_file(),"Input evidence ZIP not present on cluster")
  ensure(filehash(ARCH)==ARCH_SHA,"Input ZIP SHA mismatch")
  manifest=json.loads((SOURCE/"MANIFEST.json").read_text())
  match=next(x for x in manifest["runs"] if x["case_id"]==case and x["condition"]=="P1")
  ensure(match["source_kind"] in ("FULL_FROZEN_SNAPSHOT","FILTERED_SOURCE_PROVISIONAL"),"unexpected source type")
  pz=SOURCE/"run_zips"/(match["run_id"]+".zip")
  ensure(filehash(pz)==match["sha256"],"source ZIP SHA mismatch")
  base_dir=BASE/("CASE_"+case)
  baseline=json.loads((base_dir/"RESULT.json").read_text())
  ensure(baseline["status"]=="BASELINE_CODEQL_COMPLETE","baseline not complete")
  before_sarif=base_dir/"baseline.sarif"
  ensure(filehash(before_sarif)==baseline["sarif_sha256"],"baseline SARIF changed")
  original_dir=OLD/("CASE_"+case)/match["run_id"]
  oldresult=json.loads((original_dir/"RESULT.json").read_text())
  ensure(oldresult["status"]=="CODEQL_SCAN_COMPLETE","P1 scan not complete")
  oldsarif=original_dir/"after.sarif"
  ensure(filehash(oldsarif)==oldresult["after_sarif_sha256"],"P1 SARIF changed")
  with zipfile.ZipFile(ARCH) as bundle:
   ensure(bundle.testzip() is None,"incoming evidence ZIP damaged")
   ensure(len(bundle.namelist())==30,"expected exactly 30 evidence files")
   pn="PATCH_PILOT%s_%s_R1.patch"%(case,arm)
   rn="RECEIPT_PILOT%s_%s_R1.json"%(case,arm)
   patch=bundle.read(pn);receipt=bundle.read(rn);doc=json.loads(receipt)
   ensure(doc.get("run_id")=="PILOT%s_%s_R1"%(case,arm),"receipt run ID mismatch")
   ensure(patch.startswith(b"diff --git "),"not a unified patch")
   ensure(len(patch)<5000000 and len(receipt)<1000000,"oversized input")
   ensure(doc.get("patch_sha256",sha(patch))==sha(patch),"declared patch SHA mismatch")
   if arm=="PROSPECTIVE_BUILD":
    risk=bundle.read("RISKS_PILOT%s_PROSPECTIVE_PREDICT_R1.json"%case)
    ensure(doc.get("prediction_report_sha256")==sha(risk),"C prediction hash mismatch")
    (out/"RISKS.json").write_bytes(risk)
   (out/"PATCH.patch").write_bytes(patch)
   (out/"RECEIPT.json").write_bytes(receipt)
  for paths in re.findall(rb"^diff --git a/([^\n ]+) b/([^\n ]+)\s*$",patch,re.M):
   for b in paths:
    p=b.decode("utf-8","replace")
    ensure(p and not p.startswith("/") and ".." not in p.split("/") and "\\" not in p and "\x00" not in p,"unsafe patch path")
  result.update({"source_kind":match["source_kind"],"run_id":doc["run_id"],
    "source_zip_sha256":match["sha256"],"repo_tree_sha256":match["repo_tree_sha256"],
    "input_zip_sha256":ARCH_SHA,"baseline_sarif_sha256":baseline["sarif_sha256"],
    "original_p1_sarif_sha256":oldresult["after_sarif_sha256"],
    "patch_sha256":sha(patch),"receipt_sha256":sha(receipt),
    "agent_generation_status":doc.get("generation_status"),"source_integrity_verified":True})
  with tempfile.TemporaryDirectory(prefix="arno_ac_"+case+"_"+arm+"_") as scratch:
   t=Path(scratch);repo=t/"repo"
   result["source_file_count"]=extract_repo(pz,repo)
   result["checks"]["patch_check"]=cmd(["git","apply","--check",out/"PATCH.patch"],repo,out/"apply_check.log",120)
   ensure(result["checks"]["patch_check"]["exit"]==0,"patch does not apply")
   result["checks"]["patch_apply"]=cmd(["git","apply",out/"PATCH.patch"],repo,out/"apply.log",120)
   ensure(result["checks"]["patch_apply"]["exit"]==0,"patch application failed")
   db=t/"db"
   result["checks"]["database_create"]=cmd([CODEQL,"database","create",db,"--language=javascript",
     "--source-root="+str(repo),"--threads=4","--ram=12000"],repo,out/"codeql_create.log")
   ensure(result["checks"]["database_create"]["exit"]==0,"CodeQL database creation failed")
   sarif=out/"after.sarif"
   result["checks"]["codeql_analyze"]=cmd([CODEQL,"database","analyze",db,SUITE,
     "--format=sarifv2.1.0","--output="+str(sarif),"--threads=4","--ram=12000"],repo,out/"codeql_analyze.log")
   ensure(result["checks"]["codeql_analyze"]["exit"]==0 and sarif.exists(),"CodeQL analysis failed")
  before,before_strict,_=signals(before_sarif)
  historical,_,_=signals(oldsarif)
  after,after_strict,details=signals(out/"after.sarif")
  p1_new=historical-before;now_new=after-before;retained=p1_new&now_new
  result.update({"status":"CODEQL_SCAN_COMPLETE","baseline_total":sum(before.values()),
    "original_p1_total":sum(historical.values()),"original_p1_new":sum(p1_new.values()),
    "after_total":sum(after.values()),"new_conservative_line_agnostic":sum(now_new.values()),
    "new_strict_line_including":sum((after_strict-before_strict).values()),
    "historical_p1_new_keys_retained":sum(retained.values()),
    "historical_p1_new_keys_avoided":sum(p1_new.values())-sum(retained.values()),
    "new_by_rule":dict(Counter({k:sum(v for kk,v in now_new.items() if kk[0]==k) for k in {kk[0] for kk in now_new}})),
    "new_findings":[{**details[k],"count":v} for k,v in now_new.items()],
    "after_sarif_sha256":filehash(out/"after.sarif")})
 except Exception as e:
  result.update({"status":"ERROR","error_type":type(e).__name__,"error_message":str(e)[:500]})
 finally:
  result["finished_at_utc"]=datetime.datetime.now(datetime.timezone.utc).isoformat()
  (out/"RESULT.json").write_text(json.dumps(result,indent=2))
  print(json.dumps({k:result.get(k) for k in ["case_id","arm","status","original_p1_new","after_total","new_conservative_line_agnostic","error_message"]}),flush=True)
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--index",type=int,required=True)
 args=p.parse_args();eval_task(args.index)
