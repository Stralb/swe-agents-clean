#!/usr/bin/env python3
import os,json,zipfile,hashlib,subprocess,time,tempfile,shutil,re
from pathlib import Path,PurePosixPath
R=Path.home()/"research_artifacts/prevention_pilot_phase2"
ids=[668,3581,6104,8152,22223]
t=int(os.environ["SLURM_ARRAY_TASK_ID"]);cid=ids[t//2];attempt=1+t%2
name="CASE_%05d"%cid
out=R/("func5_o12_job"+os.environ["SLURM_ARRAY_JOB_ID"])/(name+"_O"+str(attempt))
out.mkdir(parents=True,exist_ok=False)
status={"case_id":cid,"attempt":"O"+str(attempt),"stage":"START","checks":[],"functional_acceptance":"NOT_ESTABLISHED"}
def save(): (out/"RESULT.json").write_text(json.dumps(status,indent=2)+"\n")
def run(label,cmd,working,env,timeout=300):
 started=time.time()
 try:
  p=subprocess.run([str(x) for x in cmd],cwd=working,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors="replace",timeout=timeout)
  rc=p.returncode;log=p.stdout
 except subprocess.TimeoutExpired as e:rc=124;log="TIMEOUT "+str(e)
 except Exception as e:rc=127;log="ERROR "+repr(e)
 (out/(label+".log")).write_text(log[-100000:])
 status["checks"].append({"label":label,"cmd":cmd,"exit_code":rc,"duration":round(time.time()-started,1),"log_tail":log[-600:]});save()
 return rc
save();scratch=None
try:
 stage=R/("screen65_static_analysis_job70606" if attempt==1 else "screen65_second_20261018_v1")
 manifest=json.loads((stage/"TRANSFER_MANIFEST.json").read_text())
 case=next(v for v in manifest["patches"] if v["case_id"]==cid)
 patch=stage/"patches"/(name+".patch")
 assert hashlib.sha256(patch.read_bytes()).hexdigest()==case["sha256"]
 source=R/"remaining65_archives_oct17_v1"/(name+".zip")
 assert source.exists()
 sr=R/"step1_func5_scratch";sr.mkdir(exist_ok=True)
 v=os.statvfs(sr);assert v.f_bavail*v.f_frsize>30*1024**3
 scratch=Path(tempfile.mkdtemp(prefix="func_%05d_O%d_"%(cid,attempt),dir=sr))
 repo=scratch/"repo";repo.mkdir()
 count=0;total=0
 with zipfile.ZipFile(source) as z:
  for f in z.infolist():
   if f.is_dir() or not f.filename.startswith("REPO/"):continue
   rel=PurePosixPath(f.filename).parts
   assert ".." not in rel and len(rel)>=2
   count+=1;total+=f.file_size
   assert count<40000 and total<750*1024*1024
   target=repo.joinpath(*rel[1:]);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(f))
 env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ("TOKEN","SECRET","PASSWORD","API_KEY","PRIVATE_KEY","GITHUB_","AWS_","HF_","WANDB_","SLACK_","SSH_","CODEX_","OPENAI_"))}
 env["PATH"]=str(Path.home()/"tools/node/bin")+":"+str(Path.home()/".bun/bin")+":"+env.get("PATH","/usr/bin:/bin")
 env["HOME"]=str(scratch/"home");Path(env["HOME"]).mkdir()
 env.update({"CI":"1","XDG_CACHE_HOME":str(scratch/"cache"),"npm_config_cache":str(scratch/"npmcache"),
 "npm_config_ignore_scripts":"true","npm_config_audit":"false","npm_config_fund":"false","PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD":"1",
 "PUPPETEER_SKIP_DOWNLOAD":"1","HUSKY":"0","GIT_TERMINAL_PROMPT":"0"})
 for k in ("HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","NO_PROXY"):env.pop(k,None)
 assert run("patch_check",["git","apply","--check",patch],repo,env,120)==0
 assert run("patch_apply",["git","apply",patch],repo,env,120)==0
 status["stage"]="PATCH_APPLIED";status["source_files"]=count;status["patch_sha256"]=case["sha256"];save()
 node=shutil.which("node",path=env["PATH"]);npm=shutil.which("npm",path=env["PATH"])
 bun=shutil.which("bun",path=env["PATH"]);pnpm=shutil.which("pnpm",path=env["PATH"])
 status["tools"]={"node":bool(node),"npm":bool(npm),"bun":bool(bun),"pnpm":bool(pnpm)}
 rootpkg=repo/"package.json"
 pkg=json.loads(rootpkg.read_text()) if rootpkg.exists() else {}
 scripts=pkg.get("scripts") or {}
 status["root_scripts_selected"]={k:v for k,v in scripts.items() if any(w in k for w in ("test","typecheck","build")) and len(v)<450}
 save()
 if node:
  status["node_version_return"]=run("node_version",["node","--version"],repo,env,30)
 check_paths={
  668:["src/hud/state.ts","src/hud/render.ts"],
  3581:["src/extension/services/terminal-execution-service.ts","src/webview/src/App.tsx"],
  6104:["server/src/services/communication-adapter-service.ts"],
  8152:["src/telegram/bridge.ts"],
  22223:["src/browser/chatgptFiles.ts"]
 }
 for path in check_paths[cid]:
  f=repo/path
  if f.is_file() and f.suffix in (".js",".mjs",".cjs") and node:
   run("syntax_"+f.name.replace(".","_"),["node","--check",f],repo,env,90)
 mode="NONE";runner=None;installer=None
 if pnpm and (repo/"pnpm-lock.yaml").exists():
  mode="PNPM";runner=["pnpm","run"];installer=["pnpm","install","--frozen-lockfile","--ignore-scripts","--prefer-offline"]
 elif npm and (repo/"package-lock.json").exists():
  mode="NPM_CI";runner=["npm","run"];installer=["npm","ci","--ignore-scripts","--no-audit","--no-fund","--prefer-offline"]
 elif bun and ((repo/"bun.lock").exists() or (repo/"bun.lockb").exists()):
  mode="BUN";runner=["bun","run"];installer=["bun","install","--frozen-lockfile","--ignore-scripts"]
 elif npm and rootpkg.is_file():
  mode="NPM";runner=["npm","run"];installer=["npm","install","--ignore-scripts","--no-audit","--no-fund","--prefer-offline"]
 status["install_mode"]=mode;save()
 if not installer:
  status["stage"]="ENVIRONMENT_BLOCKED";status["reason"]="No supported package manager/project root";save()
 else:
  irc=run("dependencies",installer,repo,env,800)
  if irc!=0:
   status["stage"]="DEPENDENCIES_FAILED";status["reason"]="Dependency install failed; cannot infer patch correctness";save()
  else:
   targets={668:["build","test:run"],3581:["build:extension","test:unit"],6104:["typecheck","test"],8152:["typecheck","test"],22223:["typecheck","test"]}
   preferred=targets[cid]
   selected=[]
   for script in preferred:
    if script in scripts:selected.append(script)
   # Do not run generic all-workspace test if no narrow route: bounded timeout only.
   for ix,script in enumerate(selected):
    rc=run("project_"+str(ix)+"_"+script.replace(":","_"),runner+[script],repo,env,600 if "test" in script else 700)
   status["stage"]="CHECKS_COMPLETE" if selected else "NO_USABLE_PROJECT_SCRIPTS"
   status["executed_project_scripts"]=selected
   status["functional_acceptance"]="NOT_ESTABLISHED_TASK_SPECIFIC_TESTS_REQUIRED"
   save()
except Exception as e:
 status["stage"]="ERROR";status["error"]=repr(e);save()
finally:
 if scratch:shutil.rmtree(scratch,ignore_errors=True)
 print("FUNC5",cid,attempt,status["stage"],[(r["label"],r["exit_code"]) for r in status["checks"]],status.get("error",""),flush=True)
