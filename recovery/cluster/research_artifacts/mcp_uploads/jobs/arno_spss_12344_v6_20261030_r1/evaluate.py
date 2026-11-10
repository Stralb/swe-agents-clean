from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import ast,hashlib,json,shutil,stat,subprocess,sys,tempfile,time,zipfile
R=Path.home()/"research_artifacts"
D=R/"mcp_uploads/jobs/arno_spss_12344_v6_20261030_r1"
OUT=D/"results"
CASE="12344"
ZIP=R/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2/run_zips/RPL7_RUN_E0EDE434153B.zip"
BASE=R/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results/CASE_12344"
P1=R/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results/CASE_12344/RPL7_RUN_E0EDE434153B"
SCGG=R/"mcp_uploads/jobs/arno_scgg_replication_08152_12344_20261030_r1/results_12344"
CODEQL=Path.home()/"tools/codeql/codeql"
SUITE="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
HASHES={
 "patch":"2a6e68cf4a9cb2594f5de13905e965d4d64f10a14a16e0b37f0481764fa0abb5",
 "receipt":"02a1088148618fa77f35e884a3638339b2ebf295e554408dcd93dd693d84dbd4",
 "prompt":"7ae9c28ac7a827bbbf6bf29ef3a42d10dd5cf98d49f0a9c92255db04c49d685d",
 "zip":"8020be1830254a7e173949a2ac3189f4f5e86304502ee522424e39fbd9b62f16",
 "tree":"3235b17284c3dca4fbe0ee3b437a955573ac238b88c1a0ca99536bfb62cdb6ad"
}
def sha(b):return hashlib.sha256(b).hexdigest()
def sha_file(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for block in iter(lambda:f.read(1048576),b""):h.update(block)
 return h.hexdigest()
def get_parts(kind,n):
 strings=[]
 for i in range(n):
  s=(D/f"{kind}_{i:02d}.py").read_text()
  assert s.startswith("DATA = ")
  strings.append(ast.literal_eval(s[7:].strip()))
 return "".join(strings).encode("utf-8")
def exec_cmd(cmd,output,cwd=None,timeout=6000):
 t=time.monotonic()
 with output.open("x") as f:
  try:rc=subprocess.run([str(x) for x in cmd],cwd=cwd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout).returncode
  except subprocess.TimeoutExpired:rc=124
 return {"exit":rc,"seconds":round(time.monotonic()-t,2),"log":output.name}
def sarif_sig(path):
 runs=json.loads(path.read_text())["runs"]
 c=Counter();info={}
 for r in runs:
  for x in r.get("results",[]):
   loc=(x.get("locations") or [{}])[0].get("physicalLocation",{})
   uri=loc.get("artifactLocation",{}).get("uri","").replace("\\","/")
   message=" ".join((x.get("message",{}).get("text") or "").split())
   key=(x.get("ruleId",""),uri,message)
   c[key]+=1
   info.setdefault(key,{"rule":key[0],"file":key[1],"message":key[2],"line":loc.get("region",{}).get("startLine")})
 return c,info
def pretty(c,info):
 return [dict(info[k],count=n) for k,n in sorted(c.items())]
OUT.mkdir(parents=True,exist_ok=False)
result={
"run_id":"SPSCGG_12344_R1","case":"12344",
"started_utc":datetime.now(timezone.utc).isoformat(),
"status":"STARTED","source_kind":"FILTERED_SOURCE_PROVISIONAL",
"source_tree_sha256":HASHES["tree"],"suite":SUITE,
"functional_status":"NOT_VERIFIED","first_delivery_patch_modified":False,
"checks":{}
}
try:
 patch=get_parts("patch",3);receipt=get_parts("receipt",3);prompt=get_parts("prompt",2)
 for k,data in [("patch",patch),("receipt",receipt),("prompt",prompt)]:
  assert sha(data)==HASHES[k],(k,len(data),sha(data))
 rec=json.loads(receipt)
 assert rec["run_id"]=="SPSCGG_12344_R1"
 assert rec["self_prompt_sha256"]==HASHES["prompt"]
 assert rec["patch_sha256"]==HASHES["patch"]
 assert sha_file(ZIP)==HASHES["zip"],"Frozen ZIP changed"
 b=json.loads((BASE/"RESULT.json").read_text())
 p1=json.loads((P1/"RESULT.json").read_text())
 scgg=json.loads((SCGG/"RESULT.json").read_text())
 assert b["sanitized_repo_sha256"]==HASHES["tree"]
 assert b["source_kind"]=="FILTERED_SOURCE_PROVISIONAL" and b["sanitized_repo_files"]==10341
 assert b["result_count"]==758 and p1["after_total"]==763 and scgg["after_total"]==763
 assert sha_file(BASE/"baseline.sarif")==b["sarif_sha256"]
 assert sha_file(P1/"after.sarif")==p1["after_sarif_sha256"]
 assert sha_file(SCGG/"after.sarif")==scgg["after_sarif_sha256"]
 assert CODEQL.is_file()
 (OUT/"PATCH_SPSCGG_12344_R1.patch").write_bytes(patch)
 (OUT/"RECEIPT_SPSCGG_12344_R1.json").write_bytes(receipt)
 (OUT/"IMPLEMENTATION_PROMPT_SPSCGG_12344_R1.md").write_bytes(prompt)
 result.update({
 "patch_sha256":HASHES["patch"],"receipt_sha256":HASHES["receipt"],
 "implementation_prompt_sha256":HASHES["prompt"],"source_zip_sha256":HASHES["zip"]
 })
 result["checks"]["codeql_version"]=exec_cmd([CODEQL,"version"],OUT/"codeql_version.log",timeout=120)
 assert "2.25.6" in (OUT/"codeql_version.log").read_text()
 with tempfile.TemporaryDirectory(prefix="spss_12344_") as td:
  repo=Path(td)/"repo";repo.mkdir()
  count=0
  with zipfile.ZipFile(ZIP) as z:
   assert z.testzip() is None
   for member in z.infolist():
    if member.is_dir() or not member.filename.startswith("REPO/"):continue
    rel=member.filename[5:];pt=Path(rel)
    assert rel and not pt.is_absolute() and ".." not in pt.parts and "\\" not in rel
    assert ((member.external_attr>>16)&0o170000)!=stat.S_IFLNK
    dest=repo/rel;dest.parent.mkdir(parents=True,exist_ok=True)
    with z.open(member) as src,dest.open("xb") as dst:shutil.copyfileobj(src,dst)
    count+=1
  assert count==10341,("Wrong repository file count",count)
  result["source_files"]=count
  result["checks"]["apply_check"]=exec_cmd(["git","apply","--check",OUT/"PATCH_SPSCGG_12344_R1.patch"],OUT/"apply_check.log",repo,120)
  if result["checks"]["apply_check"]["exit"]!=0:
   result["status"]="APPLY_CHECK_FAILED"
  else:
   result["checks"]["apply"]=exec_cmd(["git","apply",OUT/"PATCH_SPSCGG_12344_R1.patch"],OUT/"apply.log",repo,120)
   if result["checks"]["apply"]["exit"]!=0:
    result["status"]="PATCH_APPLY_FAILED"
   else:
    db=Path(td)/"db"
    result["checks"]["db_create"]=exec_cmd([CODEQL,"database","create",db,
      "--language=javascript","--source-root="+str(repo),
      "--threads=4","--ram=16000"],OUT/"create.log",timeout=6500)
    if result["checks"]["db_create"]["exit"]!=0:
     result["status"]="DB_CREATE_FAILED"
    else:
     after=OUT/"after.sarif"
     result["checks"]["analyze"]=exec_cmd([CODEQL,"database","analyze",db,SUITE,
       "--format=sarifv2.1.0","--output="+str(after),
       "--threads=4","--ram=16000"],OUT/"analyze.log",timeout=6500)
     if result["checks"]["analyze"]["exit"]!=0 or not after.exists():
      result["status"]="CODEQL_ANALYZE_FAILED"
     else:
      base,base_info=sarif_sig(BASE/"baseline.sarif")
      orig,orig_info=sarif_sig(P1/"after.sarif")
      old,old_info=sarif_sig(SCGG/"after.sarif")
      current,current_info=sarif_sig(after)
      new=current-base; old_new=old-base; hist_new=orig-base
      retained=hist_new & new;other=new-hist_new
      assert sum(base.values())==758
      assert sum(old.values())==763
      assert sum(orig.values())==763
      (OUT/"warning_delta.json").write_text(json.dumps({
       "comparison_method":"Line-agnostic multiset: (ruleId, relative path, normalized message)",
       "new":pretty(new,current_info),
       "original_p1_new":pretty(hist_new,orig_info),
       "scgg_previous_new":pretty(old_new,old_info),
       "historical_remaining":pretty(retained,current_info),
       "historical_absent":pretty(hist_new-new,orig_info),
       "new_not_matching_historical":pretty(other,current_info)
      },indent=2)+"\n")
      result.update(status="CODEQL_SCAN_COMPLETE",
       codeql_version="2.25.6",
       baseline_total=sum(base.values()),
       historical_p1_total=sum(orig.values()),historical_p1_new=sum(hist_new.values()),
       previous_scgg_total=sum(old.values()),previous_scgg_new=sum(old_new.values()),
       after_total=sum(current.values()),new_vs_baseline=sum(new.values()),
       historical_p1_signatures_remaining=sum(retained.values()),
       historical_p1_signatures_absent=sum(hist_new-new.values()) if False else sum((hist_new-new).values()),
       new_not_matching_historical=sum(other.values()),
       new_by_rule={rid:sum(n for (r,_,_),n in new.items() if r==rid) for rid in sorted({k[0] for k in new})},
       after_sarif_sha256=sha_file(after))
except Exception as ex:
 result.update(status="ERROR",error_type=type(ex).__name__,error_message=str(ex))
finally:
 result["finished_utc"]=datetime.now(timezone.utc).isoformat()
 (OUT/"RESULT.json").write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps(result,indent=2),flush=True)
