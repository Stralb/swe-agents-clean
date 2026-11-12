#!/usr/bin/env python3
from pathlib import Path
import json,os,subprocess,shutil,urllib.request
r={}
for exe in ("node","npm","npx","corepack","pnpm","bun","tsc","git"):
 p=shutil.which(exe);r[exe]={"path":p}
 if p:
  try:
   x=subprocess.run([p,"--version"],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=12)
   r[exe]["version"]=x.stdout[:200];r[exe]["exit"]=x.returncode
  except Exception as e:r[exe]["error"]=repr(e)
r["other_nodes"]=[]
for p in (Path.home()/"tools",Path("/usr/local/bin"),Path("/opt")):
 if p.is_dir():r["other_nodes"] += [str(f) for f in p.glob("**/node") if f.is_file()][:20]
for url in ("https://nodejs.org/dist/v24.13.0/SHASUMS256.txt","https://registry.npmjs.org/pnpm"):
 try:
  req=urllib.request.Request(url,method="HEAD",headers={"User-Agent":"WitsResearchPreflight/1.0"})
  with urllib.request.urlopen(req,timeout=10) as resp:r[url]={"status":resp.status,"length":resp.headers.get("content-length")}
 except Exception as e:r[url]={"error":repr(e)[:220]}
path=Path.home()/"research_artifacts/prevention_pilot_phase2"/("focus5_envprobe_job"+os.environ["SLURM_JOB_ID"]);path.mkdir(exist_ok=False)
(path/"TOOLS.json").write_text(json.dumps(r,indent=2)+"\n")
print("ENV_PROBE",r)
