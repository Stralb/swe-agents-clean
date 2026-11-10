#!/usr/bin/env python3
"""Safety-sandboxed differential JSONL watcher test for case 03581. Never run unsandboxed."""
from pathlib import Path,PurePosixPath
import subprocess,os,json,zipfile,hashlib,tempfile,traceback
ROOT=Path.home()/"research_artifacts/prevention_pilot_phase2"
OUT=ROOT/("owp14_watcher_blackbox_job"+os.environ["SLURM_JOB_ID"]);OUT.mkdir(parents=True,exist_ok=False)
SCRATCH=ROOT/"owp14_watcher_sandbox_scratch";SCRATCH.mkdir(exist_ok=True)
SRC=ROOT/"owp14_allcases_packets_job71014"/"CASE_03581_O.zip"
pre={"O":ROOT/"owp14_user12_o_preflight_job71153",
     "W":ROOT/"owp14_user14_w_preflight_job71208",
     "P":ROOT/"owp14_user14_p_preflight_job71201"}
meta={a:json.loads((p/"SUMMARY.json").read_text())["cases"]["3581"] for a,p in pre.items()}
bun=Path.home()/".bun/bin/bun"
BWRAP="/usr/bin/bwrap"
def sandbox(cmd,working,timeout=45):
 args=[BWRAP,"--unshare-user","--unshare-net","--die-with-parent",
    "--ro-bind","/","/","--bind",str(working),str(working),
    "--proc","/proc","--dev","/dev","--chdir",str(working)]
 env={"HOME":str(working),"TMPDIR":str(working),"PATH":str(bun.parent)+":/usr/bin:/bin",
    "BUN_INSTALL_CACHE_DIR":str(working/"bun-cache"),"CI":"1","NO_COLOR":"1"}
 args += ["--setenv", "HOME", str(working), "--setenv", "TMPDIR",str(working)]
 try:
  p=subprocess.run(args+[str(x) for x in cmd],cwd=working,env=env,
    stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=timeout)
  return {"exit_code":p.returncode,"stdout":p.stdout[-12000:]}
 except Exception as e:return {"exit_code":124,"stdout":repr(e)}
cases={}
with tempfile.TemporaryDirectory(prefix="preflight_",dir=SCRATCH) as d:
 root=Path(d)
 probe=sandbox(["/bin/true"],root,15)
 if probe["exit_code"]!=0:
  (OUT/"SUMMARY.json").write_text(json.dumps({"stage":"SKIPPED_UNAVAILABLE_SANDBOX",
    "capability_probe":probe,"cases":{}},indent=2)+"\n")
  print("WATCHER_BLACKBOX_SKIPPED sandbox unavailable "+probe["stdout"][:300],flush=True)
  raise SystemExit(0)
for arm in ("O","W","P"):
 row={"case_id":3581,"arm":arm,"status":"PENDING"}
 with tempfile.TemporaryDirectory(prefix="03581_"+arm+"_",dir=SCRATCH) as d:
  root=Path(d);repo=root/"repo";repo.mkdir()
  patch=pre[arm]/"CASE_03581"/meta[arm]["filename"]
  assert hashlib.sha256(patch.read_bytes()).hexdigest()==meta[arm]["original_patch_sha256"]
  with zipfile.ZipFile(SRC) as z:
   for name in meta[arm]["changed_paths"]:
    if "REPO/"+name not in z.namelist():continue
    part=PurePosixPath(name);assert ".." not in part.parts and ".git" not in part.parts
    dst=repo.joinpath(*part.parts);dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_bytes(z.read("REPO/"+name))
  r=subprocess.run(["git","apply",str(patch)],cwd=repo,
   stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=30,
   env={"PATH":"/usr/bin:/bin","HOME":str(root),"GIT_CONFIG_NOSYSTEM":"1","GIT_CONFIG_GLOBAL":"/dev/null"})
  assert r.returncode==0,r.stdout[-1000:]
  module=repo/"src/extension/services/jsonl-watcher-service.ts"
  testdir=root/"case";testdir.mkdir()
  runner=root/"watcher_test.mjs"
  runner.write_text("""
import {readFileSync,writeFileSync,appendFileSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {setTimeout as sleep} from 'node:timers/promises';
const [arm,modulePath,dir]=process.argv.slice(2);
const watcherModule=await import(modulePath);
const file=join(dir,'trace.jsonl');
writeFileSync(file,'');
const observed=[];
const errors=[];
let stop=()=>{};
if (arm==='O') {
  stop=watcherModule.watchClaudeSession(file,items=>{observed.push(...items);},err=>errors.push(String(err)));
} else {
  const instance=new watcherModule.JsonlWatcherService(file,items=>{observed.push(...items);});
  instance.start();
  stop=()=>instance.stop();
}
try {
  await sleep(150);
  appendFileSync(file, JSON.stringify({type:'assistant',message:{content:[{type:'text',text:'start'}]}})+'\\n'+
   JSON.stringify({type:'progress',data:{type:'bash_progress'}})+'\\n'+
   JSON.stringify({type:'user',message:{content:[{type:'tool_result',is_error:true}]}})+'\\n'+
   JSON.stringify({type:'system',subtype:'init'})+'\\n');
  await sleep(1900);
  const delivered=observed.map(x=>x.type);
  appendFileSync(file,'{"type":"assistant","message":');
  await sleep(1300);
  const prior=observed.length;
  appendFileSync(file,'{"content":[{"type":"text","text":"done"}]}}\\n');
  await sleep(1750);
  const after=observed.length;
  stop();
  appendFileSync(file,JSON.stringify({type:'assistant',message:{content:[{type:'text',text:'after stop'}]}})+'\\n');
  await sleep(1450);
  const finish=observed.length;
  const result={
    arm,firstBatch:delivered,errors,
    partialWithheld:(prior===delivered.length),
    assistantExactlyTwice:observed.filter(e=>e.type==='assistant').length===2,
    progressDelivered:delivered.includes('progress'),
    toolResultDelivered:delivered.includes('user'),
    extraMessagesAfterStop:finish!==after,
    totalEvents:finish
  };
  result.corePass=result.assistantExactlyTwice && result.progressDelivered &&
    result.partialWithheld && !result.extraMessagesAfterStop && errors.length===0;
  process.stdout.write(JSON.stringify(result)+'\\n');
  if (!result.corePass) process.exitCode=3;
} finally{stop();}
""")
  x=sandbox([bun,runner,arm,module,testdir],root,55)
  row.update({"returncode":x["exit_code"],"raw_output":x["stdout"][-4000:]})
  try:
   parsed=json.loads(x["stdout"].splitlines()[-1]);row["behavior"]=parsed
   row["status"]="CORE_PASS" if parsed["corePass"] else "CORE_FAIL"
  except Exception:row["status"]="TOOL_FAILED"
  cases[arm]=row
  print("WATCHER",arm,row["status"],row.get("behavior",{}),flush=True)
(OUT/"SUMMARY.json").write_text(json.dumps({"stage":"COMPLETE","cases":cases,
 "interpretation":"Only isolated watcher behavior; not AI commentator or issue-level feature acceptance",
 "sandbox":"bubblewrap unshared user and network with read-only filesystem except dedicated scratch"},indent=2)+"\n")
