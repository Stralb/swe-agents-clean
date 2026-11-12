#!/usr/bin/env python3
"""User-provided 668 O/W/P patch evaluation on identical frozen repo and pinned CodeQL suite."""
from pathlib import Path,PurePosixPath
from collections import Counter
import os,json,hashlib,zipfile,subprocess,shutil,time,tempfile
ROOT=Path.home()/"research_artifacts"/"prevention_pilot_phase2"
OUT=ROOT/("owp668_user_patch_eval_job"+os.environ["SLURM_JOB_ID"])
OUT.mkdir(exist_ok=False,parents=True)
INPUT=Path.home()/"research_artifacts"/"mcp_uploads/owp14_20261018_v1"
CASES={
 "O":("USER_CASE_00668_O.txt","c6f5a1911fa4e9dd32d28f3e5044b66582633bf7f2f7e00f5fc89a66e34759d0"),
 "P":(("USER_CASE_00668_P_part1.txt","USER_CASE_00668_P_part2.txt"),"7ca14f657428fdd5314e3ca8adc82e089250559562dc1fd7c0479cac4146c68b"),
 "W":(("USER_CASE_00668_W_part1.txt","USER_CASE_00668_W_part2.txt"),"4b84fabd4247f2cac08d4aa38ad56a2a8d2282d638b397cc220e83c146a8808f")
}
SOURCE=ROOT/"remaining65_archives_oct17_v1/CASE_00668.zip"
BASE=ROOT/"screen65_codeql_job70675/CASE_00668/before.sarif"
assert SOURCE.exists() and BASE.exists()
base_sha=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
assert base_sha=="8a9d61fdeb8fc5b2be27638e0ebb4f6db8a7371c0eb3a3ace3bd2dfc72c25a6b"
def fresh(bef,aft):
 def get(z):
  ans=[]
  for run in z.get("runs",[]):
   for v in run.get("results",[]):
    loc=(v.get("locations") or [{}])[0].get("physicalLocation",{})
    ans.append({"rule":v.get("ruleId",""),"path":loc.get("artifactLocation",{}).get("uri",""),"line":loc.get("region",{}).get("startLine"),
     "message":v.get("message",{}).get("text",""),"fprints":v.get("partialFingerprints") or {}})
  return ans
 a=get(bef);b=get(aft)
 def key(z):return (z["rule"],z["path"],z["fprints"].get("primaryLocationLineHash") or z["message"],z["fprints"].get("primaryLocationStartColumnFingerprint") or "")
 ct=Counter(key(v) for v in a);new=[]
 for v in b:
  k=key(v)
  if ct[k]:ct[k]-=1
  else:new.append(v)
 return a,b,new
def safe_env(temp):
 env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ("TOKEN","SECRET","PASSWORD","API_KEY","PRIVATE_KEY","GITHUB_","AWS_","HF_","WANDB_","SLACK_","SSH_","CODEX_","OPENAI_"))}
 env["PATH"]=str(Path.home()/"tools/codeql")+":"+str(Path.home()/"tools/node/bin")+":"+str(Path.home()/".bun/bin")+":"+env.get("PATH","/usr/bin:/bin")
 env["HOME"]=str(temp/"home");Path(env["HOME"]).mkdir()
 env.update({"CI":"1","XDG_CACHE_HOME":str(temp/"cache"),"npm_config_cache":str(temp/"npmcache"),
 "npm_config_ignore_scripts":"true","npm_config_audit":"false","npm_config_fund":"false","PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD":"1",
 "PUPPETEER_SKIP_DOWNLOAD":"1","HUSKY":"0","GIT_TERMINAL_PROMPT":"0"})
 for k in ("HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","NO_PROXY"):env.pop(k,None)
 return env
def run(status,out,tag,cmd,cwd,env,timeout):
 st=time.time()
 try:
  with (out/(tag+".log")).open("w") as f:res=subprocess.run([str(x) for x in cmd],cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  rc=res.returncode
 except subprocess.TimeoutExpired:rc=124
 except Exception as e:
  rc=127;(out/(tag+".log")).write_text("EXCEPTION "+repr(e))
 status["checks"][tag]={"returncode":rc,"seconds":round(time.time()-st,2),"log":tag+".log"}
 (out/"RESULT.json").write_text(json.dumps(status,indent=2)+"\n")
 return rc
manifest={"source_zip_sha256":base_sha,"base_sarif_sha256":hashlib.sha256(BASE.read_bytes()).hexdigest(),"case_id":668,
 "conditions":{},"scanner_suite":"codeql/javascript-queries:codeql-suites/javascript-security-extended.qls",
 "target_rule":"js/file-system-race",
 "note":"Scanner-negative does not imply correct functionality. Issue-level acceptance and PR-time issue-body provenance unverified."}
for arm in ("O","W","P"):
 out=OUT/arm;out.mkdir()
 value,digest=CASES[arm]
 paths=[value] if isinstance(value,str) else list(value)
 patch_data=b"".join((INPUT/p).read_bytes() for p in paths)+b"\n"
 assert hashlib.sha256(patch_data).hexdigest()==digest,("PATCH_HASH_MISMATCH",arm)
 patch=out/("CASE_00668_"+arm+".patch");patch.write_bytes(patch_data)
 status={"case_id":668,"arm":arm,"patch_sha256":digest,"stage":"START","checks":{},"scanner_result":"UNRUN",
 "task_functionality":"NOT_PROVEN","test_scope":"existing project tests; no independent task acceptance oracle"}
 scratch=None
 try:
  scratchroot=ROOT/"owp668_user_eval_scratch";scratchroot.mkdir(exist_ok=True)
  fs=os.statvfs(scratchroot);assert fs.f_bavail*fs.f_frsize>60*1024**3
  scratch=Path(tempfile.mkdtemp(prefix="owp668_"+arm+"_",dir=scratchroot))
  repo=scratch/"repo";repo.mkdir()
  count=0;total=0
  with zipfile.ZipFile(SOURCE) as z:
   for f in z.infolist():
    if f.is_dir() or not f.filename.startswith("REPO/"):continue
    parts=PurePosixPath(f.filename).parts
    assert ".." not in parts and len(parts)>1
    count+=1;total+=f.file_size
    assert count<=60000 and total<850*1024*1024
    target=repo.joinpath(*parts[1:]);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(f))
  status["frozen_file_count"]=count
  env=safe_env(scratch)
  status["stage"]="PATCH_CHECK";(out/"RESULT.json").write_text(json.dumps(status,indent=2)+"\n")
  if run(status,out,"applycheck",["git","apply","--check",patch],repo,env,180):raise RuntimeError("PATCH_DOES_NOT_APPLY")
  if run(status,out,"apply",["git","apply",patch],repo,env,180):raise RuntimeError("PATCH_APPLICATION_FAILED")
  status["stage"]="PATCH_APPLIED"
  codeql=Path.home()/"tools/codeql/codeql";db=scratch/"db_after"
  status["stage"]="CODEQL"
  if run(status,out,"database",[codeql,"database","create",db,"--language=javascript-typescript","--build-mode=none",
        "--source-root="+str(repo),"--threads=4","--ram=24000"],repo,env,3100):raise RuntimeError("CODEQL_DATABASE_FAILED")
  if run(status,out,"analyze",[codeql,"database","analyze",db,manifest["scanner_suite"],
        "--format=sarif-latest","--output",out/"after.sarif","--threads=4","--ram=24000"],repo,env,3800):raise RuntimeError("CODEQL_ANALYSIS_FAILED")
  baseline,post,new=fresh(json.loads(BASE.read_text()),json.loads((out/"after.sarif").read_text()))
  status["new_alerts"]= [{k:v for k,v in a.items() if k in ("rule","path","line","message")} for a in new]
  status["new_alerts_by_rule"]=dict(Counter(x["rule"] for x in new))
  status["new_alert_count"]=len(new)
  status["new_historical_rule_alert_count"]=sum(x["rule"]=="js/file-system-race" for x in new)
  status["pre_codeql_count"]=len(baseline);status["after_codeql_count"]=len(post)
  status["scanner_result"]="COMPLETE"
  status["stage"]="FUNCTIONAL_CHECKS"
  i_rc=run(status,out,"dependency_install",["npm","ci","--ignore-scripts","--no-audit","--no-fund","--prefer-offline"],repo,env,800)
  if i_rc==0:
   build=run(status,out,"build",["npm","run","build"],repo,env,650)
   test=run(status,out,"focused_hud_tests",["npm","run","test:run","--","src/__tests__/hud"],repo,env,400)
   status["build_pass"]=build==0;status["focused_hud_tests_pass"]=test==0
  else:
   status["build_pass"]=None;status["focused_hud_tests_pass"]=None
  status["stage"]="COMPLETE"
 except Exception as e:
  status["stage"]="FAILED";status["error"]=repr(e)
 finally:
  (out/"RESULT.json").write_text(json.dumps(status,indent=2)+"\n")
  manifest["conditions"][arm]={"stage":status["stage"],"patch_sha256":digest,"scanner_result":status["scanner_result"],
   "new_alert_count":status.get("new_alert_count"),"target_alert_count":status.get("new_historical_rule_alert_count"),
   "build_pass":status.get("build_pass"),"focused_hud_tests_pass":status.get("focused_hud_tests_pass"),"error":status.get("error")}
  (OUT/"SUMMARY.json").write_text(json.dumps(manifest,indent=2)+"\n")
  if scratch:shutil.rmtree(scratch,ignore_errors=True)
  print("CASE_668_EVAL",arm,status["stage"],manifest["conditions"][arm],flush=True)
