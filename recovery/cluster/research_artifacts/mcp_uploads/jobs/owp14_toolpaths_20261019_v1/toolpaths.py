#!/usr/bin/env python3
"""Find preinstalled local JS/TS toolchains without repository code execution or downloads."""
from pathlib import Path
import os,shutil,subprocess,json
h=Path.home()
places=[
 h/"tools/node/bin",h/"tools/codeql",
 h/".local/bin",h/".bun/bin",
 h/".npm-global/bin",h/".volta/bin",
 Path("/usr/local/bin"),Path("/usr/bin"),
 Path("/opt/node/bin"),Path("/opt/nodejs/bin")]
path=":".join(str(p) for p in places)+":"+os.environ.get("PATH","")
ans={}
for x in ["node","npm","npx","pnpm","corepack","bun","tsc","vitest","jest","tsx","ts-node"]:
 f=shutil.which(x,path=path)
 if f:
  try:
   r=subprocess.run([f,"--version"],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=10,
     env={"HOME":str(h),"PATH":path})
   vers=r.stdout.strip()[:170]
  except Exception as e:vers=str(e)[:150]
 else:vers=""
 ans[x]={"path":f,"version":vers}
def globdirs(root,patterns):
 return [str(y) for patt in patterns for y in root.glob(patt) if y.exists()][:35]
ans["installed_candidates"]={
 "local_node_bins":globdirs(h,["tools/node/bin/*","tools/*/bin/node","tools/**/bin/node"]),
 "global_npm_typescript":globdirs(h,["tools/node/lib/node_modules/typescript","tools/node/lib/node_modules/tsx",
  ".local/lib/node_modules/typescript",".npm-global/lib/node_modules/typescript"]),
 "system_other_bins":globdirs(Path("/opt"),["node*/bin/node","*/bin/tsc"])}
out=h/"research_artifacts/prevention_pilot_phase2"/("owp14_toolchain_paths_job"+os.environ["SLURM_JOB_ID"])
out.mkdir(parents=True,exist_ok=False)
(out/"NODE_PATHS.json").write_text(json.dumps(ans,indent=2)+"\n")
print("NODE_PATHS",json.dumps(ans),flush=True)
