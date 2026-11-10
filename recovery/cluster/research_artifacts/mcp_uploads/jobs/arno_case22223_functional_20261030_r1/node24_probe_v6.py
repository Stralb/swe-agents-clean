#!/usr/bin/env python3
from pathlib import Path
import os,subprocess,json
R=Path.home()/"research_artifacts"
O=R/"mcp_uploads/jobs/arno_case22223_functional_20261030_r1"
ROOT=Path.home()/"tools"
out={}
for x in ["node24","node22","node","node24/bin/node","node24/bin/corepack","node24/bin/npm","node22/bin/node"]:
 p=ROOT/x
 record={"exists":p.exists(),"isdir":p.is_dir(),"issymlink":p.is_symlink(),"resolved":str(p.resolve())}
 if p.is_file() and os.access(p,os.X_OK):
  try:
   v=subprocess.run([str(p),"--version"],capture_output=True,text=True,timeout=10)
   record["version"]=(v.stdout+v.stderr)[-500:];record["exit"]=v.returncode
  except Exception as e:record["error"]=repr(e)
 out[x]=record
(O/"NODE24_PROBE.json").write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
