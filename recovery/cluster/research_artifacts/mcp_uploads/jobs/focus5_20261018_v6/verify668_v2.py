#!/usr/bin/env python3
"""Differential BASE/O1/O2 environment-aware evaluation. Researcher-only, no W/P."""
from pathlib import Path,PurePosixPath
from contextlib import contextmanager
import os,json,hashlib,zipfile,subprocess,shutil,tempfile,time,importlib.util,re,sys
R=Path.home()/"research_artifacts/prevention_pilot_phase2"
STAGE=Path.home()/"research_artifacts/mcp_uploads/jobs/focus5_20261018_v6"
spec=importlib.util.spec_from_file_location("frozen_acceptance",STAGE/"acceptance_v2.py")
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
IDS=[668]
out=R/("focus5_668_acceptance_v2_job"+os.environ["SLURM_JOB_ID"]);out.mkdir(exist_ok=False)
root=R/"focus5_668_acceptance_v2_scratch";root.mkdir(exist_ok=True)
disk=os.statvfs(root)
assert disk.f_bavail*disk.f_frsize>65*1024**3,"INSUFFICIENT_SCRATCH_SPACE"
shared=Path(tempfile.mkdtemp(prefix="env5_shared_",dir=root))
def h(p):
 x=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(8*1024*1024),b""):x.update(b)
 return x.hexdigest()
def save(p,obj):p.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+"\n")
def sanitized_env(tmp,cid):
 env={k:v for k,v in os.environ.items() if not any(t in k.upper() for t in ("TOKEN","PASSWORD","SECRET","PRIVATE_KEY","API_KEY","GITHUB_","AWS_","AZURE_","GOOGLE_APPLICATION_","HF_","HUGGING","WANDB_","OPENAI_","SLACK_","SSH_","ANTHROPIC_","GCP_","CREDENTIAL","COOKIE","HTTP_PROXY","HTTPS_PROXY","ALL_PROXY"))}
 env["HOME"]=str(tmp/"home");Path(env["HOME"]).mkdir(parents=True)
 env["XDG_CACHE_HOME"]=str(shared/"xdg");env["XDG_DATA_HOME"]=str(shared/"xdg-data")
 env["COREPACK_HOME"]=str(shared/"corepack")
 env["COREPACK_ENABLE_AUTO_PIN"]="0";env["COREPACK_ENABLE_DOWNLOAD_PROMPT"]="0"
 env["npm_config_cache"]=str(shared/"npm-cache")
 env["npm_config_audit"]="false";env["npm_config_fund"]="false";env["npm_config_ignore_scripts"]="true";env["npm_config_update_notifier"]="false"
 env["CI"]="1";env["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"]="1";env["PUPPETEER_SKIP_DOWNLOAD"]="1";env["HUSKY"]="0";env["GIT_TERMINAL_PROMPT"]="0"
 env["VERITAS_DISABLE_WATCHERS"]="1"
 bin_path=Path.home()/"tools/node24/bin" if cid in (6104,22223) else Path.home()/"tools/node22/bin" if cid==3581 else Path.home()/"tools/node/bin"
 env["PATH"]=str(bin_path)+":"+str(Path.home()/"tools/node/bin")+":"+str(Path.home()/".bun/bin")+":/usr/local/bin:/usr/bin:/bin"
 return env
def cmd(label,argv,cwd,env,dir,checks,timeout):
 log=dir/(label+".log");beg=time.time()
 args=[str(x) for x in argv]
 try:
  with log.open("w") as f:
   s=subprocess.run(args,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,text=True,timeout=timeout)
  rc=s.returncode
 except subprocess.TimeoutExpired:rc=124
 except Exception as e:rc=127;log.write_text("EXCEPTION: "+repr(e))
 try: tail=log.read_text(errors="replace")[-950:]
 except:tail=""
 row={"name":label,"argv":args,"rc":rc,"seconds":round(time.time()-beg,2),"log":str(log),"tail":tail}
 checks.append(row)
 print("CHECK",dir.name,label,rc,round(time.time()-beg,1),flush=True)
 return rc
def apply_patch(rootdir,patch,checks,env,dest):
 if cmd("patch_check",["git","apply","--check",patch],rootdir,env,dest,checks,120)!=0:return False
 return cmd("patch_apply",["git","apply",patch],rootdir,env,dest,checks,120)==0
def archive_extract(archive,dest):
 cnt=0;total=0
 with zipfile.ZipFile(archive) as z:
  for f in z.infolist():
   if not f.filename.startswith("REPO/") or f.is_dir():continue
   rel=PurePosixPath(f.filename).parts
   if ".." in rel or len(rel)<2:raise ValueError("UNSAFE_ARCHIVE")
   cnt+=1;total+=f.file_size
   if cnt>80000 or total>900*1024**2:raise ValueError("SOURCE_EXTRACTION_LIMIT")
   dst=dest.joinpath(*rel[1:]);dst.parent.mkdir(parents=True,exist_ok=True)
   dst.write_bytes(z.read(f))
 return cnt
def toolcheck(cid,env,repo,dest,checks):
 exe=["node","--version"];cmd("node_version",exe,repo,env,dest,checks,15)
 for choice in ("bun","corepack"):
  cmd(choice+"_version",[choice,"--version"],repo,env,dest,checks,30)
 if cid in (6104,22223):cmd("pnpm_version",["corepack","pnpm","--version"],repo,env,dest,checks,150)
def install_and_test(cid,repo,env,dest,checks):
 result={"installation":"UNATTEMPTED","checks_selected":[]}
 if cid in (668,3581):
  inst=["npm","ci","--ignore-scripts","--no-audit","--no-fund","--prefer-offline"]
 elif cid==8152:
  inst=["bun","install","--frozen-lockfile","--ignore-scripts"]
 else:
  inst=["corepack","pnpm","install","--frozen-lockfile","--ignore-scripts","--prefer-offline"]
 irc=cmd("dependency_install",inst,repo,env,dest,checks,1200)
 result["installation"]="PASS" if irc==0 else "FAIL"
 if irc!=0:return result
 if cid==3581:
  nested=repo/"src/webview"
  npm_args=["npm","ci" if (nested/"package-lock.json").is_file() else "install",
   "--ignore-scripts","--no-audit","--no-fund","--prefer-offline"]
  sub=cmd("webview_install",npm_args,nested,env,dest,checks,1100)
  result["webview_install"]="PASS" if sub==0 else "FAIL"
 scripts={
   668:[("build",["npm","run","build"],660),
        ("existing_hud_render",["npm","run","test:run","--","src/__tests__/hud/render.test.ts","src/__tests__/hud/defaults.test.ts"],650)],
   8152:[("typecheck",["bun","run","typecheck"],500),
         ("existing_telegram_limits",["bunx","vitest","run","src/telegram/limits.test.ts"],500)],
   3581:[("extension_build",["npm","run","build:extension"],740),
         ("webview_build",["npm","run","build:webview"],740),
         ("webview_unit_tests",["npm","run","test:unit"],650)],
   6104:[("shared_build",["corepack","pnpm","--filter","@veritas-kanban/shared","build"],750),
         ("server_typecheck",["corepack","pnpm","--filter","@veritas-kanban/server","exec","tsc","--noEmit"],850),
         ("communication_adapter_tests",["corepack","pnpm","--filter","@veritas-kanban/server","exec","vitest","run","src/__tests__/communication-adapter-service.test.ts"],660)],
   22223:[("typecheck",["corepack","pnpm","run","typecheck"],750),
          ("browser_artifact_tests",["corepack","pnpm","exec","vitest","run","tests/browser/artifacts.test.ts"],660)]
 }
 for label,args,timeout in scripts[cid]:
  rc=cmd(label,args,repo,env,dest,checks,timeout)
  result["checks_selected"].append({"name":label,"rc":rc})
 if cid in module.TESTS:
  rel=module.PATHS[cid]
  code=module.TESTS[cid]
  tp=repo/rel;tp.parent.mkdir(parents=True,exist_ok=True)
  tp.write_text(code)
  result["frozen_acceptance_sha256"]=hashlib.sha256(code.encode()).hexdigest()
  result["frozen_acceptance_path"]=rel
  tests=["npm","run","test:run","--",rel] if cid==668 else ["bunx","vitest","run",rel]
  t=cmd("FROZEN_TASK_ACCEPTANCE",tests,repo,env,dest,checks,700)
  result["checks_selected"].append({"name":"FROZEN_TASK_ACCEPTANCE","rc":t})
 return result
rows=[]
try:
 for cid in IDS:
  filename="CASE_%05d"%cid
  archive=R/"remaining65_archives_oct17_v1"/(filename+".zip")
  assert archive.is_file()
  for arm in ("BASE","O1","O2"):
   dest=out/(filename+"_"+arm);dest.mkdir()
   result={"case":cid,"arm":arm,"stage":"START","checks":[],"issue_task_complete":"NOT_ESTABLISHED",
    "archive_sha256":h(archive),"evaluator_sha256":h(STAGE/"acceptance.py")}
   target=Path(tempfile.mkdtemp(prefix="env_%05d_%s_"%(cid,arm),dir=root))
   try:
    repo=target/"repo";repo.mkdir()
    result["source_files"]=archive_extract(archive,repo)
    env=sanitized_env(target,cid)
    basepath=None
    if arm!="BASE":
     basepath=R/("screen65_static_analysis_job70606" if arm=="O1" else "screen65_second_20261018_v1")/"patches"/(filename+".patch")
     manifest=json.loads((R/("screen65_static_analysis_job70606" if arm=="O1" else "screen65_second_20261018_v1")/"TRANSFER_MANIFEST.json").read_text())
     expected=next(v["sha256"] for v in manifest["patches"] if v["case_id"]==cid)
     assert h(basepath)==expected
     result["patch_sha256"]=expected
     if not apply_patch(repo,basepath,result["checks"],env,dest):
      result["stage"]="PATCH_APPLY_FAILED";save(dest/"RESULT.json",result);continue
    toolcheck(cid,env,repo,dest,result["checks"])
    result["environment"]={"node_path":env["PATH"].split(":")[0],"Node_version":next((x["tail"] for x in result["checks"] if x["name"]=="node_version"),"unknown"),
      "npm_or_pnpm":("corepack-pnpm" if cid in (6104,22223) else "bun" if cid==8152 else "npm"),"scripts_disabled_on_install":True}
    result["checks_result"]=install_and_test(cid,repo,env,dest,result["checks"])
    result["stage"]="EVALUATED" if result["checks_result"]["installation"]=="PASS" else "DEPENDENCIES_FAILED"
    save(dest/"RESULT.json",result)
    rows.append({"case_id":cid,"arm":arm,"stage":result["stage"],"inst":result["checks_result"]["installation"],
     "checks":{i["name"]:i["rc"] for i in result["checks_result"]["checks_selected"]},"node_version":result["environment"]["Node_version"]})
   except Exception as e:
    result["stage"]="ERROR";result["error"]=repr(e)[:1300];save(dest/"RESULT.json",result)
    rows.append({"case_id":cid,"arm":arm,"stage":result["stage"],"error":repr(e)[:250]})
   finally:
    shutil.rmtree(target,ignore_errors=True)
   print("ARM_COMPLETED",cid,arm,result["stage"],flush=True)
finally:
 save(out/"SUMMARY.json",{"rows":rows,"total_expected":15,"actual":len(rows),
  "notes":["BASE and O patches evaluated in fresh isolated trees with matching install strategy",
           "Task acceptance probes are independent of historical warnings and were written before this run",
           "No generated outputs altered; W/P generation not performed",
           "Generic unit tests/builds do not alone establish full issue-level acceptance"]})
 shutil.rmtree(shared,ignore_errors=True)
print("EVAL5_COMPLETE",len(rows),out,flush=True)
