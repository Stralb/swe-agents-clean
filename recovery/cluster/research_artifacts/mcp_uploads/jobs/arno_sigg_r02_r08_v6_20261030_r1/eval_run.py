#!/usr/bin/env python3
"""Frozen case 03581 SIGG pilot evaluation: 1 independent agent run per invocation."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import ast,hashlib,json,stat,subprocess,tempfile,zipfile,shutil,time,re,sys,os
CASE="03581"
ROOT=Path.home()/"research_artifacts"
STAGE=ROOT/"mcp_uploads/jobs/arno_sigg_r02_r08_v6_20261030_r1"
SOURCE=ROOT/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2/run_zips/RPL7_RUN_887FBD20CB75.zip"
BASE=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results/CASE_03581"
P1=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results/CASE_03581/RPL7_RUN_887FBD20CB75"
CODEQL=Path.home()/"tools/codeql/codeql"
SUITE="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
HASHES={
 "R02":{"patch":"ebcb09ddb1b07f6c94d28cd96a34b77aa607da643ba66f8d385af7ab4510cf87","receipt":"dc652982e0b051a83e13b9dd75b638dc331f785c028988c9cae6489c2e9e1301","patch_bytes":17214,"receipt_bytes":3701},
 "R08":{"patch":"09e61ccaa60ee0e7b9ef3f221234652b5e507646f7d1bffc3cf11e25ab2d00e6","receipt":"5493c04e211f4b5ed1b1fb002d2167c9f496dfe8e58b9f32ed3828e8ad4941a6","patch_bytes":19035,"receipt_bytes":5918}}
SOURCE_SHA="d9e3951a75d9a0b53e442523d5bd517df1f4e353e7977efec2002fc4a0fe9142"
TREE_SHA="bda7536fe4761882898b1f3e5a968b1c9777f3f1355f72eac850bbbd3d5964ca"
def digest(blob):return hashlib.sha256(blob).hexdigest()
def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for v in iter(lambda:f.read(1048576),b""):h.update(v)
 return h.hexdigest()
def part(path):
 s=path.read_text(encoding="utf-8")
 assert s.startswith("DATA = ")
 val=ast.literal_eval(s[7:].strip())
 assert isinstance(val,str)
 return val
def call(cmd,out,cwd=None,timeout=3600):
 start=time.monotonic()
 with out.open("x",encoding="utf-8") as f:
  try:
   p=subprocess.run([str(x) for x in cmd],cwd=cwd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
   code=p.returncode
  except subprocess.TimeoutExpired:code=124
 return {"exit":code,"elapsed_s":round(time.monotonic()-start,2),"log":out.name}
def signature(p):
 x=json.loads(p.read_text());counter=Counter();examples={}
 for run in x.get("runs",[]):
  for item in run.get("results",[]):
   ph=(item.get("locations") or [{}])[0].get("physicalLocation",{})
   key=(item.get("ruleId",""),ph.get("artifactLocation",{}).get("uri","").replace("\\","/"),
       " ".join((item.get("message",{}).get("text") or "").split()))
   counter[key]+=1
   examples.setdefault(key,dict(rule=key[0],path=key[1],message=key[2],line_sample=ph.get("region",{}).get("startLine",0)))
 return counter,examples
def entries(counts,details):
 return [{**details[k],"count":v} for k,v in sorted(counts.items())]
def main(run_id):
 assert run_id in HASHES
 info=HASHES[run_id]
 out=STAGE/("results_"+run_id)
 out.mkdir(parents=True,exist_ok=False)
 result={"case_id":CASE,"run_id":run_id,"status":"STARTED",
         "started_at_utc":datetime.now(timezone.utc).isoformat(),
         "source_kind":"FULL_FROZEN_SNAPSHOT","source_zip_sha256":SOURCE_SHA,"source_tree_sha256":TREE_SHA,
         "suite":SUITE,"functional_status":"NOT_VERIFIED","checks":{}}
 try:
  patch="".join(part(STAGE/("patch_"+run_id.lower()+"_%02d.py"%i)) for i in range(3)).encode("utf-8")+b"\n"
  receipt=part(STAGE/("receipt_"+run_id.lower()+"_00.py")).encode("utf-8")+b"\n"
  for label,b in [("patch",patch),("receipt",receipt)]:
   assert len(b)==info[label+"_bytes"],(label,len(b),info[label+"_bytes"])
   assert digest(b)==info[label],(label,digest(b),info[label])
  record=json.loads(receipt)
  assert record["run_id"]==run_id,(record.get("run_id"),run_id)
  assert sha(SOURCE)==SOURCE_SHA
  baseline=json.loads((BASE/"RESULT.json").read_text())
  historical=json.loads((P1/"RESULT.json").read_text())
  assert baseline["source_kind"]=="FULL_FROZEN_SNAPSHOT"
  assert baseline["sanitized_repo_sha256"]==TREE_SHA and baseline["result_count"]==82
  assert historical["status"]=="CODEQL_SCAN_COMPLETE"
  assert sha(BASE/"baseline.sarif")==baseline["sarif_sha256"]
  assert sha(P1/"after.sarif")==historical["after_sarif_sha256"]
  for f in [patch,receipt]:assert b"\0" not in f
  for a,b in re.findall(rb"^diff --git a/([^\s]+) b/([^\s]+)\s*$",patch,re.M):
   for name in [a,b]:
    n=name.decode("utf-8")
    assert n and not n.startswith("/") and ".." not in n.split("/") and "\\" not in n
  (out/("PATCH_"+run_id+".patch")).write_bytes(patch)
  (out/("RECEIPT_"+run_id+".json")).write_bytes(receipt)
  result.update(patch_sha256=digest(patch),receipt_sha256=digest(receipt),
     receipt_generation_status=record.get("generation_status","UNSPECIFIED"))
  with tempfile.TemporaryDirectory(prefix="arno_sigg_"+run_id+"_") as td:
   repo=Path(td)/"repo";repo.mkdir()
   num=0
   with zipfile.ZipFile(SOURCE) as z:
    assert z.testzip() is None
    for e in z.infolist():
     if e.is_dir() or not e.filename.startswith("REPO/"):continue
     n=e.filename[5:];f=Path(n)
     assert n and not f.is_absolute() and ".." not in f.parts and "\\" not in n
     assert ((e.external_attr>>16)&0o170000)!=stat.S_IFLNK
     to=repo/f;to.parent.mkdir(parents=True,exist_ok=True)
     with z.open(e) as src,to.open("xb") as dst:shutil.copyfileobj(src,dst)
     num+=1
   assert num==397,num
   result["source_files"]=num
   result["checks"]["patch_check"]=call(["git","apply","--check",out/("PATCH_"+run_id+".patch")],out/"apply_check.log",repo,180)
   if result["checks"]["patch_check"]["exit"]!=0:result["status"]="PATCH_APPLY_CHECK_FAILED"
   else:
    result["checks"]["patch_apply"]=call(["git","apply",out/("PATCH_"+run_id+".patch")],out/"apply.log",repo,180)
    if result["checks"]["patch_apply"]["exit"]!=0:result["status"]="PATCH_APPLY_FAILED"
    else:
     db=Path(td)/"db"
     result["checks"]["db_create"]=call([CODEQL,"database","create",db,"--language=javascript","--source-root="+str(repo),"--threads=4","--ram=12000"],out/"create.log",None,5400)
     if result["checks"]["db_create"]["exit"]!=0:result["status"]="CODEQL_DB_FAILED"
     else:
      sarif=out/"after.sarif"
      result["checks"]["scan"]=call([CODEQL,"database","analyze",db,SUITE,"--format=sarifv2.1.0","--output="+str(sarif),"--threads=4","--ram=12000"],out/"scan.log",None,5400)
      if result["checks"]["scan"]["exit"]!=0 or not sarif.exists():result["status"]="CODEQL_SCAN_FAILED"
      else:
       base,bmeta=signature(BASE/"baseline.sarif")
       p1,pmeta=signature(P1/"after.sarif")
       after,ameta=signature(sarif)
       hist=p1-base
       new=after-base
       retained=hist & new
       absent=hist-new
       novel=new-hist
       result.update(status="CODEQL_SCAN_COMPLETE",
         baseline_total=sum(base.values()),historical_p1_total=sum(p1.values()),
         historical_p1_new=sum(hist.values()),after_total=sum(after.values()),
         new_vs_baseline=sum(new.values()),historical_p1_signatures_remaining=sum(retained.values()),
         historical_p1_signatures_absent=sum(absent.values()),
         new_signatures_not_matching_p1=sum(novel.values()),
         new_by_rule=dict(sorted({rule:sum(v for (r,p,m),v in new.items() if r==rule) for rule,_,_ in new}.items())),
         after_sarif_sha256=sha(sarif))
       (out/"warning_delta.json").write_text(json.dumps({
        "count_method":"line-agnostic rule/path/normalized message multiset delta",
        "new_vs_baseline":entries(new,ameta),
        "original_p1_new":entries(hist,pmeta),
        "historical_p1_remaining":entries(retained,ameta),
        "historical_p1_absent":entries(absent,pmeta),
        "new_not_matching_p1":entries(novel,ameta)},indent=2)+"\n")
 except Exception as err:
  result.update(status="ERROR",error_type=type(err).__name__,error_message=str(err))
 finally:
  result["finished_at_utc"]=datetime.now(timezone.utc).isoformat()
  (out/"RESULT.json").write_text(json.dumps(result,indent=2)+"\n")
  print(json.dumps(result,indent=2),flush=True)
if __name__=="__main__":
 assert len(sys.argv)==2
 main(sys.argv[1])
