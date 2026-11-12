#!/usr/bin/env python3
from pathlib import Path
import subprocess,os,shutil,json,glob
R=Path.home()/"research_artifacts"
D=R/"mcp_uploads/jobs/arno_case22223_functional_20261030_r1"
D.mkdir(exist_ok=True)
bins=[Path.home()/"tools/node/bin"/x for x in ("node","npm","pnpm","corepack","npx")] +[Path.home()/"tools/node"/x for x in ("node","pnpm")]
out={}
for p in bins:
 k=str(p);r={"exists":p.exists(),"executable":os.access(p,os.X_OK)}
 if r["executable"]:
  try:
   v=subprocess.run([str(p),"--version"],capture_output=True,text=True,timeout=10,env={**os.environ,"PATH":str(p.parent)+":"+os.environ["PATH"]})
   r.update(exit=v.returncode,stdout=v.stdout[-400:],stderr=v.stderr[-400:])
  except Exception as e:r["error"]=repr(e)
 out[k]=r
candidates=[R/"mcp_uploads/jobs/owp14_functional_env_20261019_v1",Path.home()/".cache/node/corepack",Path.home()/".local/share/pnpm",Path.home()/"tools/node"]
for p in candidates:out[str(p)]={"exists":p.exists(),"children":[x.name for x in p.iterdir()][:50] if p.is_dir() else []}
(D/"ENV_NODE.json").write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
