#!/usr/bin/env python3
"""Offline design-adaptive smoke for case 22223 only; not confirmatory."""
from pathlib import Path,PurePosixPath
import os,json,hashlib,subprocess,tempfile,zipfile,shutil,time,importlib.util
R=Path.home()/"research_artifacts/prevention_pilot_phase2"
P=Path.home()/"research_artifacts/mcp_uploads/jobs/focus5_20261018_v5"
s=importlib.util.spec_from_file_location("t",P/"artifact_smoke_test.py");m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
out=R/("focus5_browser_smoke_job"+os.environ["SLURM_JOB_ID"]);out.mkdir(exist_ok=False)
sr=R/"focus5_browser_smoke_scratch";sr.mkdir(exist_ok=True)
scratch=Path(tempfile.mkdtemp(prefix="browser_smoke_",dir=sr))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def cmd(tag,args,cwd,env,dest,timeout):
 t=time.time()
 log=dest/(tag+".log")
 try:
  with log.open("w") as f:
   x=subprocess.run(list(map(str,args)),cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  rc=x.returncode
 except subprocess.TimeoutExpired:rc=124
 except Exception as e:rc=127;log.write_text(repr(e))
 return {"label":tag,"rc":rc,"sec":round(time.time()-t,1),"log_tail":log.read_text(errors="replace")[-1400:]}
try:
 for arm in ("BASE","O1","O2"):
  dest=out/arm;dest.mkdir()
  repo=scratch/("repo_"+arm);repo.mkdir()
  source=R/"remaining65_archives_oct17_v1/CASE_22223.zip"
  with zipfile.ZipFile(source) as z:
   for f in z.infolist():
    if not f.filename.startswith("REPO/") or f.is_dir():continue
    parts=PurePosixPath(f.filename).parts
    if ".." in parts:raise ValueError("unsafe source member")
    target=repo.joinpath(*parts[1:]);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(f))
  env={k:v for k,v in os.environ.items() if not any(t in k.upper() for t in ("PASSWORD","TOKEN","SECRET","API_KEY","PRIVATE_KEY","OPENAI_","AWS_","SSH_","COOKIE","GOOGLE_APPLICATION_","GITHUB_","GCP_","AZURE_","ANTHROPIC_","HTTP_PROXY","HTTPS_PROXY","ALL_PROXY"))}
  home=scratch/("home_"+arm);home.mkdir()
  env.update({"HOME":str(home),"PATH":str(Path.home()/"tools/node24/bin")+":"+str(Path.home()/"tools/node/bin")+":"+str(Path.home()/".bun/bin")+":/usr/bin:/bin",
   "COREPACK_HOME":str(scratch/"corepack"),"COREPACK_ENABLE_AUTO_PIN":"0","COREPACK_ENABLE_DOWNLOAD_PROMPT":"0",
   "CI":"1","HUSKY":"0","npm_config_ignore_scripts":"true","npm_config_cache":str(scratch/"npmcache"),
   "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD":"1","PUPPETEER_SKIP_DOWNLOAD":"1","GIT_TERMINAL_PROMPT":"0"})
  status={"arm":arm,"stage":"START","checks":[],"acceptance_type":"EXPLORATORY_ARCHITECTURE_ADAPTIVE","test_sha256":hashlib.sha256(m.TEST.encode()).hexdigest()}
  if arm!="BASE":
   stage=R/("screen65_static_analysis_job70606" if arm=="O1" else "screen65_second_20261018_v1")
   patch=stage/"patches/CASE_22223.patch"
   manifest=json.loads((stage/"TRANSFER_MANIFEST.json").read_text())
   expected=next(x["sha256"] for x in manifest["patches"] if x["case_id"]==22223)
   assert sha(patch)==expected
   status["patch_sha256"]=expected
   for tag,op in (("patch_check",["git","apply","--check",patch]),("patch_apply",["git","apply",patch])):
    c=cmd(tag,op,repo,env,dest,120);status["checks"].append(c)
    if c["rc"]:status["stage"]="PATCH_FAILED";break
  if status["stage"]!="PATCH_FAILED":
   inst=cmd("install",["corepack","pnpm","install","--frozen-lockfile","--ignore-scripts","--prefer-offline"],repo,env,dest,800)
   status["checks"].append(inst)
   if inst["rc"]:status["stage"]="INSTALL_FAILED"
   else:
    target=repo/m.REL;target.parent.mkdir(exist_ok=True);target.write_text(m.TEST)
    case=cmd("task_smoke",["corepack","pnpm","exec","vitest","run",m.REL],repo,env,dest,600)
    status["checks"].append(case)
    status["stage"]="SMOKE_PASS" if case["rc"]==0 else "SMOKE_FAIL"
  (dest/"RESULT.json").write_text(json.dumps(status,indent=2)+"\n")
  print("BROWSER_SMOKE",arm,status["stage"],flush=True)
finally:
 shutil.rmtree(scratch,ignore_errors=True)
print("BROWSER_SMOKE_COMPLETE",out)
