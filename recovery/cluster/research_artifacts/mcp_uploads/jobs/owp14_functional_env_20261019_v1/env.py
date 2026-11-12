#!/usr/bin/env python3
"""Toolchain availability and packet install footprint, no repo script execution."""
from pathlib import Path
import subprocess,os,json,zipfile
ROOT=Path.home()/"research_artifacts/prevention_pilot_phase2"
OUT=ROOT/("owp14_functional_env_job"+os.environ["SLURM_JOB_ID"])
OUT.mkdir(parents=True,exist_ok=False)
tools=["node","npm","pnpm","bun","tsc","vitest","jest","docker","bwrap","unshare","git","python3"]
result={"tools":{},"packets":{},"safe_execution_requested":False}
for tool in tools:
 try:
  r=subprocess.run(["which",tool],text=True,stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,timeout=15)
  p=r.stdout.strip()
  if r.returncode:result["tools"][tool]={"available":False};continue
  ver=subprocess.run([p,"--version"],text=True,stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,timeout=15) if tool not in ("bwrap","unshare") else None
  result["tools"][tool]={"available":True,"path":p,"version":(ver.stdout or "").strip()[:400] if ver else "N/A"}
 except Exception as e:result["tools"][tool]={"error":str(e)[:250]}
for cid in [668,3429,3581,6104,8152,8461,12344,15151,16633,20094,21682,22223,31207,32759]:
 path=ROOT/"owp14_allcases_packets_job71014"/("CASE_%05d_O.zip"%cid)
 with zipfile.ZipFile(path) as z:
  names=z.namelist()
  result["packets"][str(cid)]={"node_modules_members":sum('/node_modules/' in s for s in names),
   "has_root_lockfile":any(f"REPO/{name}" in names for name in ["package-lock.json","pnpm-lock.yaml","bun.lockb","bun.lock","yarn.lock"]),
   "js_sources":sum(s.endswith((".js",".mjs",".cjs",".ts",".tsx")) for s in names),
   "repository_members":sum(s.startswith("REPO/") for s in names)}
(OUT/"ENV.json").write_text(json.dumps(result,indent=2)+"\n")
print("ENV_COMPLETE",json.dumps(result["tools"],sort_keys=True),flush=True)
