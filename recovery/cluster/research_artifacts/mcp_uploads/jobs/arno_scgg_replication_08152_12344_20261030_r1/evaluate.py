from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import ast,hashlib,json,shutil,stat,subprocess,sys,tempfile,time,zipfile
ROOT=Path.home()/"research_artifacts"
STAGE=ROOT/"mcp_uploads/jobs/arno_scgg_replication_08152_12344_20261030_r1"
INPUTS=ROOT/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2/run_zips"
BASE=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results"
P1=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results"
CODEQL=Path.home()/"tools/codeql/codeql"
SUITE="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
CASES={
"08152":{"run":"RPL7_RUN_23E9AAB8295A","zip_sha":"ae4d55030cae00e1b20e0043f64afb750198aabc7fd8961b6db68e4c23552ee4",
"tree_sha":"f71ea5cd1ab9286a5087bfd1d30aa8c46dc78c95a706b3121123216731321377",
"files":85,"source_kind":"FULL_FROZEN_SNAPSHOT","baseline":4,"p1":5,
"patch_sha":"1ba0e72f908dd88537fa9082c3c038cb1d6a7e6430f00abf83dea0c6514cd30e",
"receipt_sha":"ff7547a287b99af4962993e4f532a9f2996e924f1b3816395ea318287453edca",
"patch_parts":2,"receipt_parts":2},
"12344":{"run":"RPL7_RUN_E0EDE434153B","zip_sha":"8020be1830254a7e173949a2ac3189f4f5e86304502ee522424e39fbd9b62f16",
"tree_sha":"3235b17284c3dca4fbe0ee3b437a955573ac238b88c1a0ca99536bfb62cdb6ad",
"files":10341,"source_kind":"FILTERED_SOURCE_PROVISIONAL","baseline":758,"p1":763,
"patch_sha":"d67df6e67554fe92951c28874b40f5073139f5b4de0c0d6f6ef9de60dd7a4879",
"receipt_sha":"2ac2f0355ba6cf1ac60b2829fddf59fa0f89f23e166e9554b024fc389b5ea7d3",
"patch_parts":3,"receipt_parts":2}
}
def sha(b):return hashlib.sha256(b).hexdigest()
def filehash(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(1048576),b""):h.update(b)
 return h.hexdigest()
def part(kind,case,i):
 file=STAGE/(f"{kind}_{case}_{i:02d}.py")
 text=file.read_text(encoding="utf-8")
 assert text.startswith("DATA = "),file
 return ast.literal_eval(text[7:].strip())
def run(cmd,log,cwd=None,timeout=5500):
 start=time.monotonic()
 with log.open("x") as f:
  try: rc=subprocess.run([str(x) for x in cmd],cwd=cwd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout).returncode
  except subprocess.TimeoutExpired: rc=124
 return {"exit":rc,"seconds":round(time.monotonic()-start,2),"log":log.name}
def signatures(path):
 data=json.loads(path.read_text()); c=Counter(); d={}
 for block in data.get("runs",[]):
  for entry in block.get("results",[]):
   loc=(entry.get("locations") or [{}])[0].get("physicalLocation",{})
   key=(entry.get("ruleId",""),loc.get("artifactLocation",{}).get("uri","").replace("\\","/"),
        " ".join((entry.get("message",{}).get("text") or "").split()))
   c[key]+=1
   d.setdefault(key,{"rule":key[0],"file":key[1],"message":key[2],"line":loc.get("region",{}).get("startLine")})
 return c,d
def pretty(items,details):return [dict(details[k],count=n) for k,n in sorted(items.items())]
if len(sys.argv)!=2 or sys.argv[1] not in CASES:raise SystemExit("Expected one case: 08152 or 12344")
case=sys.argv[1]; cfg=CASES[case];out=STAGE/("results_"+case)
out.mkdir(parents=True,exist_ok=False)
result={"run_id":f"SCGG_{case}_R1","case":case,"status":"STARTED",
 "started_utc":datetime.now(timezone.utc).isoformat(),"source_kind":cfg["source_kind"],
 "source_tree_sha256":cfg["tree_sha"],"suite":SUITE,"functional_status":"NOT_VERIFIED",
 "checks":{},"original_patch_modified":False}
try:
 patch="".join(part("patch",case,i) for i in range(cfg["patch_parts"])).encode("utf-8")
 receipt="".join(part("receipt",case,i) for i in range(cfg["receipt_parts"])).encode("utf-8")
 assert sha(patch)==cfg["patch_sha"],("patch sha mismatch",sha(patch))
 assert sha(receipt)==cfg["receipt_sha"],("receipt sha mismatch",sha(receipt))
 assert json.loads(receipt)["run_id"]==f"SCGG_{case}_R1"
 inputzip=INPUTS/(cfg["run"]+".zip")
 assert filehash(inputzip)==cfg["zip_sha"],"Frozen source zip hash mismatch"
 bdir=BASE/("CASE_"+case);pdir=P1/("CASE_"+case)/cfg["run"]
 bmeta=json.loads((bdir/"RESULT.json").read_text());pmeta=json.loads((pdir/"RESULT.json").read_text())
 assert bmeta["sanitized_repo_sha256"]==cfg["tree_sha"]
 assert bmeta["source_kind"]==cfg["source_kind"]
 assert bmeta["sanitized_repo_files"]==cfg["files"]
 assert bmeta["result_count"]==cfg["baseline"]
 assert pmeta["after_total"]==cfg["p1"] and pmeta["source_kind"]==cfg["source_kind"]
 assert filehash(bdir/"baseline.sarif")==bmeta["sarif_sha256"]
 assert filehash(pdir/"after.sarif")==pmeta["after_sarif_sha256"]
 assert CODEQL.is_file()
 patch_path=out/(f"PATCH_SCGG_{case}_R1.patch")
 receipt_path=out/(f"RECEIPT_SCGG_{case}_R1.json")
 patch_path.write_bytes(patch);receipt_path.write_bytes(receipt)
 result.update({"patch_sha256":sha(patch),"receipt_sha256":sha(receipt),"input_source_zip_sha256":cfg["zip_sha"]})
 result["checks"]["version"]=run([CODEQL,"version"],out/"version.log",timeout=120)
 if result["checks"]["version"]["exit"]!=0:raise RuntimeError("CodeQL version query failed")
 version=(out/"version.log").read_text()
 assert "2.25.6" in version,("CodeQL version mismatch",version[:500])
 with tempfile.TemporaryDirectory(prefix=f"arno_scgg_{case}_") as work:
  repo=Path(work)/"repo";repo.mkdir()
  count=0
  with zipfile.ZipFile(inputzip) as z:
   assert z.testzip() is None
   for info in z.infolist():
    if info.is_dir() or not info.filename.startswith("REPO/"):continue
    rel=info.filename[5:]; path=Path(rel)
    assert rel and not path.is_absolute() and ".." not in path.parts and "\\" not in rel
    assert ((info.external_attr>>16)&0o170000)!=stat.S_IFLNK
    dest=repo/rel;dest.parent.mkdir(parents=True,exist_ok=True)
    with z.open(info) as orig,dest.open("xb") as new:shutil.copyfileobj(orig,new)
    count+=1
  assert count==cfg["files"],("source file count mismatch",count)
  result["source_files"]=count
  result["checks"]["apply_check"]=run(["git","apply","--check",patch_path],out/"apply_check.log",repo,120)
  if result["checks"]["apply_check"]["exit"]!=0:result["status"]="APPLY_CHECK_FAILED"
  else:
   result["checks"]["apply"]=run(["git","apply",patch_path],out/"apply.log",repo,120)
   if result["checks"]["apply"]["exit"]!=0:result["status"]="APPLY_FAILED"
   else:
    db=Path(work)/"codeql-db"
    result["checks"]["database_create"]=run([CODEQL,"database","create",db,"--language=javascript",
      "--source-root="+str(repo),"--threads=4","--ram=16000"],out/"database_create.log",timeout=6500)
    if result["checks"]["database_create"]["exit"]!=0:result["status"]="DB_CREATE_FAILED"
    else:
     after=out/"after.sarif"
     result["checks"]["analysis"]=run([CODEQL,"database","analyze",db,SUITE,
       "--format=sarifv2.1.0","--output="+str(after),"--threads=4","--ram=16000"],
       out/"analysis.log",timeout=6500)
     if result["checks"]["analysis"]["exit"]!=0 or not after.is_file():result["status"]="CODEQL_ANALYSIS_FAILED"
     else:
      base,bd=signatures(bdir/"baseline.sarif")
      p1,pd=signatures(pdir/"after.sarif")
      curr,cd=signatures(after)
      new=curr-base;historical=p1-base
      retained=historical&new;absent=historical-new;other=new-historical
      assert sum(base.values())==cfg["baseline"] and sum(p1.values())==cfg["p1"]
      (out/"warning_delta.json").write_text(json.dumps({
       "method":"line-agnostic multiset (ruleId,relative path,normalized message)",
       "new":pretty(new,cd),"historical_p1_new":pretty(historical,pd),
       "historical_remaining":pretty(retained,cd),"historical_absent":pretty(absent,pd),
       "other_new":pretty(other,cd)},indent=2)+"\n")
      result.update({"status":"CODEQL_SCAN_COMPLETE","codeql_version":"2.25.6",
       "baseline_total":sum(base.values()),"historical_p1_total":sum(p1.values()),
       "historical_p1_new":sum(historical.values()),"after_total":sum(curr.values()),
       "new_vs_baseline":sum(new.values()),"historical_p1_remaining":sum(retained.values()),
       "historical_p1_absent":sum(absent.values()),"new_not_matching_p1":sum(other.values()),
       "new_by_rule":dict(sorted({k[0]:sum(v for (rule,pathname,msg),v in new.items() if rule==k[0]) for k in new}.items())),
       "after_sarif_sha256":filehash(after)})
except Exception as e:
 result.update({"status":"ERROR","error_type":type(e).__name__,"error_message":str(e)})
finally:
 result["finished_utc"]=datetime.now(timezone.utc).isoformat()
 (out/"RESULT.json").write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps(result,indent=2),flush=True)
