#!/usr/bin/env python3
from pathlib import Path
from collections import Counter
import json,hashlib,zipfile,tempfile,subprocess,os,sys,shutil,stat,runpy,datetime
R=Path.home()/"research_artifacts"
D=R/"mcp_uploads/jobs/arno_case22223_three_arm_eval_20261030_r1"
B=R/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results/CASE_22223"
Z=R/"mcp_uploads/jobs/arno_v6_20261030_case22223_three_pilots/ready"
suite="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
metadata={"A":("PILOT22223_MECHANISM_R1","ARNO_22223_A_MECHANISM_UPLOAD.zip","70231c04cc604219793d62f162fdcfffb86805f373abe551ec587469ca99e62b","9809b3c87b4b908abadd46faf2de6310517b98b9c370ca5fda6066e1b2e43c2b"),"B":("PILOT22223_BLIND_REPAIR_R1","ARNO_22223_B_BLIND_REVIEW_UPLOAD.zip","6908da2062a6ee0a68a1a7a0ef095ab84f7caf8f7d82f144424f0e858d1ca551","0adc6f63670ec90203e741cc7f375b72879d123a157c0efbc62ec44a3983a848"),"C":("PILOT22223_PROSPECTIVE_BUILD_R1","ARNO_22223_C_PROSPECTIVE_RISKS_UPLOAD.zip","6ab14df3b02ce3644038aef31f4fddc5fb9237a8f0898b8f80742393924bc2c8","71ccef7cd0b1289d4784219465fa8c3aa429d362a7f728f85bcd6e5137a938ba")}
def sha(x):return hashlib.sha256(x).hexdigest()
def load(name):return runpy.run_path(str(D/("in_"+name+".py")))["DATA"]
def sarif(p):
 d=json.loads(p.read_text());o=Counter()
 for run in d["runs"]:
  for v in run.get("results",[]):
   loc=v.get("locations",[]);ph=loc[0].get("physicalLocation",{}) if loc else {}
   key=(v.get("ruleId",""),ph.get("artifactLocation",{}).get("uri","").replace("\\","/")," ".join((v.get("message",{}).get("text") or "").split()))
   o[key]+=1
 return o
def cmd(args,log,cwd=None):
 with log.open("w") as f:return subprocess.run(list(map(str,args)),cwd=cwd,stdout=f,stderr=subprocess.STDOUT).returncode
def main(arm):
 rid,zname,zsha,psha=metadata[arm];out=D/"results"/arm;out.mkdir(parents=True,exist_ok=False)
 result={"arm":arm,"run_id":rid,"functional_status":"NOT_TESTED","status":"STARTED","started_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  indexes=["A_alt","A_001"] if arm=="A" else ([f"B_{i:03d}" for i in range(3)] if arm=="B" else [f"C_{i:03d}" for i in range(3)])
  patch="".join(load(n) for n in indexes).encode()
  assert sha(patch)==psha,(sha(patch),psha)
  receipt=load("r"+arm.lower()+"_alt").encode()
  rec=json.loads(receipt)
  assert rec["run_id"]==rid
  if arm=="B":
   review=load("review_alt2").encode()
   assert sha(review)==rec["review_sha256"]
   (out/"REVIEW.json").write_bytes(review)
  if arm=="C":
   risk=load("risks_alt").encode()
   assert sha(risk)==rec["prediction_report_sha256"]
   (out/"RISKS.json").write_bytes(risk)
  (out/"PATCH.patch").write_bytes(patch);(out/"RECEIPT.json").write_bytes(receipt)
  result.update(patch_sha256=sha(patch),receipt_sha256=sha(receipt))
  source=Z/zname; assert sha(source.read_bytes())==zsha
  prior=json.loads((B/"RESULT.json").read_text())
  assert prior["status"]=="BASELINE_CODEQL_COMPLETE" and prior["result_count"]==41
  assert sha((B/"baseline.sarif").read_bytes())==prior["sarif_sha256"]
  q=Path.home()/"tools/codeql/codeql";assert q.is_file()
  with tempfile.TemporaryDirectory(prefix="arno_22223_"+arm+"_") as t:
   repo=Path(t)/"repo";repo.mkdir()
   with zipfile.ZipFile(source) as z:
    entries=[i for i in z.infolist() if i.filename.startswith("REPO/") and not i.is_dir()]
    assert len(entries)==401
    for i in entries:
     n=i.filename[5:];p=Path(n)
     assert not p.is_absolute() and ".." not in p.parts and "\\" not in n
     assert ((i.external_attr>>16)&0o170000)!=stat.S_IFLNK
     dest=repo/n;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(i))
   pth=out/"PATCH.patch"
   result["git_apply_check_exit"]=cmd(["git","apply","--check",pth],out/"apply_check.log",repo)
   assert result["git_apply_check_exit"]==0
   result["git_apply_exit"]=cmd(["git","apply",pth],out/"apply.log",repo)
   assert result["git_apply_exit"]==0
   db=Path(t)/"database"
   result["database_create_exit"]=cmd([q,"database","create",db,"--language=javascript","--source-root="+str(repo),"--threads=4","--ram=12000"],out/"codeql_create.log")
   assert result["database_create_exit"]==0
   result["codeql_analysis_exit"]=cmd([q,"database","analyze",db,suite,"--format=sarifv2.1.0","--output="+str(out/"after.sarif"),"--threads=4","--ram=12000"],out/"codeql_analyze.log")
   assert result["codeql_analysis_exit"]==0
  before=sarif(B/"baseline.sarif");after=sarif(out/"after.sarif");news=after-before
  result.update(status="CODEQL_SCAN_COMPLETE",baseline_total=sum(before.values()),after_total=sum(after.values()),new_line_agnostic=sum(news.values()),new_by_rule=dict(Counter({rule:sum(v for (r,p,m),v in news.items() if r==rule) for rule,_,_ in news})),removed_line_agnostic=sum((before-after).values()),sarif_sha256=sha((out/"after.sarif").read_bytes()))
 except Exception as e:
  result.update(status="FAILED",error=repr(e))
 finally:
  result["finished_utc"]=datetime.datetime.now(datetime.timezone.utc).isoformat()
  (out/"RESULT.json").write_text(json.dumps(result,indent=2))
  print(json.dumps(result),flush=True)
if __name__=="__main__":main(sys.argv[1])
