import sys,ast,json,hashlib,subprocess,tempfile,zipfile,shutil,time
from pathlib import Path
from collections import Counter
R=Path.home()/"research_artifacts"
D=R/"mcp_uploads/jobs/arno_archgen_03429_31207_v6_20261031_r1"
Q=Path.home()/"tools/codeql/codeql"
cases={
"03429":("RPL7_RUN_6F9E2CE56C8C","5b8e0ab4063788f2c6a5efe52b355511192515f434adbdc23c0457a16f4f5f97",4,241,42,40,1),
"31207":("RPL7_RUN_18A6F0AE41E9","970ea6a8e84d3191ec16fe9cbeef94d659e0c951ed32866e45d67b25cc1f71db",3,15499,60,61,1)}
case=sys.argv[1];run,patch_sha,nparts,nfiles,baseline,historical,historical_new=cases[case]
out=D/("results_"+case);out.mkdir(exist_ok=False)
def sha(b):return hashlib.sha256(b).hexdigest()
def fsha(p):return sha(p.read_bytes())
def signatures(path):
 c=Counter();info={}
 for r in json.loads(path.read_text())["runs"]:
  for x in r.get("results",[]):
   pl=(x.get("locations") or [{}])[0].get("physicalLocation",{})
   k=(x.get("ruleId",""),pl.get("artifactLocation",{}).get("uri","").replace("\\","/")," ".join((x.get("message",{}).get("text") or "").split()))
   c[k]+=1;info[k]={"rule":k[0],"file":k[1],"message":k[2],"line":pl.get("region",{}).get("startLine")}
 return c,info
def details(c,info):return [dict(info[k],count=n) for k,n in sorted(c.items())]
def call(command,log,cwd=None):
 with log.open("w") as f:return subprocess.run([str(x) for x in command],cwd=cwd,stdout=f,stderr=subprocess.STDOUT).returncode
result={"run_id":"ARCHGEN_"+case+"_R1","case":case,"status":"STARTED","source_kind":"FILTERED_SOURCE_PROVISIONAL","codeql_suite":"codeql/javascript-queries:codeql-suites/javascript-security-extended.qls","functional_status":"NOT_VERIFIED","receipt_status":"LOCAL_RECEIPT_NOT_IMPORTED_TO_V6","checks":{}}
try:
 patch="".join(ast.literal_eval((D/f"{case}_patch_{i:02d}.py").read_text()[7:].strip()) for i in range(nparts)).encode()
 assert sha(patch)==patch_sha
 dest=out/("PATCH_ARCHGEN_"+case+"_R1.patch");dest.write_bytes(patch)
 result["patch_sha256"]=sha(patch)
 source=R/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2/run_zips"/(run+".zip")
 base=R/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results"/("CASE_"+case)
 prev=R/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results"/("CASE_"+case)/run
 bm=json.loads((base/"RESULT.json").read_text());pm=json.loads((prev/"RESULT.json").read_text())
 assert fsha(source)==bm["input_zip_sha256"]
 assert bm["sanitized_repo_files"]==nfiles and bm["result_count"]==baseline
 assert bm["source_kind"]=="FILTERED_SOURCE_PROVISIONAL"
 assert pm["after_total"]==historical and pm["new_conservative_line_agnostic"]==historical_new
 result["source_zip_sha256"]=bm["input_zip_sha256"]
 result["source_tree_sha256"]=bm["sanitized_repo_sha256"]
 assert fsha(base/"baseline.sarif")==bm["sarif_sha256"]
 assert fsha(prev/"after.sarif")==pm["after_sarif_sha256"]
 result["checks"]["codeql_version"]=call([Q,"version"],out/"version.log")
 assert result["checks"]["codeql_version"]==0 and "2.25.6" in (out/"version.log").read_text()
 with tempfile.TemporaryDirectory(prefix="arno_archgen_"+case+"_") as tmp:
  repo=Path(tmp)/"repo";repo.mkdir();number=0
  with zipfile.ZipFile(source) as z:
   assert z.testzip() is None
   for item in z.namelist():
    if not item.startswith("REPO/") or item.endswith("/"):continue
    rel=Path(item[5:]);assert ".." not in rel.parts and not rel.is_absolute()
    target=repo/rel;target.parent.mkdir(parents=True,exist_ok=True)
    with z.open(item) as s,target.open("wb") as t:shutil.copyfileobj(s,t)
    number+=1
  assert number==nfiles;result["source_files"]=number
  result["checks"]["apply_check"]=call(["git","apply","--check",dest],out/"apply_check.log",repo)
  if result["checks"]["apply_check"]!=0:result["status"]="APPLY_FAILED"
  else:
   result["checks"]["apply"]=call(["git","apply",dest],out/"apply.log",repo)
   if result["checks"]["apply"]!=0:result["status"]="APPLY_FAILED"
   else:
    db=Path(tmp)/"db"
    result["checks"]["database_create"]=call([Q,"database","create",db,"--language=javascript","--source-root="+str(repo),"--threads=4","--ram=16000"],out/"create.log")
    if result["checks"]["database_create"]!=0:result["status"]="DATABASE_FAILED"
    else:
     after=out/"after.sarif"
     result["checks"]["analyze"]=call([Q,"database","analyze",db,result["codeql_suite"],"--format=sarifv2.1.0","--output="+str(after),"--threads=4","--ram=16000"],out/"analyze.log")
     if result["checks"]["analyze"]!=0:result["status"]="ANALYSIS_FAILED"
     else:
      b,bi=signatures(base/"baseline.sarif");h,hi=signatures(prev/"after.sarif");a,ai=signatures(after)
      new=a-b;hist=h-b
      assert sum(b.values())==baseline and sum(h.values())==historical and sum(hist.values())==historical_new
      (out/"warning_delta.json").write_text(json.dumps({"method":"line-agnostic rule/file/normalized-message multiset","new":details(new,ai),"historical_new":details(hist,hi),"historical_remaining":details(new&hist,ai),"historical_absent":details(hist-new,hi),"other_new":details(new-hist,ai)},indent=2)+"\n")
      result.update(status="CODEQL_SCAN_COMPLETE",codeql_version="2.25.6",baseline_total=baseline,historical_p1_total=historical,historical_p1_new=historical_new,after_total=sum(a.values()),new_vs_baseline=sum(new.values()),historical_p1_remaining=sum((new&hist).values()),historical_p1_absent=sum((hist-new).values()),new_by_rule=dict(Counter({rule:sum(n for (r,_,_),n in new.items() if r==rule) for rule in {x[0] for x in new}})),after_sarif_sha256=fsha(after))
except Exception as e:
 result.update(status="ERROR",error_type=type(e).__name__,error_message=str(e))
finally:
 (out/"RESULT.json").write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps(result,indent=2),flush=True)
