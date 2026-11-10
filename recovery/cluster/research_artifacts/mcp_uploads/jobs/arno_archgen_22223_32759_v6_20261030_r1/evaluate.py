from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import ast,hashlib,json,shutil,stat,subprocess,sys,tempfile,time,zipfile
R=Path.home()/"research_artifacts"
D=R/"mcp_uploads/jobs/arno_archgen_22223_32759_v6_20261030_r1"
SRC=R/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2/run_zips"
B=R/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results"
H=R/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results"
Q=Path.home()/"tools/codeql/codeql"
SUITE="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
CFG={
"22223":dict(run="RPL7_RUN_3D0780CD09D2",source="d4e4eac094924b52f16a98593efb7a9770b542150eb9e31de4026f426c7e6f8c",tree="fd0570cef84bc540aa53f6377f9e90026e9b4ef9906c7516430f79d5398547fa",files=401,baseline=41,historical=44,new=3,patch="6ff31ebfd7a2ec4419544a4b6616f6b440d37bbcaac2d6b609973c6da5b605f8",prompt="db24cf5a1901293930e09b9d66da28dae92549cf518631c3bd076887c918dedf",receipt=None,pc=2,mc=2,rc=0),
"32759":dict(run="RPL7_RUN_C24121FB6FE5",source="cf9fdbcc6d38d0cb42e47599c061c72b8f571c7c914d7010a404d88af8b5af07",tree="fc5893eaa233a34b5869edd291f54352c50b2484e326925ddcc8755e72a0d921",files=23,baseline=12,historical=14,new=2,patch="3f4a0e599d357a448062a17bdfee7f83cc70aa567ed5fad964c9ca4387e7d013",prompt="b73106774f0d22951f03aaea1d727641cc67076649e98dcebcfdf8396d54dd0d",receipt="ed0ff8c0d37e1dee28da27eb18fef2fbb47c2ef8d2b1bbf589b4187bc4423aa7",pc=1,mc=2,rc=2)
}
def sha(x):return hashlib.sha256(x).hexdigest()
def fsha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(1048576),b""):h.update(b)
 return h.hexdigest()
def parts(case,kind,n):
 s=""
 for i in range(n):
  t=(D/f"{case}_{kind}_{i:02d}.py").read_text()
  assert t.startswith("DATA = ")
  s+=ast.literal_eval(t[7:].strip())
 return s.encode()
def run(args,path,cwd=None,timeout=5400):
 t=time.monotonic()
 with path.open("x") as f:
  try:rc=subprocess.run([str(x) for x in args],cwd=cwd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout).returncode
  except subprocess.TimeoutExpired:rc=124
 return dict(exit=rc,seconds=round(time.monotonic()-t,2),log=path.name)
def signature(path):
 counts=Counter();details={}
 for r in json.loads(path.read_text())["runs"]:
  for e in r.get("results",[]):
   pl=(e.get("locations") or [{}])[0].get("physicalLocation",{})
   key=(e.get("ruleId",""),pl.get("artifactLocation",{}).get("uri","").replace("\\","/")," ".join((e.get("message",{}).get("text") or "").split()))
   counts[key]+=1
   details.setdefault(key,dict(rule=key[0],file=key[1],message=key[2],line=pl.get("region",{}).get("startLine")))
 return counts,details
def pretty(c,d):return [dict(d[k],count=v) for k,v in sorted(c.items())]
if len(sys.argv)!=2 or sys.argv[1] not in CFG:raise SystemExit("case must be 22223 or 32759")
case=sys.argv[1];c=CFG[case];out=D/("results_"+case)
out.mkdir(exist_ok=False)
result=dict(case=case,run_id="ARCHGEN_"+case+"_R1",status="STARTED",started_utc=datetime.now(timezone.utc).isoformat(),source_kind="FULL_FROZEN_SNAPSHOT",source_tree_sha256=c["tree"],suite=SUITE,first_delivered_patch_modified=False,receipt_status="PROVIDED" if c["receipt"] else "MISSING",functional_status="NOT_VERIFIED",checks={})
try:
 p=parts(case,"patch",c["pc"]);m=parts(case,"prompt",c["mc"])
 assert sha(p)==c["patch"] and sha(m)==c["prompt"]
 patch=out/f"PATCH_ARCHGEN_{case}_R1.patch"
 patch.write_bytes(p)
 (out/f"IMPLEMENTATION_PROMPT_ARCHGEN_{case}_R1.md").write_bytes(m)
 result.update(patch_sha256=sha(p),prompt_sha256=sha(m))
 if c["receipt"]:
  receipt=parts(case,"receipt",c["rc"])
  assert sha(receipt)==c["receipt"]
  meta=json.loads(receipt)
  assert meta["run_id"]==result["run_id"] and meta["patch_sha256"]==c["patch"] and meta["self_prompt_sha256"]==c["prompt"]
  (out/f"RECEIPT_ARCHGEN_{case}_R1.json").write_bytes(receipt)
  result["receipt_sha256"]=sha(receipt)
 zipfile_path=SRC/(c["run"]+".zip")
 assert fsha(zipfile_path)==c["source"]
 result["source_zip_sha256"]=c["source"]
 base=B/("CASE_"+case);historical=H/("CASE_"+case)/c["run"]
 bm=json.loads((base/"RESULT.json").read_text());hm=json.loads((historical/"RESULT.json").read_text())
 assert bm["source_kind"]=="FULL_FROZEN_SNAPSHOT" and bm["sanitized_repo_files"]==c["files"]
 assert bm["sanitized_repo_sha256"]==c["tree"] and bm["result_count"]==c["baseline"]
 assert hm["after_total"]==c["historical"] and hm["new_conservative_line_agnostic"]==c["new"]
 assert fsha(base/"baseline.sarif")==bm["sarif_sha256"] and fsha(historical/"after.sarif")==hm["after_sarif_sha256"]
 result["checks"]["version"]=run([Q,"version"],out/"version.log",timeout=120)
 assert result["checks"]["version"]["exit"]==0 and "2.25.6" in (out/"version.log").read_text()
 with tempfile.TemporaryDirectory(prefix="archgen_"+case+"_") as temp:
  repo=Path(temp)/"repo";repo.mkdir();count=0
  with zipfile.ZipFile(zipfile_path) as z:
   assert z.testzip() is None
   for f in z.infolist():
    if f.is_dir() or not f.filename.startswith("REPO/"):continue
    rel=f.filename[5:];pr=Path(rel)
    assert rel and not pr.is_absolute() and ".." not in pr.parts and "\\" not in rel
    assert ((f.external_attr>>16)&0o170000)!=stat.S_IFLNK
    dest=repo/pr;dest.parent.mkdir(parents=True,exist_ok=True)
    with z.open(f) as src,dest.open("xb") as d:shutil.copyfileobj(src,d)
    count+=1
  assert count==c["files"]
  result["source_files"]=count
  result["checks"]["apply_check"]=run(["git","apply","--check",patch],out/"apply_check.log",repo,120)
  if result["checks"]["apply_check"]["exit"]!=0:result["status"]="APPLY_CHECK_FAILED"
  else:
   result["checks"]["apply"]=run(["git","apply",patch],out/"apply.log",repo,120)
   if result["checks"]["apply"]["exit"]!=0:result["status"]="PATCH_APPLY_FAILED"
   else:
    db=Path(temp)/"db"
    result["checks"]["db_create"]=run([Q,"database","create",db,"--language=javascript","--source-root="+str(repo),"--threads=4","--ram=12000"],out/"db_create.log")
    if result["checks"]["db_create"]["exit"]!=0:result["status"]="CODEQL_DB_FAILED"
    else:
     after=out/"after.sarif"
     result["checks"]["analysis"]=run([Q,"database","analyze",db,SUITE,"--format=sarifv2.1.0","--output="+str(after),"--threads=4","--ram=12000"],out/"analysis.log")
     if result["checks"]["analysis"]["exit"]!=0 or not after.exists():result["status"]="CODEQL_ANALYSIS_FAILED"
     else:
      bc,bd=signature(base/"baseline.sarif");hc,hd=signature(historical/"after.sarif");cc,cd=signature(after)
      assert sum(bc.values())==c["baseline"] and sum(hc.values())==c["historical"]
      new=cc-bc;hn=hc-bc;retained=hn&new
      (out/"warning_delta.json").write_text(json.dumps({"identity":"line-agnostic (ruleId,path,normalized message) multiset","new":pretty(new,cd),"historical_p1_new":pretty(hn,hd),"historical_remaining":pretty(retained,cd),"historical_absent":pretty(hn-new,hd),"new_not_historical":pretty(new-hn,cd)},indent=2)+"\n")
      result.update(status="CODEQL_SCAN_COMPLETE",codeql_version="2.25.6",baseline_total=sum(bc.values()),historical_p1_total=sum(hc.values()),historical_p1_new=sum(hn.values()),after_total=sum(cc.values()),new_vs_baseline=sum(new.values()),historical_p1_remaining=sum(retained.values()),historical_p1_absent=sum((hn-new).values()),new_not_historical=sum((new-hn).values()),new_by_rule={rule:sum(v for (r,_,_),v in new.items() if r==rule) for rule in sorted({k[0] for k in new})},after_sarif_sha256=fsha(after))
except Exception as e:result.update(status="ERROR",error_type=type(e).__name__,error_message=str(e))
finally:
 result["finished_utc"]=datetime.now(timezone.utc).isoformat()
 (out/"RESULT.json").write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps(result,indent=2),flush=True)
