from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import ast,hashlib,json,shutil,stat,subprocess,sys,tempfile,time,zipfile

ROOT=Path.home()/"research_artifacts"
STAGE=ROOT/"mcp_uploads/jobs/arno_spscgg_12344_v6_20261030_r1"
OUT=STAGE/"results"
SOURCE=ROOT/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2/run_zips/RPL7_RUN_E0EDE434153B.zip"
BASE=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results/CASE_12344"
HIST=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results/CASE_12344/RPL7_RUN_E0EDE434153B"
PRIOR=ROOT/"mcp_uploads/jobs/arno_scgg_replication_08152_12344_20261030_r1/results_12344"
SUITE="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
CODEQL=Path.home()/"tools/codeql/codeql"
EXPECTED={
"patch_sha":"2a6e68cf4a9cb2594f5de13905e965d4d64f10a14a16e0b37f0481764fa0abb5",
"receipt_sha":"02a1088148618fa77f35e884a3638339b2ebf295e554408dcd93dd693d84dbd4",
"self_prompt_sha":"7ae9c28ac7a827bbbf6bf29ef3a42d10dd5cf98d49f0a9c92255db04c49d685d",
"source_zip":"8020be1830254a7e173949a2ac3189f4f5e86304502ee522424e39fbd9b62f16",
"source_tree":"3235b17284c3dca4fbe0ee3b437a955573ac238b88c1a0ca99536bfb62cdb6ad"}
def sha(data):return hashlib.sha256(data).hexdigest()
def filehash(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(1048576),b""):h.update(b)
 return h.hexdigest()
def part(kind,i):
 s=(STAGE/f"{kind}_{i:02d}.py").read_text()
 assert s.startswith("DATA = ")
 return ast.literal_eval(s[7:].strip())
def run(args,path,cwd=None,timeout=6500):
 t=time.monotonic()
 with path.open("x") as f:
  try:code=subprocess.run([str(x) for x in args],cwd=cwd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout).returncode
  except subprocess.TimeoutExpired:code=124
 return {"exit":code,"seconds":round(time.monotonic()-t,2),"log":path.name}
def signatures(file):
 sarif=json.loads(file.read_text())
 counter=Counter();details={}
 for run_block in sarif.get("runs",[]):
  for result in run_block.get("results",[]):
   loc=(result.get("locations") or [{}])[0].get("physicalLocation",{})
   key=(result.get("ruleId",""),loc.get("artifactLocation",{}).get("uri","").replace("\\","/"),
    " ".join((result.get("message",{}).get("text") or "").split()))
   counter[key]+=1
   details.setdefault(key,{"rule":key[0],"file":key[1],"message":key[2],"line":loc.get("region",{}).get("startLine")})
 return counter,details
def pretty(counter,details):
 return [dict(details[k],count=n) for k,n in sorted(counter.items())]
OUT.mkdir(parents=True,exist_ok=False)
report={"run_id":"SPSCGG_12344_R1","case_id":"12344","status":"STARTED",
"source_kind":"FILTERED_SOURCE_PROVISIONAL","functional_status":"NOT_VERIFIED",
"started_utc":datetime.now(timezone.utc).isoformat(),"checks":{},"codeql_suite":SUITE,
"source_tree_sha256":EXPECTED["source_tree"],"original_first_delivered_patch_modified":False}
try:
 patch="".join(part("patch",i) for i in range(6)).encode()
 receipt="".join(part("receipt",i) for i in range(8)).encode()
 self_prompt="".join(part("self_prompt",i) for i in range(5)).encode()
 filemap=[
 ("PATCH_SPSCGG_12344_R1.patch",patch,EXPECTED["patch_sha"]),
 ("RECEIPT_SPSCGG_12344_R1.json",receipt,EXPECTED["receipt_sha"]),
 ("IMPLEMENTATION_PROMPT_SPSCGG_12344_R1.md",self_prompt,EXPECTED["self_prompt_sha"])]
 for name,blob,expected_sha in filemap:
  assert sha(blob)==expected_sha,("uploaded artifact integrity",name,len(blob),sha(blob),expected_sha)
  (OUT/name).write_bytes(blob)
 receipt_data=json.loads(receipt)
 assert receipt_data["run_id"]=="SPSCGG_12344_R1"
 assert receipt_data["patch_sha256"]==EXPECTED["patch_sha"]
 assert filehash(SOURCE)==EXPECTED["source_zip"]
 baseline_meta=json.loads((BASE/"RESULT.json").read_text())
 hist_meta=json.loads((HIST/"RESULT.json").read_text())
 prior_meta=json.loads((PRIOR/"RESULT.json").read_text())
 assert baseline_meta["result_count"]==758 and baseline_meta["sanitized_repo_files"]==10341
 assert baseline_meta["source_kind"]=="FILTERED_SOURCE_PROVISIONAL"
 assert baseline_meta["sanitized_repo_sha256"]==EXPECTED["source_tree"]
 assert filehash(BASE/"baseline.sarif")==baseline_meta["sarif_sha256"]
 assert filehash(HIST/"after.sarif")==hist_meta["after_sarif_sha256"]
 assert hist_meta["after_total"]==763 and hist_meta["new_conservative_line_agnostic"]==5
 assert filehash(PRIOR/"after.sarif")==prior_meta["after_sarif_sha256"]
 assert prior_meta["new_vs_baseline"]==5
 assert CODEQL.is_file()
 report.update(patch_sha256=sha(patch),receipt_sha256=sha(receipt),
  self_prompt_sha256=sha(self_prompt),source_zip_sha256=EXPECTED["source_zip"],
  prior_scgg_after_total=prior_meta["after_total"],prior_scgg_new=prior_meta["new_vs_baseline"])
 report["checks"]["version"]=run([CODEQL,"version"],OUT/"codeql_version.log",timeout=120)
 assert report["checks"]["version"]["exit"]==0
 assert "2.25.6" in (OUT/"codeql_version.log").read_text()
 report["codeql_version"]="2.25.6"
 with tempfile.TemporaryDirectory(prefix="arno_spscgg_12344_") as temp:
  repo=Path(temp)/"repo";repo.mkdir()
  count=0
  with zipfile.ZipFile(SOURCE) as z:
   assert z.testzip() is None
   for entry in z.infolist():
    if entry.is_dir() or not entry.filename.startswith("REPO/"):continue
    rel=entry.filename[5:];p=Path(rel)
    assert rel and not p.is_absolute() and ".." not in p.parts and "\\" not in rel
    assert ((entry.external_attr>>16)&0o170000)!=stat.S_IFLNK
    dst=repo/rel;dst.parent.mkdir(parents=True,exist_ok=True)
    with z.open(entry) as inp,dst.open("xb") as o:shutil.copyfileobj(inp,o)
    count+=1
  assert count==10341,("frozen source count",count)
  report["source_files"]=count
  report["checks"]["apply_check"]=run(["git","apply","--check",OUT/"PATCH_SPSCGG_12344_R1.patch"],OUT/"apply_check.log",repo,120)
  if report["checks"]["apply_check"]["exit"]!=0:report["status"]="APPLY_CHECK_FAILED"
  else:
   report["checks"]["apply"]=run(["git","apply",OUT/"PATCH_SPSCGG_12344_R1.patch"],OUT/"apply.log",repo,120)
   if report["checks"]["apply"]["exit"]!=0:report["status"]="PATCH_APPLY_FAILED"
   else:
    db=Path(temp)/"codeql-db"
    report["checks"]["database_create"]=run([CODEQL,"database","create",db,"--language=javascript",
     "--source-root="+str(repo),"--threads=4","--ram=16000"],OUT/"create.log",timeout=6800)
    if report["checks"]["database_create"]["exit"]!=0:report["status"]="CODEQL_DB_CREATE_FAILED"
    else:
     after=OUT/"after.sarif"
     report["checks"]["analysis"]=run([CODEQL,"database","analyze",db,SUITE,
      "--format=sarifv2.1.0","--output="+str(after),"--threads=4","--ram=16000"],
      OUT/"analyze.log",timeout=6800)
     if report["checks"]["analysis"]["exit"]!=0 or not after.exists():report["status"]="CODEQL_ANALYZE_FAILED"
     else:
      b,bd=signatures(BASE/"baseline.sarif")
      h,hd=signatures(HIST/"after.sarif")
      p,pd=signatures(PRIOR/"after.sarif")
      c,cd=signatures(after)
      new=c-b;historical=h-b;previous=p-b
      assert sum(b.values())==758 and sum(h.values())==763 and sum(previous.values())==5
      retained=new&historical;excluded=historical-new;other=new-historical
      (OUT/"warning_delta.json").write_text(json.dumps({
       "method":"line-agnostic multiset (ruleId, relative URI, normalized message)",
       "new":pretty(new,cd),"historical_p1_new":pretty(historical,hd),
       "historical_remaining":pretty(retained,cd),"historical_absent":pretty(excluded,hd),
       "new_not_in_historical":pretty(other,cd),"prior_scgg_new":pretty(previous,pd)},indent=2)+"\n")
      report.update(status="CODEQL_SCAN_COMPLETE",baseline_total=sum(b.values()),
       historical_p1_total=sum(h.values()),historical_p1_new=sum(historical.values()),
       prior_scgg_after_total=sum(p.values()),prior_scgg_new=sum(previous.values()),
       after_total=sum(c.values()),new_vs_baseline=sum(new.values()),
       historical_p1_remaining=sum(retained.values()),historical_p1_absent=sum(excluded.values()),
       new_not_matching_p1=sum(other.values()),new_by_rule=dict(sorted({
        key[0]:sum(v for (rule,path,msg),v in new.items() if rule==key[0]) for key in new
       }.items())),after_sarif_sha256=filehash(after))
except Exception as e:
 report.update(status="ERROR",error_type=type(e).__name__,error_message=str(e))
finally:
 report["finished_utc"]=datetime.now(timezone.utc).isoformat()
 (OUT/"RESULT.json").write_text(json.dumps(report,indent=2)+"\n")
 print(json.dumps(report,indent=2),flush=True)
