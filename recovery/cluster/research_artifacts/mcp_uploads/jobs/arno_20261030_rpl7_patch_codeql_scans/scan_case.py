#!/usr/bin/env python3
"""Controlled RPL7 P1/P2/P3 CodeQL patch analysis, one case per isolated Slurm task.
No untrusted project code executed; git apply + CodeQL JS extractor only.
Original member bytes, raw SARIF, logs and hashes are preserved for independent replay.
No master SQLite or Hugging Face writes.
"""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import argparse,hashlib,json,os,re,shutil,stat,subprocess,sys,tempfile,time,zipfile
ROOT=Path.home()/"research_artifacts"
SOURCE=ROOT/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2"
INCOMING=ROOT/"mcp_uploads/arno_rpl7_patch_upload_20261030/RECEIPT_RPL7_RUN_04B827A1E668.zip"
BASE=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results"
OUT=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results"
CODEQL=Path.home()/"tools/codeql/codeql"
EXPECTED_ZIP_SHA="c88bc9da10a830ffccd6c318a4da446440ed7aeb16ad4ef07f37c725edd3e9e6"
SUITE="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
CASES=("03429","03581","08152","12344","22223","31207","32759")
def sha_bytes(x):return hashlib.sha256(x).hexdigest()
def sha_file(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(4*1024*1024),b""):h.update(b)
 return h.hexdigest()
def ck(ok,msg):
 if not ok:raise ValueError(msg)
def run(cmd,log,cwd=None,timeout=10800):
 start=time.monotonic()
 with log.open("x",encoding="utf-8") as f:
  try:
   r=subprocess.run([str(x) for x in cmd],cwd=cwd,stdout=f,stderr=subprocess.STDOUT,check=False,timeout=timeout)
   code=r.returncode
  except subprocess.TimeoutExpired:
   code=124
 return {"exit":code,"seconds":round(time.monotonic()-start,2),"log":str(log.name)}
def extract_repo(zip_path,dest):
 dest.mkdir(parents=True)
 count=0
 with zipfile.ZipFile(zip_path) as z:
  for info in z.infolist():
   if info.is_dir() or not info.filename.startswith("REPO/"):continue
   rel=info.filename[len("REPO/"):]
   parts=Path(rel).parts
   ck(parts and not Path(rel).is_absolute() and ".." not in parts and "\\" not in rel,"Unsafe source ZIP member")
   mode=(info.external_attr>>16)&0o170000
   ck(mode!=stat.S_IFLNK,"Source ZIP symlink blocked")
   target=dest.joinpath(*parts)
   target.parent.mkdir(parents=True,exist_ok=True)
   ck(not target.exists(),"Duplicate input path")
   with z.open(info) as f,target.open("xb") as g:shutil.copyfileobj(f,g)
   count+=1
 ck(count>0,"Empty frozen source")
 return count
def signals(sarif):
 doc=json.loads(Path(sarif).read_text(encoding="utf-8"))
 strict=Counter();stable=Counter()
 for job in doc.get("runs",[]):
  for item in job.get("results",[]):
   rule=item.get("ruleId") or ""
   msg=" ".join(str(item.get("message",{}).get("text") or "").split())
   loc=item.get("locations",[])
   physical=(loc[0].get("physicalLocation") or {}) if loc else {}
   path=((physical.get("artifactLocation") or {}).get("uri") or "").replace("\\","/")
   line=(physical.get("region") or {}).get("startLine") or 0
   stable[(rule,path,msg)]+=1
   strict[(rule,path,msg,line)]+=1
 return strict,stable
def main(case):
 ck(case in CASES,"Unapproved case")
 ck(INCOMING.is_file(),"Uploaded ZIP not present in Wits workspace: "+str(INCOMING))
 ck(sha_file(INCOMING)==EXPECTED_ZIP_SHA,"Uploaded ZIP SHA does not match user-supplied original")
 manifest=json.loads((SOURCE/"MANIFEST.json").read_text())
 matched=sorted([row for row in manifest["runs"] if row["case_id"]==case],key=lambda x:x["condition"])
 ck(len(matched)==3 and [x["condition"] for x in matched]==["P1","P2","P3"],"Three research conditions missing")
 ck(len({x["repo_tree_sha256"] for x in matched})==1,"Different source repos across conditions")
 base_dir=BASE/("CASE_"+case)
 base_result=json.loads((base_dir/"RESULT.json").read_text())
 ck(base_result["status"]=="BASELINE_CODEQL_COMPLETE","Corresponding frozen baseline scan failed")
 base_sarif=base_dir/"baseline.sarif"
 ck(base_sarif.exists() and sha_file(base_sarif)==base_result["sarif_sha256"],"Baseline SARIF fingerprint changed")
 baseline_strict,baseline_stable=signals(base_sarif)
 caseout=OUT/("CASE_"+case)
 ck(not caseout.exists(),"Case results exist; do not overwrite")
 caseout.mkdir(parents=True)
 records=[]
 with zipfile.ZipFile(INCOMING) as bundle:
  ck(bundle.testzip() is None,"Corrupted user-returned ZIP")
  all_names={f.filename for f in bundle.infolist() if not f.is_dir()}
  ck(len(all_names)==42 and len(bundle.namelist())==42,"Wrong patch/receipt census")
  with tempfile.TemporaryDirectory(prefix="arno_rpl7_after_"+case+"_",dir=os.environ.get("TMPDIR","/tmp")) as temp:
   scratch=Path(temp)
   for m in matched:
    run_id=m["run_id"];condition=m["condition"]
    record={"run_id":run_id,"case_id":case,"condition":condition,"source_kind":m["source_kind"],
      "original_input_zip_sha256":m["sha256"],"sanitized_repo_tree_sha256":m["repo_tree_sha256"],
      "user_return_zip_sha256":EXPECTED_ZIP_SHA,"baseline_sarif_sha256":base_result["sarif_sha256"],
      "codeql_version":"2.25.6","suite":SUITE,"functional_status":"NOT_TESTED",
      "started_at_utc":datetime.now(timezone.utc).isoformat(),"checks":{}}
    runout=caseout/run_id;runout.mkdir()
    pname="PATCH_"+run_id+".patch";rname="RECEIPT_"+run_id+".json"
    try:
     ck(pname in all_names and rname in all_names,"Missing case patch/receipt")
     patch=bundle.read(pname);receipt=bundle.read(rname)
     document=json.loads(receipt)
     ck(document.get("run_id")==run_id,"Receipt run ID mismatch")
     ck(patch.startswith(b"diff --git "),"Missing unified diff header")
     ck(len(patch)<5_000_000 and len(receipt)<1_000_000,"Suspicious output size")
     (runout/pname).write_bytes(patch)
     (runout/rname).write_bytes(receipt)
     record["patch_sha256"]=sha_bytes(patch)
     record["receipt_sha256"]=sha_bytes(receipt)
     record["receipt_generation_status"]=document.get("generation_status",document.get("status","UNSPECIFIED"))
     if document.get("patch_sha256"):
      record["receipt_declared_patch_sha_match"]=document["patch_sha256"]==record["patch_sha256"]
      ck(record["receipt_declared_patch_sha_match"],"Reported patch SHA mismatch")
     for path in re.findall(rb"^diff --git a/([^\n ]+) b/([^\n ]+)\s*$",patch,re.M):
      for name in path:
       x=name.decode("utf-8","replace")
       ck(x and not x.startswith("/") and ".." not in x.split("/") and "\\" not in x and "\x00" not in x,"Unsafe patch header path")
     input_zip=SOURCE/"run_zips"/(run_id+".zip")
     ck(sha_file(input_zip)==m["sha256"],"Source ZIP checksum mismatch")
     repo=scratch/run_id/"REPO";repo.parent.mkdir()
     record["source_file_count"]=extract_repo(input_zip,repo)
     record["checks"]["apply_check"]=run(["git","apply","--check",str(runout/pname)],runout/"apply_check.log",cwd=repo,timeout=180)
     if record["checks"]["apply_check"]["exit"]!=0:
      record["status"]="PATCH_APPLY_CHECK_FAILED"
     else:
      record["checks"]["apply"]=run(["git","apply",str(runout/pname)],runout/"apply.log",cwd=repo,timeout=180)
      if record["checks"]["apply"]["exit"]!=0:
       record["status"]="PATCH_APPLY_FAILED"
      else:
       database=scratch/run_id/"db"
       record["checks"]["database_create"]=run([CODEQL,"database","create",database,"--language=javascript",
           "--source-root="+str(repo),"--threads=4","--ram=12000"],runout/"codeql_create.log")
       if record["checks"]["database_create"]["exit"]!=0:record["status"]="CODEQL_DB_CREATE_FAILED"
       else:
        sarif=runout/"after.sarif"
        record["checks"]["analysis"]=run([CODEQL,"database","analyze",database,SUITE,
         "--format=sarifv2.1.0","--output="+str(sarif),"--threads=4","--ram=12000"],runout/"codeql_analyze.log")
        if record["checks"]["analysis"]["exit"]!=0 or not sarif.exists():record["status"]="CODEQL_SCAN_FAILED"
        else:
         after_strict,after_stable=signals(sarif)
         record.update({"status":"CODEQL_SCAN_COMPLETE","after_sarif_sha256":sha_file(sarif),"after_total":sum(after_stable.values()),
          "before_total":sum(baseline_stable.values()),
          "new_strict_line_including":sum((after_strict-baseline_strict).values()),
          "new_conservative_line_agnostic":sum((after_stable-baseline_stable).values()),
          "new_conservative_by_rule":dict(Counter({k:sum(v for x,v in (after_stable-baseline_stable).items() if x[0]==k) for k in {x[0] for x in (after_stable-baseline_stable)}}))})
    except Exception as error:
     record["status"]="VALIDATION_OR_EXECUTION_ERROR"
     record["error_type"]=type(error).__name__
     record["error_message"]=str(error)[:350]
    finally:
     record["finished_at_utc"]=datetime.now(timezone.utc).isoformat()
     (runout/"RESULT.json").write_text(json.dumps(record,indent=2),encoding="utf-8")
     records.append(record)
     shutil.rmtree(scratch/run_id,ignore_errors=True)
  result={"case_id":case,"run_ids":[x["run_id"] for x in records],
    "statuses":{x["run_id"]:x["status"] for x in records},
    "scans_complete":sum(x["status"]=="CODEQL_SCAN_COMPLETE" for x in records),
    "source_baseline_sarif_sha256":base_result["sarif_sha256"],
    "original_patches_not_modified":True,"historical_master_not_modified":True,
    "note":"Case scripts use independent source trees and a common re-scanned source baseline; raw source patch/receipt and CodeQL SARIF preserved."}
  (caseout/"CASE_SUMMARY.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
  print(json.dumps(result),flush=True)
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--case",choices=CASES,required=True)
 arg=p.parse_args();main(arg.case)
