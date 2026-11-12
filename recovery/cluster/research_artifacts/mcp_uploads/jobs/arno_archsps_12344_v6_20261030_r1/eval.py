from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import ast, hashlib, json, shutil, stat, subprocess, tempfile, time, zipfile

ROOT=Path.home()/"research_artifacts"
STAGE=ROOT/"mcp_uploads/jobs/arno_archsps_12344_v6_20261030_r1"
OUT=STAGE/"results"
SOURCE=ROOT/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2/run_zips/RPL7_RUN_E0EDE434153B.zip"
BASE=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results/CASE_12344"
HIST=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results/CASE_12344/RPL7_RUN_E0EDE434153B"
SCGG=ROOT/"mcp_uploads/jobs/arno_scgg_replication_08152_12344_20261030_r1/results_12344"
SPS=ROOT/"mcp_uploads/jobs/arno_spss_12344_v6_20261030_r1/results"
CODEQL=Path.home()/"tools/codeql/codeql"
SUITE="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
HASH={
 "patch":"b34ee487256941f62d566db9d538bcff08c0ad686c0cfb30d4cbdeed144a8d3b",
 "receipt":"d22751e2647b5cc6e8b66f665f6a4aaafce86ec1f5f0066ca93dc6f043e67d0e",
 "prompt":"28879044cdc63b2adba9eae1b78542d899c24bde9e40c347a3a048289589ee2c",
 "source_zip":"8020be1830254a7e173949a2ac3189f4f5e86304502ee522424e39fbd9b62f16",
 "source_tree":"3235b17284c3dca4fbe0ee3b437a955573ac238b88c1a0ca99536bfb62cdb6ad"
}
FILES={"patch":"PATCH_ARCHSPSCGG_12344_R1.patch",
       "receipt":"RECEIPT_ARCHSPSCGG_12344_R1.json",
       "prompt":"IMPLEMENTATION_PROMPT_ARCHSPSCGG_12344_R1.md"}
def sha(data): return hashlib.sha256(data).hexdigest()
def filehash(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for item in iter(lambda:f.read(1048576),b""):h.update(item)
 return h.hexdigest()
def content(kind,count):
 chunks=[]
 for i in range(count):
  t=(STAGE/f"{kind}_{i:02d}.py").read_text()
  assert t.startswith("DATA = "),("bad chunk",kind,i)
  chunks.append(ast.literal_eval(t[7:].strip()))
 return "".join(chunks).encode("utf8")
def command(args,log,cwd=None,timeout=7000):
 t=time.monotonic()
 with log.open("x") as fp:
  try:rc=subprocess.run([str(a) for a in args],cwd=cwd,stdout=fp,stderr=subprocess.STDOUT,timeout=timeout).returncode
  except subprocess.TimeoutExpired:rc=124
 return {"exit":rc,"seconds":round(time.monotonic()-t,2),"log":log.name}
def normalize_sarif(p):
 data=json.loads(p.read_text())
 counts=Counter(); info={}
 for run in data.get("runs",[]):
  for x in run.get("results",[]):
   loc=(x.get("locations") or [{}])[0].get("physicalLocation",{})
   relative=loc.get("artifactLocation",{}).get("uri","").replace("\\","/")
   rule=x.get("ruleId","")
   msg=" ".join((x.get("message",{}).get("text") or "").split())
   key=(rule,relative,msg)
   counts[key]+=1
   info.setdefault(key,{"rule":rule,"path":relative,"message":msg,"line":loc.get("region",{}).get("startLine")})
 return counts,info
def serialize(c,details):
 return [dict(details[k],count=n) for k,n in sorted(c.items())]
OUT.mkdir(parents=True,exist_ok=False)
result={
 "run_id":"ARCHSPSCGG_12344_R1","case":"12344","condition":"ARCHITECTURE_CONSTRAINED_SELF_PROMPTING",
 "status":"STARTED","started_utc":datetime.now(timezone.utc).isoformat(),
 "source_kind":"FILTERED_SOURCE_PROVISIONAL","source_tree_sha256":HASH["source_tree"],
 "suite":SUITE,"functional_status":"NOT_VERIFIED",
 "checks":{},"original_first_delivery_patch_modified":False
}
try:
 artifacts={"patch":content("patch",4),"receipt":content("receipt",1),"prompt":content("prompt",2)}
 for kind,data in artifacts.items():
  assert sha(data)==HASH[kind],(kind,"hash_mismatch",len(data),sha(data))
  (OUT/FILES[kind]).write_bytes(data)
  result[kind+"_sha256"]=HASH[kind]
 receipt=json.loads(artifacts["receipt"])
 assert receipt["run_id"]=="ARCHSPSCGG_12344_R1"
 assert receipt["self_prompt_sha256"]==HASH["prompt"]
 assert receipt["gate"]["patch_sha256"]==HASH["patch"]
 assert filehash(SOURCE)==HASH["source_zip"]
 result["source_zip_sha256"]=HASH["source_zip"]
 b=json.loads((BASE/"RESULT.json").read_text())
 h=json.loads((HIST/"RESULT.json").read_text())
 c=json.loads((SCGG/"RESULT.json").read_text())
 s=json.loads((SPS/"RESULT.json").read_text())
 assert b["source_kind"]=="FILTERED_SOURCE_PROVISIONAL" and b["sanitized_repo_files"]==10341
 assert b["sanitized_repo_sha256"]==HASH["source_tree"] and b["result_count"]==758
 assert h["after_total"]==c["after_total"]==s["after_total"]==763
 assert b["sarif_sha256"]==filehash(BASE/"baseline.sarif")
 for obj,loc in [(h,HIST),(c,SCGG),(s,SPS)]:
  assert obj["after_sarif_sha256"]==filehash(loc/"after.sarif")
 assert CODEQL.is_file()
 result["checks"]["version"]=command([CODEQL,"version"],OUT/"version.log",timeout=120)
 assert result["checks"]["version"]["exit"]==0
 assert "2.25.6" in (OUT/"version.log").read_text(), "CodeQL version mismatch"
 with tempfile.TemporaryDirectory(prefix="arno_archsps_12344_") as work:
  repo=Path(work)/"repo";repo.mkdir()
  count=0
  with zipfile.ZipFile(SOURCE) as z:
   assert z.testzip() is None
   for entry in z.infolist():
    if entry.is_dir() or not entry.filename.startswith("REPO/"):continue
    rel=entry.filename[5:]
    path=Path(rel)
    assert rel and not path.is_absolute() and ".." not in path.parts and "\\" not in rel
    assert ((entry.external_attr >> 16) & 0o170000)!=stat.S_IFLNK
    target=repo/path;target.parent.mkdir(parents=True,exist_ok=True)
    with z.open(entry) as src,target.open("xb") as dst:shutil.copyfileobj(src,dst)
    count+=1
  assert count==10341,("wrong frozen source count",count)
  result["source_files"]=count
  patch=OUT/FILES["patch"]
  result["checks"]["apply_check"]=command(["git","apply","--check",patch],OUT/"apply_check.log",repo,120)
  if result["checks"]["apply_check"]["exit"]!=0:
   result["status"]="APPLY_CHECK_FAILED"
  else:
   result["checks"]["apply"]=command(["git","apply",patch],OUT/"apply.log",repo,120)
   if result["checks"]["apply"]["exit"]!=0:
    result["status"]="PATCH_APPLY_FAILED"
   else:
    db=Path(work)/"database"
    result["checks"]["create"]=command([CODEQL,"database","create",db,"--language=javascript","--source-root="+str(repo),"--threads=4","--ram=16000"],OUT/"create.log",timeout=6000)
    if result["checks"]["create"]["exit"]!=0:result["status"]="CODEQL_DB_FAILED"
    else:
     after=OUT/"after.sarif"
     result["checks"]["analyze"]=command([CODEQL,"database","analyze",db,SUITE,"--format=sarifv2.1.0","--output="+str(after),"--threads=4","--ram=16000"],OUT/"analyze.log",timeout=7000)
     if result["checks"]["analyze"]["exit"]!=0 or not after.exists():
      result["status"]="CODEQL_SCAN_FAILED"
     else:
      before,bd=normalize_sarif(BASE/"baseline.sarif")
      hist,hd=normalize_sarif(HIST/"after.sarif")
      scgg,sd=normalize_sarif(SCGG/"after.sarif")
      sps,pd=normalize_sarif(SPS/"after.sarif")
      current,cd=normalize_sarif(after)
      introduced=current-before
      historical_new=hist-before
      retained=introduced&historical_new
      assert sum(before.values())==758
      assert sum(hist.values())==sum(scgg.values())==sum(sps.values())==763
      delta={
       "method":"line-agnostic multiset (ruleId, relative path, normalized message)",
       "new":serialize(introduced,cd),
       "historical_p1_new":serialize(historical_new,hd),
       "previous_scgg_new":serialize(scgg-before,sd),
       "previous_self_prompt_new":serialize(sps-before,pd),
       "historical_remaining":serialize(retained,cd),
       "historical_absent":serialize(historical_new-introduced,hd),
       "other_new":serialize(introduced-historical_new,cd)
      }
      (OUT/"warning_delta.json").write_text(json.dumps(delta,indent=2)+"\n")
      result.update(
        status="CODEQL_SCAN_COMPLETE",
        codeql_version="2.25.6",
        baseline_total=sum(before.values()),historical_p1_total=sum(hist.values()),
        historical_p1_new=sum(historical_new.values()),
        previous_scgg_total=sum(scgg.values()),previous_scgg_new=sum((scgg-before).values()),
        previous_self_prompt_total=sum(sps.values()),previous_self_prompt_new=sum((sps-before).values()),
        after_total=sum(current.values()),new_vs_baseline=sum(introduced.values()),
        historical_p1_remaining=sum(retained.values()),
        historical_p1_absent=sum((historical_new-introduced).values()),
        new_not_matching_p1=sum((introduced-historical_new).values()),
        new_by_rule={k:sum(n for (rule,_,_),n in introduced.items() if rule==k) for k in sorted({key[0] for key in introduced})},
        after_sarif_sha256=filehash(after)
      )
except Exception as e:
 result.update(status="ERROR",error_type=type(e).__name__,error_message=str(e))
finally:
 result["finished_utc"]=datetime.now(timezone.utc).isoformat()
 (OUT/"RESULT.json").write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps(result,indent=2),flush=True)
