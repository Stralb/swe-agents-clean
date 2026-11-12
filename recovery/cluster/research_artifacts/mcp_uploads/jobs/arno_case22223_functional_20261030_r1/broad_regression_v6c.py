#!/usr/bin/env python3
"""Functional verification of case 22223; isolated copies and no package lifecycle scripts."""
from pathlib import Path
from zipfile import ZipFile
import os,sys,subprocess,hashlib,shutil,json,tempfile,time,stat
R=Path.home()/"research_artifacts"
O=R/"mcp_uploads/jobs/arno_case22223_functional_20261030_r1"
SRC=R/"mcp_uploads/jobs/arno_v6_20261030_case22223_three_pilots/ready/ARNO_22223_A_MECHANISM_UPLOAD.zip"
EVAL=R/"mcp_uploads/jobs/arno_case22223_three_arm_eval_20261030_r1/results2"
NODE=Path.home()/"tools/node24/bin/node"
PNPM=Path.home()/".cache/node/corepack/v1/pnpm/10.20.0/bin/pnpm.cjs"
TIMESTAMP=time.time()
result={"status":"STARTED","node24":str(NODE),"pnpm":str(PNPM),"started_epoch":TIMESTAMP,"arms":{},"commands":[]}
assert NODE.exists() and PNPM.exists()
def run(argv,cwd,env,logname,timeout=180):
 log=O/logname
 start=time.monotonic()
 with log.open("w") as f:
  try:
   p=subprocess.run([str(x) for x in argv],cwd=cwd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout,env=env)
   out={"exit":p.returncode,"seconds":round(time.monotonic()-start,2),"log":log.name}
  except subprocess.TimeoutExpired:out={"exit":124,"seconds":round(time.monotonic()-start,2),"log":log.name,"timeout":True}
 result["commands"].append({"argv":list(map(str,argv)),"cwd_name":Path(cwd).name,**out})
 print(json.dumps({"cmd":list(map(str,argv[:4])),"cwd_name":Path(cwd).name,**out}),flush=True)
 return out
def extract(repo):
 repo.mkdir(parents=True,exist_ok=False)
 with ZipFile(SRC) as z:
  assert z.testzip() is None
  for i in z.infolist():
   if i.is_dir() or not i.filename.startswith("REPO/"):continue
   n=i.filename[5:];p=Path(n)
   assert not p.is_absolute() and ".." not in p.parts and "\\" not in n
   assert ((i.external_attr>>16)&0o170000)!=stat.S_IFLNK
   dest=repo/n;dest.parent.mkdir(parents=True,exist_ok=True)
   with z.open(i) as src,dest.open("xb") as o:shutil.copyfileobj(src,o)
def target(arm,root,env,linked=None):
 repo=root/arm
 extract(repo)
 patch=EVAL/arm/"PATCH.patch"
 ap=run(["git","apply","--check",patch],repo,env,f"f_verify4_{arm}_apply_check.log",30)
 if ap["exit"]==0:ap=run(["git","apply",patch],repo,env,f"f_verify4_{arm}_apply.log",30)
 state={"apply_pass":ap["exit"]==0}
 if not state["apply_pass"]:return repo,state
 if linked is not None:(repo/"node_modules").symlink_to(linked,target_is_directory=True)
 for rel in ("src/browser/chatgptFiles.ts","tests/browser/chatgptFiles.test.ts"):
  source=repo/rel
  if source.exists():
   x=run([NODE,"--check",source],repo,env,f"f_verify4_{arm}_{source.name}.log",30)
   state["syntax_"+source.name]=x["exit"]
 return repo,state
try:
 with tempfile.TemporaryDirectory(prefix="arno22223_types_",dir=str(O)) as td:
  root=Path(td)
  env={k:v for k,v in os.environ.items() if k in {"PATH","LANG","LC_ALL","TMPDIR","SLURM_JOB_ID","SLURM_CPUS_PER_TASK"}}
  env.update({"HOME":str(root),"PATH":str(NODE.parent)+":/usr/bin:/bin","CI":"true","COREPACK_ENABLE_PROJECT_SPEC":"0",
   "COREPACK_ENABLE_AUTO_PIN":"0","COREPACK_ENABLE_NETWORK":"0","npm_config_ignore_scripts":"true",
   "npm_config_registry":"https://registry.npmjs.org","PNPM_STORE_DIR":str(root/"pnpm_store")})
  b_repo,b=target("B",root,env)
  result["arms"]["B"]=b
  run([NODE,"--version"],b_repo,env,"f_verify4_node24_version.log",15)
  version=run([NODE,PNPM,"--version"],b_repo,env,"f_verify4_pnpm_version.log",45)
  if version["exit"]==0:
   install=run([NODE,PNPM,"install","--frozen-lockfile","--ignore-scripts","--config.manage-package-manager-versions=false"],b_repo,env,"f_verify4_install.log",480)
   result["install"]=install
   if install["exit"]==0:
    for arm in ("A","C"):
     repo,s=target(arm,root,env,linked=b_repo/"node_modules")
     result["arms"][arm]=s
    for arm in ("A","B","C"):
     repo=root/arm
     c=run([NODE,PNPM,"exec","tsgo","--noEmit"],repo,env,f"f_verify4_{arm}_typecheck.log",180)
     result["arms"][arm]["typecheck"]=c["exit"]
     tests=["tests/browser/artifacts.test.ts","tests/browser/chatgptImages.test.ts","tests/browser/index.test.ts","tests/browser/sessionRunner.test.ts","tests/cli/renderOutput.test.ts","tests/sessionManager.test.ts"] + (["tests/browser/chatgptFiles.test.ts"] if arm!="C" else [])
     x=run([NODE,PNPM,"exec","vitest","run",*tests],repo,env,f"f_verify4_{arm}_vitest.log",180)
     result["arms"][arm]["vitest"]=x["exit"]
     build=run([NODE,PNPM,"exec","tsgo","-p","tsconfig.build.json"],repo,env,f"f_verify4_{arm}_build_tsgo.log",180)
     result["arms"][arm]["build_tsgo"]=build["exit"]
  if not result.get("install",{}).get("exit")==0:
   for arm in ("A","C"):
    repo,s=target(arm,root,env)
    result["arms"][arm]=s
  result["status"]="FINISHED_WITH_RESULTS"
except Exception as e:result.update(status="ERROR",error=repr(e))
finally:
 result["finished_epoch"]=time.time()
 (O/"BROAD_REGRESSION_RESULTS_V6C.json").write_text(json.dumps(result,indent=2))
 print(json.dumps({"status":result["status"],"install":result.get("install"),"arms":result["arms"],"error":result.get("error")},indent=2),flush=True)
