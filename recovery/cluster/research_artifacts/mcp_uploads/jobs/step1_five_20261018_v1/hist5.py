#!/usr/bin/env python3
import os,json,zipfile,hashlib,subprocess,time,tempfile,shutil
from pathlib import Path,PurePosixPath
from collections import Counter
R=Path.home()/"research_artifacts/prevention_pilot_phase2"
ids=[668,3581,6104,8152,22223]
cid=ids[int(os.environ["SLURM_ARRAY_TASK_ID"])]
out=R/("hist5_codeql_job"+os.environ["SLURM_ARRAY_JOB_ID"])/("CASE_%05d"%cid)
out.mkdir(parents=True,exist_ok=False)
result={"case_id":cid,"stage":"START","checks":{},"suite":"codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"}
def save(): (out/"RESULT.json").write_text(json.dumps(result,indent=2)+"\n")
def run(tag,cmd,cwd,timeout):
 t=time.time()
 try:
  with (out/(tag+".log")).open("w") as f:
   p=subprocess.run([str(a) for a in cmd],cwd=cwd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  result["checks"][tag]={"exit":p.returncode,"secs":round(time.time()-t,1)};save()
  if p.returncode:raise RuntimeError(tag+"_FAILED")
 except subprocess.TimeoutExpired:
  result["checks"][tag]={"exit":124};save();raise
def sarif(q):
 z=json.loads(q.read_text());out=[]
 for r in z.get("runs",[]):
  for v in r.get("results",[]):
   loc=(v.get("locations") or [{}])[0].get("physicalLocation",{})
   out.append({"rule":v.get("ruleId",""),"path":loc.get("artifactLocation",{}).get("uri",""),"line":loc.get("region",{}).get("startLine"),"msg":v.get("message",{}).get("text",""),"fp":v.get("partialFingerprints") or {}})
 return out
def diff(before,after):
 def key(x):return (x["rule"],x["path"],x["fp"].get("primaryLocationLineHash") or x["msg"],x["fp"].get("primaryLocationStartColumnFingerprint") or "")
 count=Counter(key(v) for v in before);found=[]
 for v in after:
  k=key(v)
  if count[k]:count[k]-=1
  else:found.append(v)
 return found
save();scratch=None
try:
 name="CASE_%05d"%cid
 patch=R/"hist_pr_apply14_job70964"/name/"DATASET_PR_RECONSTRUCTED.patch"
 status=json.loads((R/"hist_pr_apply14_job70964"/name/"RESULT.json").read_text())
 assert status["status"]=="APPLIED"
 source=R/"remaining65_archives_oct17_v1"/(name+".zip")
 assert source.is_file()
 baseline=R/"screen65_codeql_job70675"/name/"before.sarif"
 assert baseline.is_file()
 result["baseline_sha256"]=hashlib.sha256(baseline.read_bytes()).hexdigest()
 result["historical_patch_sha256"]=hashlib.sha256(patch.read_bytes()).hexdigest()
 root=R/"step1_hist5_scratch"
 root.mkdir(exist_ok=True)
 disk=os.statvfs(root);assert disk.f_bavail*disk.f_frsize>60*1024**3
 scratch=Path(tempfile.mkdtemp(prefix="hist_%s_"%cid,dir=root))
 repo=scratch/"repo";repo.mkdir()
 with zipfile.ZipFile(source) as z:
  for f in z.infolist():
   if f.is_dir() or not f.filename.startswith("REPO/"):continue
   parts=PurePosixPath(f.filename).parts
   assert ".." not in parts
   target=repo.joinpath(*parts[1:]);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(f))
 run("applycheck",["git","apply","--check",patch],repo,180)
 run("apply",["git","apply",patch],repo,180)
 codeql=Path.home()/"tools/codeql/codeql"
 db=scratch/"db_hist"
 result["stage"]="DATABASE";save()
 run("database", [codeql,"database","create",db,"--language=javascript-typescript","--build-mode=none","--source-root="+str(repo),"--threads=4","--ram=24000"],repo,4000)
 result["stage"]="ANALYSIS";save()
 run("analyze",[codeql,"database","analyze",db,result["suite"],"--format=sarif-latest","--output",out/"historical_pr.sarif","--threads=4","--ram=24000"],repo,5000)
 pre=sarif(baseline);post=sarif(out/"historical_pr.sarif");fresh=diff(pre,post)
 desired=json.loads((R/"dual_o_audit14_job70958"/"cases"/(name+".json")).read_text())["historical_warnings"]
 d_rules={v["rule_id"] for v in desired if v["introduced"]}
 rulefile={(v["rule_id"],v["file_path"]) for v in desired if v["introduced"]}
 result["historical_replay"]={"baseline_findings":len(pre),"pr_findings":len(post),"strong_new":len(fresh),
  "selected_historical_rules":sorted(d_rules),
  "new_matching_rule":[{"rule":v["rule"],"path":v["path"],"line":v["line"],"msg":v["msg"][:220]} for v in fresh if v["rule"] in d_rules],
  "new_matching_rule_file":[{"rule":v["rule"],"path":v["path"],"line":v["line"]} for v in fresh if (v["rule"],v["path"]) in rulefile],
  "historic_rule_count":dict(Counter(v["rule"] for v in fresh))}
 result["stage"]="COMPLETE"
except Exception as e:result["stage"]="FAILED";result["error"]=repr(e)
finally:
 save()
 if scratch:shutil.rmtree(scratch,ignore_errors=True)
 print("HIST5",cid,result["stage"],result.get("historical_replay",{}).get("new_matching_rule_file"),result.get("error",""),flush=True)
