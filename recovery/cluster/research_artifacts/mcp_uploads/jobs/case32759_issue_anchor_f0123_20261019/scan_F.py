#!/usr/bin/env python3
from pathlib import Path,PurePosixPath
from collections import Counter
import hashlib,json,os,zipfile,subprocess,tempfile,shutil,time,traceback
root=Path.home()/"research_artifacts"
source=root/"prevention_pilot_phase2/owp14_allcases_packets_job71014/CASE_32759_O.zip"
base_sarif=root/"prevention_pilot_phase2/case32759_fresh6_scan_job71754/base.sarif"
stage=root/"mcp_uploads/jobs/case32759_issue_anchor_f0123_20261019"
out=root/("prevention_pilot_phase2/case32759_issue_anchor_scans_job"+os.environ.get("SLURM_JOB_ID","unknown"))
out.mkdir(parents=True,exist_ok=False)
scanner=Path.home()/"tools/codeql/codeql"
suite="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
hashes={"F0":"5f1f5d25594bcb09c7fc768d800229551d105fdb288f18cd31d2bba1ad51d419","F1":"3a42d0f02b71f5f0139f7965a322828f9e4d6e699bd4adea8604a83cb5be4b0","F2":"cbcf683f08c1bb8c158d26eb4327d23feeab96ee35c14ba5161be3e06c381ba5","F3":"bc11ee45e6d9998329284dac34ead74b61a536342cbcc92109d261da09c8177e"}
assert hashlib.sha256(source.read_bytes()).hexdigest()=="2dce5a0132cadb85b779bcd032e81b5aadc95bfafce391e8437916fb400399f2"
assert base_sarif.is_file()
assert "2.25.6" in subprocess.check_output([str(scanner),"version"],text=True)
def cmd(label,argv,cwd):
 start=time.monotonic()
 with (out/(label+".log")).open("w") as f:
  p=subprocess.run([str(a) for a in argv],cwd=str(cwd),stdout=f,stderr=subprocess.STDOUT,timeout=2100)
 res={"returncode":p.returncode,"seconds":round(time.monotonic()-start,2)}
 if p.returncode:raise RuntimeError(label+" failed: "+str(res))
 return res
def scanrows(path):
 rows=[]
 for run in json.loads(path.read_text()).get("runs",[]):
  for x in run.get("results",[]):
   loc=(x.get("locations") or [{}])[0].get("physicalLocation",{})
   rows.append({"rule":x.get("ruleId",""),"path":loc.get("artifactLocation",{}).get("uri",""),"line":loc.get("region",{}).get("startLine"),"message":x.get("message",{}).get("text",""),"fp":x.get("partialFingerprints") or {}})
 return rows
def diff(before,after,strict):
 def key(x):
  if strict:return (x["rule"],x["path"],x["fp"].get("primaryLocationLineHash") or x["message"],x["fp"].get("primaryLocationStartColumnFingerprint") or "")
  return (x["rule"],x["path"],x["message"])
 old=Counter(map(key,before));ret=[]
 for r in after:
  k=key(r)
  if old[k]:old[k]-=1
  else:ret.append({z:v for z,v in r.items() if z!="fp"})
 return ret
scratch=Path(tempfile.mkdtemp(prefix="case32759_issueanch_",dir=os.environ.get("SLURM_TMPDIR") or "/tmp"))
before=scanrows(base_sarif)
rows=[]
try:
 repo=scratch/"baseline";repo.mkdir()
 with zipfile.ZipFile(source) as z:
  names=[i.filename for i in z.infolist() if i.filename.startswith("REPO/") and not i.is_dir()]
  assert len(names)==23
  for f in names:
   parts=PurePosixPath(f).parts
   assert len(parts)>1 and ".." not in parts
   target=repo.joinpath(*parts[1:]);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(f))
 for arm,expected in hashes.items():
  result={"case":32759,"arm":arm,"stage":"START","baseline_count":len(before),"suite":suite,"version":"2.25.6","functional_status":"NATIVE_WINDOWS_UNTESTED"}
  dest=out/arm;dest.mkdir()
  try:
   patch=dest/("CASE_32759_"+arm+".patch")
   result["stage_file"]=cmd(arm+"_stage",["python3",stage/("input_"+arm+".py"),patch],repo)
   assert hashlib.sha256(patch.read_bytes()).hexdigest()==expected,"PATCH_HASH_MISMATCH"
   candidate=scratch/arm;shutil.copytree(repo,candidate)
   result["applycheck"]=cmd(arm+"_check",["git","apply","--check",patch],candidate)
   result["apply"]=cmd(arm+"_apply",["git","apply",patch],candidate)
   result["nodecheck"]=cmd(arm+"_nodecheck",["node","--check",candidate/"skills/codex-delegate/scripts/relay.mjs"],candidate)
   result["help"]=cmd(arm+"_help",["node",candidate/"skills/codex-delegate/scripts/relay.mjs","--help"],candidate)
   db=scratch/(arm+"_db")
   result["db"]=cmd(arm+"_db",[scanner,"database","create",db,"--language=javascript-typescript","--build-mode=none","--source-root="+str(candidate),"--threads=3","--ram=10000"],candidate)
   sarif=dest/"after.sarif"
   result["scan"]=cmd(arm+"_scan",[scanner,"database","analyze",db,suite,"--format=sarif-latest","--output="+str(sarif),"--threads=3","--ram=10000"],candidate)
   after=scanrows(sarif)
   strong=diff(before,after,True);conservative=diff(before,after,False)
   result.update(stage="SCAN_COMPLETE",after_count=len(after),new_strong_count=len(strong),new_conservative_count=len(conservative),new_strong=strong,new_conservative=conservative)
  except Exception as e:
   result.update(stage="ERROR",error=repr(e),traceback=traceback.format_exc()[-2300:])
  (dest/"RESULT.json").write_text(json.dumps(result,indent=2)+"\n")
  rows.append(result)
  (out/"SUMMARY.json").write_text(json.dumps(rows,indent=2)+"\n")
  print(arm,result["stage"],result.get("new_strong_count"),result.get("error",""),flush=True)
finally:shutil.rmtree(scratch,ignore_errors=True)
