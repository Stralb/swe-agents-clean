from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import hashlib,json,shutil,stat,subprocess,sys,tempfile,time,zipfile
ROOT=Path.home()/"research_artifacts"
D=ROOT/"mcp_uploads/jobs/arno_archgen_last3_v6_20261031_r1"
INPUT=ROOT/"mcp_uploads/archgen_last3_agent_inputs_20261031"
FROZEN=ROOT/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2/run_zips"
BASE=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results"
P1=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results"
CODEQL=Path.home()/"tools/codeql/codeql"
SUITE="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
CASES={"03581":("RPL7_RUN_887FBD20CB75",397,82,84,2,7),
       "08152":("RPL7_RUN_23E9AAB8295A",85,4,5,1,3),
       "12344":("RPL7_RUN_E0EDE434153B",10341,758,763,5,3)}
def sha(data):return hashlib.sha256(data).hexdigest()
def fhash(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for block in iter(lambda:f.read(1048576),b""):h.update(block)
 return h.hexdigest()
def command(argv,path,cwd=None,timeout=7000):
 start=time.monotonic()
 with path.open("x") as f:
  try:code=subprocess.run([str(a) for a in argv],cwd=cwd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout).returncode
  except subprocess.TimeoutExpired:code=124
 return dict(exit=code,seconds=round(time.monotonic()-start,2),log=path.name)
def signature(p):
 c=Counter();info={}
 for batch in json.loads(p.read_text()).get("runs",[]):
  assert batch.get("tool",{}).get("driver",{}).get("name")=="CodeQL"
  for e in batch.get("results",[]):
   loc=(e.get("locations") or [{}])[0].get("physicalLocation",{})
   k=(e.get("ruleId",""),loc.get("artifactLocation",{}).get("uri","").replace("\\","/"),
      " ".join((e.get("message",{}).get("text") or "").split()))
   c[k]+=1;info.setdefault(k,dict(rule=k[0],path=k[1],message=k[2],line=loc.get("region",{}).get("startLine")))
 return c,info
def enumerate_counts(counter,details):
 return [dict(details[k],count=n) for k,n in sorted(counter.items())]
def read_original(path,expected):
 b=path.read_bytes()
 if sha(b)==expected:return b
 if b.endswith(b"\n") and sha(b[:-1])==expected:return b[:-1]
 raise RuntimeError("Original upload SHA256 mismatch: "+str(path))
if len(sys.argv)!=2 or sys.argv[1] not in CASES:raise SystemExit("Case must be 03581/08152/12344")
case=sys.argv[1];run,source_count,base_count,p1_count,p1_new,chunks=CASES[case]
out=D/("results_"+case);out.mkdir(parents=True,exist_ok=False)
status=dict(case=case,run_id="ARCHGEN_"+case+"_R1",status="STARTED",
    condition="GENERAL_ARCHITECTURE",started_utc=datetime.now(timezone.utc).isoformat(),
    source_kind="FULL_FROZEN_SNAPSHOT" if case!="12344" else "FILTERED_SOURCE_PROVISIONAL",
    suite=SUITE,codeql_version="2.25.6",original_patch_modified=False,
    functional_status="NOT_INDEPENDENTLY_VERIFIED",checks={})
try:
 name=f"PATCH_ARCHGEN_{case}_R1.patch"
 receipt_path=INPUT/f"RECEIPT_ARCHGEN_{case}_R1.json"
 receipt=json.loads(receipt_path.read_text())
 assert receipt["case_id"]==case and receipt["run_id"]==status["run_id"]
 patch="".join(json.loads((INPUT/f"PATCH_ARCHGEN_{case}_R1_chunk{i:02d}.json").read_text())["part"] for i in range(chunks)).encode("utf8")
 assert sha(patch)==receipt["patch_sha256"],("Patch hash mismatch",sha(patch),receipt["patch_sha256"])
 prompt_path=INPUT/f"IMPLEMENTATION_PROMPT_ARCHGEN_{case}_R1.md"
 prompt=read_original(prompt_path,receipt["self_prompt_sha256"])
 (out/name).write_bytes(patch)
 (out/prompt_path.name).write_bytes(prompt)
 (out/receipt_path.name).write_bytes(read_original(receipt_path,sha(json.dumps(receipt,ensure_ascii=False,indent=2).encode())) if False else receipt_path.read_bytes())
 status.update(patch_sha256=sha(patch),prompt_sha256=sha(prompt),receipt_sha256=fhash(receipt_path),receipt_status="PROVIDED_VERIFIED",
    source_file_count=source_count,gate_status=receipt.get("gate_status"),
    agent_reported_functional_status=receipt.get("functional_status"))
 frozen=FROZEN/(run+".zip")
 bdir=BASE/("CASE_"+case);hdir=P1/("CASE_"+case)/run
 bm=json.loads((bdir/"RESULT.json").read_text())
 hm=json.loads((hdir/"RESULT.json").read_text())
 assert bm["model_run_id_p1"]==run and bm["case_id"]==case and bm["result_count"]==base_count
 assert bm["sanitized_repo_files"]==source_count and bm["source_kind"]==status["source_kind"]
 assert bm["suite"]==SUITE and bm["codeql_version_expected"]=="2.25.6"
 assert hm["status"]=="CODEQL_SCAN_COMPLETE" and hm["suite"]==SUITE and hm["codeql_version"]=="2.25.6"
 assert hm["after_total"]==p1_count and hm["new_conservative_line_agnostic"]==p1_new
 assert fhash(frozen)==bm["input_zip_sha256"]
 assert fhash(bdir/"baseline.sarif")==bm["sarif_sha256"]
 assert fhash(hdir/"after.sarif")==hm["after_sarif_sha256"]
 status.update(source_zip_sha256=bm["input_zip_sha256"],source_tree_sha256=bm["sanitized_repo_sha256"])
 status["checks"]["version"]=command([CODEQL,"version"],out/"version.log",timeout=120)
 assert status["checks"]["version"]["exit"]==0 and "2.25.6" in (out/"version.log").read_text()
 with tempfile.TemporaryDirectory(prefix="arno_archgen_"+case+"_") as tmp:
  repo=Path(tmp)/"repo";repo.mkdir();count=0
  with zipfile.ZipFile(frozen) as z:
   assert z.testzip() is None
   for e in z.infolist():
    if e.is_dir() or not e.filename.startswith("REPO/"):continue
    rel=e.filename[5:];p=Path(rel)
    assert rel and not p.is_absolute() and ".." not in p.parts and "\\" not in rel
    assert ((e.external_attr>>16)&0o170000)!=stat.S_IFLNK
    dest=repo/p;dest.parent.mkdir(parents=True,exist_ok=True)
    with z.open(e) as fi,dest.open("xb") as fo:shutil.copyfileobj(fi,fo)
    count+=1
  assert count==source_count
  path=out/name
  status["checks"]["apply_check"]=command(["git","apply","--check",path],out/"apply_check.log",cwd=repo,timeout=120)
  if status["checks"]["apply_check"]["exit"]!=0:status["status"]="APPLY_CHECK_FAILED"
  else:
   status["checks"]["apply"]=command(["git","apply",path],out/"apply.log",cwd=repo,timeout=120)
   if status["checks"]["apply"]["exit"]!=0:status["status"]="PATCH_APPLY_FAILED"
   else:
    db=Path(tmp)/"db"
    status["checks"]["create"]=command([CODEQL,"database","create",db,"--language=javascript","--source-root="+str(repo),"--threads=4","--ram=16000"],out/"create.log")
    if status["checks"]["create"]["exit"]!=0:status["status"]="CODEQL_DB_FAILED"
    else:
     sarif=out/"after.sarif"
     status["checks"]["analyze"]=command([CODEQL,"database","analyze",db,SUITE,"--format=sarifv2.1.0","--output="+str(sarif),"--threads=4","--ram=16000"],out/"analyze.log")
     if status["checks"]["analyze"]["exit"]!=0:status["status"]="CODEQL_ANALYZE_FAILED"
     else:
      b,bi=signature(bdir/"baseline.sarif");h,hi=signature(hdir/"after.sarif");a,ai=signature(sarif)
      assert sum(b.values())==base_count and sum(h.values())==p1_count
      historical=h-b;new=a-b;retained=historical&new
      assert sum(historical.values())==p1_new
      delta={"matching":"line-agnostic multiset of ruleId,relative path,normalized message",
          "new":enumerate_counts(new,ai),"historical_p1_new":enumerate_counts(historical,hi),
          "historical_p1_remaining":enumerate_counts(retained,ai),
          "historical_p1_absent":enumerate_counts(historical-new,hi),
          "new_not_matching_historical":enumerate_counts(new-historical,ai)}
      (out/"warning_delta.json").write_text(json.dumps(delta,indent=2)+"\n")
      status.update(status="CODEQL_SCAN_COMPLETE",baseline_total=sum(b.values()),
         historical_p1_total=sum(h.values()),historical_p1_new=sum(historical.values()),
         after_total=sum(a.values()),new_vs_baseline=sum(new.values()),
         historical_p1_remaining=sum(retained.values()),
         historical_p1_absent=sum((historical-new).values()),
         new_not_matching_p1=sum((new-historical).values()),
         new_by_rule={rule:sum(n for (r,_,_),n in new.items() if r==rule) for rule in sorted({k[0] for k in new})},
         after_sarif_sha256=fhash(sarif))
except Exception as e:
 status.update(status="ERROR",error_type=type(e).__name__,error_message=str(e))
finally:
 status["finished_utc"]=datetime.now(timezone.utc).isoformat()
 (out/"RESULT.json").write_text(json.dumps(status,indent=2)+"\n")
 print(json.dumps(status,indent=2),flush=True)
