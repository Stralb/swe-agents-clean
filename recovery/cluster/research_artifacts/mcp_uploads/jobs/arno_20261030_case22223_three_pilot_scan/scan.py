#!/usr/bin/env python3
"""Independent CodeQL scans for the three 22223 pilot patches.
Original input + returned stage2 packages hashed and validated.
No master database modifications; no remote fetch, no package installs, no executing model patch code.
"""
from pathlib import Path, PurePosixPath
import os,sys,json,hashlib,zipfile,stat,shutil,tempfile,subprocess,time
from collections import Counter
from datetime import datetime,timezone
ROOT=Path.home()/"research_artifacts"
SRC=ROOT/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2/run_zips/RPL7_RUN_3D0780CD09D2.zip"
BASE=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results/CASE_22223"
IN=ROOT/"mcp_uploads/arno_20261030_case22223_three_pilot_intake/ARNO_22223_THREE_PILOT_OUTPUTS_FOR_WITS_20261030.zip"
OUT=ROOT/"mcp_uploads/jobs/arno_20261030_case22223_three_pilot_scan/results"
EXPECTED="59eff1ec445ee38a0d14bc525b9de478e5b29b4867812ec30378093674debafd"
SOURCE_SHA="d4e4eac094924b52f16a98593efb7a9770b542150eb9e31de4026f426c7e6f8c"
BASE_SARIF_SHA="29cd6a0eafc532b0fcfa8ebeb3ffe45f1c869bfa2dabfcef8e74dabd5c4a6094"
ISSUE_SHA="1e33d2030f0ff9128cca2d7c2c541a54e279827c331f4b7f1897642f12cfb3df"
ORIG_P1_SHA="176fc27f7b1fb1b863d10ccbfa9a5fef5a08d9230b5ed6ee4bc615a2433b68f5"
SUITE="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
QL=Path.home()/"tools/codeql/codeql"
IDS={
 "A":("PILOT22223_MECHANISM_R1",None),
 "B":("PILOT22223_BLIND_REPAIR_R1","ARNO_22223_B_STAGE2_REPAIR_READY.zip"),
 "C":("PILOT22223_PROSPECTIVE_BUILD_R1","ARNO_22223_C_STAGE2_IMPLEMENT_READY.zip")}
def check(x,s):
 if not x:raise RuntimeError(s)
def digest(b):return hashlib.sha256(b).hexdigest()
def digfile(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for chunk in iter(lambda:f.read(4*1024*1024),b""):h.update(chunk)
 return h.hexdigest()
def extract(z,repo):
 count=0
 for info in z.infolist():
  n=info.filename
  if not n.startswith("REPO/") or info.is_dir():continue
  rel=n[5:]
  parts=PurePosixPath(rel).parts
  check(rel and not rel.startswith("/") and ".." not in parts and "\\" not in rel,"Invalid REPO member")
  check(((info.external_attr>>16)&0o170000)!=stat.S_IFLNK,"Symlink in source input")
  p=repo.joinpath(*parts);p.parent.mkdir(parents=True,exist_ok=True)
  check(not p.exists(),"Duplicate source member")
  with z.open(info) as f,p.open("xb") as t:shutil.copyfileobj(f,t)
  count+=1
 return count
def counter(path):
 x=json.loads(path.read_text())
 stable=Counter();strict=Counter();samples={}
 for run in x.get("runs",[]):
  for result in run.get("results",[]):
   rule=result.get("ruleId") or ""
   msg=" ".join(str((result.get("message") or {}).get("text") or "").split())
   loc=result.get("locations",[])
   phy=(loc[0].get("physicalLocation") or {}) if loc else {}
   uri=((phy.get("artifactLocation") or {}).get("uri") or "").replace("\\","/")
   line=(phy.get("region") or {}).get("startLine") or 0
   key=(rule,uri,msg)
   stable[key]+=1;strict[(rule,uri,msg,line)]+=1
   samples.setdefault(key,[]).append({"line":line,"physical_location":phy,
    "partial_fingerprints":result.get("partialFingerprints")})
 return stable,strict,samples
def call(args,log,working=None,timeout=14400):
 start=time.monotonic()
 with log.open("x") as f:
  try:
   p=subprocess.run([str(x) for x in args],cwd=working,stdout=f,stderr=subprocess.STDOUT,timeout=timeout,check=False)
   ret=p.returncode
  except subprocess.TimeoutExpired:ret=124
 return {"exit":ret,"seconds":round(time.monotonic()-start,2),"log":log.name}
def main(arm):
 run,stagezip=IDS[arm]
 check(IN.is_file(),"Input bundle not transferred to Wits")
 check(digfile(IN)==EXPECTED,"Uploaded bundle SHA mismatch")
 check(digfile(SRC)==SOURCE_SHA,"Frozen original input hash mismatch")
 result0=json.loads((BASE/"RESULT.json").read_text())
 check(result0["status"]=="BASELINE_CODEQL_COMPLETE" and result0["result_count"]==41,"Baseline state changed")
 check(result0["suite"]==SUITE,"Baseline suite mismatch")
 check(digfile(BASE/"baseline.sarif")==BASE_SARIF_SHA==result0["sarif_sha256"],"Baseline SARIF hash mismatch")
 bstable,bstrict,_=counter(BASE/"baseline.sarif")
 check(sum(bstable.values())==41,"Baseline warning multiset mismatch")
 out=OUT/arm
 check(not out.exists(),"Previous output exists; refuse overwrite")
 out.mkdir(parents=True)
 report={"arm":arm,"run_id":run,"case_id":"22223","status":"CHECKING",
  "source_zip_sha256":SOURCE_SHA,"user_bundle_sha256":EXPECTED,
  "baseline_sarif_sha256":BASE_SARIF_SHA,"codeql_version":"2.25.6","suite":SUITE,
  "functional_status":"NOT_TESTED","started_utc":datetime.now(timezone.utc).isoformat(),
  "node":os.uname().nodename,"python_executable":sys.executable,"checks":{}}
 tmp=Path(tempfile.mkdtemp(prefix="arno_22223_pilot_"+arm+"_",dir=os.environ.get("TMPDIR","/tmp")))
 try:
  with zipfile.ZipFile(IN) as z:
   check(z.testzip() is None,"Corrupt user evidence ZIP")
   manifest=json.loads(z.read("INTAKE_MANIFEST.json"))
   listed={m["filename"]:m for m in manifest["file_manifest"]}
   for n,m in listed.items():
    d=z.read(n)
    check(len(d)==m["bytes"] and digest(d)==m["sha256"],"Intake member SHA failure "+n)
   pn="PATCH_"+run+".patch";rn="RECEIPT_"+run+".json"
   pb=z.read(pn);rb=z.read(rn);receipt=json.loads(rb)
   check(receipt["run_id"]==run,"Model receipt run ID mismatch")
   check(pb.startswith(b"diff --git "),"Not a git patch")
   check(len(pb)<1000000,"Unexpected patch size")
   (out/pn).write_bytes(pb);(out/rn).write_bytes(rb)
   report["patch_sha256"]=digest(pb)
   report["receipt_sha256"]=digest(rb)
   report["receipt_status"]=receipt.get("generation_status","UNSPECIFIED")
   if stagezip:
    with zipfile.ZipFile(z.open(stagezip)) as stage:
     check(stage.testzip() is None,"Corrupt dynamic stage2")
     names=set(stage.namelist())
     reportname="REVIEW.json" if arm=="B" else "PREDICTED_RISKS.json"
     originalreport=("REVIEW_PILOT22223_BLIND_REVIEW_R1.json" if arm=="B" else "RISKS_PILOT22223_PROSPECTIVE_PREDICT_R1.json")
     check(stage.read(reportname)==z.read(originalreport),"Dynamic report not preserved in stage2")
     met=json.loads(stage.read("RUN_METADATA.json"))
     check(met["run_id"]==run and met["case_id"]=="22223","Stage2 metadata mismatch")
     check(digest(stage.read("ISSUE.md"))==ISSUE_SHA,"Stage2 issue bytes mismatch")
     if arm=="B":check(digest(stage.read("P1_PATCH.patch"))==ORIG_P1_SHA,"Blind review prior P1 patch mismatch")
     if arm=="C":check("P1_PATCH.patch" not in names,"Prospective branch contaminated with historical patch")
     check(len([x for x in names if x.startswith("REPO/") and not x.endswith("/")])==401,"Stage2 source census mismatch")
     report["stage2_zip_sha256"]=listed[stagezip]["sha256"]
     report["dynamic_report_sha256"]=listed[originalreport]["sha256"]
  with zipfile.ZipFile(SRC) as z:
   check(digest(z.read("ISSUE.md"))==ISSUE_SHA,"Original issue SHA mismatch")
   repo=tmp/"repo";repo.mkdir()
   report["repo_files"]=extract(z,repo)
   check(report["repo_files"]==401,"Original source count mismatch")
   if stagezip:
    with zipfile.ZipFile(IN) as bundle,zipfile.ZipFile(bundle.open(stagezip)) as stage:
     for x in stage.namelist():
      if x.startswith("REPO/") and not x.endswith("/"):
       check((repo/x[5:]).read_bytes()==stage.read(x),"Stage2 repo source differs from frozen input: "+x)
  # Compile source in isolated temp repo; do not run downloaded model code.
  checkrun=call(["git","apply","--check",str(out/pn)],out/"apply_check.log",working=repo,timeout=300)
  report["checks"]["apply_check"]=checkrun
  check(checkrun["exit"]==0,"Patch did not apply to original")
  report["checks"]["apply"]=call(["git","apply",str(out/pn)],out/"apply.log",working=repo,timeout=300)
  check(report["checks"]["apply"]["exit"]==0,"Patch application failed")
  report["checks"]["codeql_version"]=call([QL,"version"],out/"codeql_version.log",timeout=120)
  check("2.25.6" in (out/"codeql_version.log").read_text(),"CodeQL version mismatch")
  db=tmp/"codeql_db"
  report["checks"]["database_create"]=call([QL,"database","create",db,"--language=javascript",
   "--source-root="+str(repo),"--threads=4","--ram=12000"],out/"codeql_create.log",timeout=10800)
  check(report["checks"]["database_create"]["exit"]==0,"CodeQL create failure")
  after=out/"after.sarif"
  report["checks"]["analysis"]=call([QL,"database","analyze",db,SUITE,"--format=sarifv2.1.0",
   "--output="+str(after),"--threads=4","--ram=12000"],out/"codeql_analyze.log",timeout=10800)
  check(report["checks"]["analysis"]["exit"]==0 and after.exists(),"CodeQL scan failure")
  afterS,afterL,afterExamples=counter(after)
  newS=afterS-bstable
  report.update({"status":"CODEQL_SCAN_COMPLETE","after_sarif_sha256":digfile(after),
   "baseline_total":41,"after_total":sum(afterS.values()),
   "new_conservative_count":sum(newS.values()),
   "new_line_sensitive_count":sum((afterL-bstrict).values()),
   "new_conservative_by_rule":dict(Counter({k:sum(v for t,v in newS.items() if t[0]==k) for k in {t[0] for t in newS}})),
   "retained_finding_count":sum((afterS&bstable).values())})
  findings=[{"rule_id":key[0],"file_uri":key[1],"message":key[2],
   "introduced_occurrences":count,"locations":afterExamples[key]} for key,count in sorted(newS.items())]
  (out/"NEW_WARNINGS.json").write_text(json.dumps(findings,indent=2,ensure_ascii=False))
 except Exception as e:
  report.update({"status":"FAILED","error":repr(e)[:700]})
 finally:
  report["finished_utc"]=datetime.now(timezone.utc).isoformat()
  (out/"RESULT.json").write_text(json.dumps(report,indent=2))
  shutil.rmtree(tmp,ignore_errors=True)
 print(json.dumps({k:report.get(k) for k in ("arm","run_id","status","baseline_total",
 "after_total","new_conservative_count","new_conservative_by_rule","error")}),flush=True)
 if report["status"]!="CODEQL_SCAN_COMPLETE":sys.exit(1)
if __name__=="__main__":
 import argparse
 p=argparse.ArgumentParser();p.add_argument("--arm",required=True,choices=IDS)
 args=p.parse_args();main(args.arm)
