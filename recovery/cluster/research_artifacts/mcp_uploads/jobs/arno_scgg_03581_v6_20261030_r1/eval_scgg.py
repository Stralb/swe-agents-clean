from pathlib import Path
from collections import Counter
import ast,hashlib,json,shutil,stat,subprocess,tempfile,time,zipfile
from datetime import datetime,timezone

ROOT=Path.home()/"research_artifacts"
STAGE=ROOT/"mcp_uploads/jobs/arno_scgg_03581_v6_20261030_r1"
OUT=STAGE/"results"
SOURCE=ROOT/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2/run_zips/RPL7_RUN_887FBD20CB75.zip"
BASE=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results/CASE_03581"
P1=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results/CASE_03581/RPL7_RUN_887FBD20CB75"
SUITE="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
CODEQL=Path.home()/"tools/codeql/codeql"
H={"patch":"7889c0dcfb99936f64ef3caf95ac90ae386fe717dd36ea7d0438ee53f49c8fb5",
"receipt":"36521623ab964ff773e9e3f6271dc3c9fe9aed8b7870e38945e040bbadeb74e4",
"source":"d9e3951a75d9a0b53e442523d5bd517df1f4e353e7977efec2002fc4a0fe9142",
"tree":"bda7536fe4761882898b1f3e5a968b1c9777f3f1355f72eac850bbbd3d5964ca"}
def sha(data):return hashlib.sha256(data).hexdigest()
def filehash(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for chunk in iter(lambda:f.read(1048576),b""):h.update(chunk)
 return h.hexdigest()
def piece(name,i):
 s=(STAGE/("%s_%02d.py"%(name,i))).read_text()
 assert s.startswith("DATA = ")
 return ast.literal_eval(s[7:].strip())
def run(args,out,cwd=None,timeout=5400):
 start=time.monotonic()
 with out.open("x") as f:
  try: rc=subprocess.run([str(x) for x in args],cwd=cwd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout).returncode
  except subprocess.TimeoutExpired: rc=124
 return {"exit":rc,"seconds":round(time.monotonic()-start,2),"log":out.name}
def sigs(sarif):
 data=json.loads(sarif.read_text());cnt=Counter();details={}
 for r in data.get("runs",[]):
  for obj in r.get("results",[]):
   loc=(obj.get("locations") or [{}])[0].get("physicalLocation",{})
   key=(obj.get("ruleId",""),loc.get("artifactLocation",{}).get("uri","").replace("\\","/"),
        " ".join((obj.get("message",{}).get("text") or "").split()))
   cnt[key]+=1
   details.setdefault(key,{"rule":key[0],"file":key[1],"message":key[2],"line":loc.get("region",{}).get("startLine")})
 return cnt,details
def pretty(cnt,detail):return [dict(detail[k],count=n) for k,n in sorted(cnt.items())]
OUT.mkdir(parents=True,exist_ok=False)
result={"run_id":"SCGG_03581_P1","case":"03581","status":"STARTED",
        "started_utc":datetime.now(timezone.utc).isoformat(),"source_kind":"FULL_FROZEN_SNAPSHOT",
        "source_tree_sha256":H["tree"],"suite":SUITE,"functional_status":"NOT_VERIFIED","checks":{}}
try:
 patch=("".join(piece("patch",i) for i in range(3))+"\n").encode()
 receipt=("".join(piece("receipt",i) for i in range(2))+"\n").encode()
 assert len(patch)==15141 and sha(patch)==H["patch"],("patch integrity",len(patch),sha(patch))
 assert len(receipt)==7947 and sha(receipt)==H["receipt"],("receipt integrity",len(receipt),sha(receipt))
 assert json.loads(receipt)["run_id"]=="SCGG_03581_P1"
 assert filehash(SOURCE)==H["source"]
 base_meta=json.loads((BASE/"RESULT.json").read_text())
 p1_meta=json.loads((P1/"RESULT.json").read_text())
 assert base_meta["sanitized_repo_sha256"]==H["tree"] and base_meta["source_kind"]=="FULL_FROZEN_SNAPSHOT" and base_meta["result_count"]==82
 assert filehash(BASE/"baseline.sarif")==base_meta["sarif_sha256"]
 assert filehash(P1/"after.sarif")==p1_meta["after_sarif_sha256"]
 assert CODEQL.is_file()
 (OUT/"PATCH_SCGG_03581_P1.patch").write_bytes(patch)
 (OUT/"RECEIPT_SCGG_03581_P1.json").write_bytes(receipt)
 result.update(patch_sha256=sha(patch),receipt_sha256=sha(receipt),source_zip_sha256=H["source"])
 with tempfile.TemporaryDirectory(prefix="arno_scgg_03581_") as td:
  repo=Path(td)/"repo";repo.mkdir();num=0
  with zipfile.ZipFile(SOURCE) as z:
   assert z.testzip() is None
   for m in z.infolist():
    if m.is_dir() or not m.filename.startswith("REPO/"):continue
    rel=m.filename[5:];path=Path(rel)
    assert rel and not path.is_absolute() and ".." not in path.parts and "\\" not in rel
    assert ((m.external_attr>>16)&0o170000)!=stat.S_IFLNK
    dest=repo/rel;dest.parent.mkdir(parents=True,exist_ok=True)
    with z.open(m) as src,dest.open("xb") as out:shutil.copyfileobj(src,out)
    num+=1
  assert num==397,num
  result["source_files"]=num
  result["checks"]["apply_check"]=run(["git","apply","--check",OUT/"PATCH_SCGG_03581_P1.patch"],OUT/"apply_check.log",repo,120)
  if result["checks"]["apply_check"]["exit"]!=0:result["status"]="APPLY_CHECK_FAILED"
  else:
   result["checks"]["apply"]=run(["git","apply",OUT/"PATCH_SCGG_03581_P1.patch"],OUT/"apply.log",repo,120)
   if result["checks"]["apply"]["exit"]!=0:result["status"]="PATCH_APPLY_FAILED"
   else:
    db=Path(td)/"db"
    result["checks"]["db_create"]=run([CODEQL,"database","create",db,"--language=javascript","--source-root="+str(repo),"--threads=4","--ram=12000"],OUT/"create.log")
    if result["checks"]["db_create"]["exit"]!=0:result["status"]="CODEQL_DB_FAILED"
    else:
     after=OUT/"after.sarif"
     result["checks"]["analyze"]=run([CODEQL,"database","analyze",db,SUITE,"--format=sarifv2.1.0","--output="+str(after),"--threads=4","--ram=12000"],OUT/"analyze.log")
     if result["checks"]["analyze"]["exit"]!=0 or not after.is_file():result["status"]="CODEQL_ANALYZE_FAILED"
     else:
      base,bmeta=sigs(BASE/"baseline.sarif")
      p1,pmeta=sigs(P1/"after.sarif")
      curr,cmeta=sigs(after)
      new=curr-base;hist=p1-base;retained=hist&new;absent=hist-new;extra=new-hist
      result.update(status="CODEQL_SCAN_COMPLETE",baseline_total=sum(base.values()),historical_p1_total=sum(p1.values()),
       historical_p1_new=sum(hist.values()),after_total=sum(curr.values()),new_vs_baseline=sum(new.values()),
       historical_p1_signatures_remaining=sum(retained.values()),historical_p1_signatures_absent=sum(absent.values()),
       new_signatures_not_matching_p1=sum(extra.values()),after_sarif_sha256=filehash(after),
       new_by_rule=dict(sorted({k[0]:sum(v for (r,p,m),v in new.items() if r==k[0]) for k in new}.items())))
      (OUT/"warning_delta.json").write_text(json.dumps({"method":"line-agnostic rule/path/normalized-message multiset",
       "new":pretty(new,cmeta),"historical_p1_new":pretty(hist,pmeta),"historical_p1_remaining":pretty(retained,cmeta),
       "historical_p1_absent":pretty(absent,pmeta),"new_not_in_p1":pretty(extra,cmeta)},indent=2))
except Exception as e:
 result.update(status="ERROR",error_type=type(e).__name__,error_message=str(e))
finally:
 result["finished_utc"]=datetime.now(timezone.utc).isoformat()
 (OUT/"RESULT.json").write_text(json.dumps(result,indent=2))
 print(json.dumps(result,indent=2),flush=True)
