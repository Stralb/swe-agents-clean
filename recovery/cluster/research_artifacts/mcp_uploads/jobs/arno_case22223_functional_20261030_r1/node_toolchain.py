#!/usr/bin/env python3
from pathlib import Path
import os,json,subprocess
R=Path.home()/"research_artifacts"
D=R/"mcp_uploads/jobs/arno_case22223_functional_20261030_r1"
BIN=Path.home()/"tools/node/bin"
env={**os.environ,"PATH":str(BIN)+":"+os.environ.get("PATH",""),"COREPACK_ENABLE_NETWORK":"0"}
items={}
for name,args in {
 "pnpm_offline":[str(BIN/"corepack"),"pnpm","--version"],
 "node_version":[str(BIN/"node"),"--version"],
 "global_typescript":[str(BIN/"npm"),"list","-g","--depth=0"],
 "npm_cache":[str(BIN/"npm"),"cache","ls","typescript"]
}.items():
 try:
  x=subprocess.run(args,capture_output=True,text=True,timeout=18,env=env)
  items[name]={"exit":x.returncode,"stdout":x.stdout[-5000:],"stderr":x.stderr[-2000:]}
 except Exception as e:items[name]={"error":repr(e)}
cp=Path.home()/".cache/node/corepack/v1"
items["corepack_cached"]=[str(x.relative_to(cp)) for x in cp.glob("*/*")][:50] if cp.exists() else []
(D/"NODE_TOOLCHAIN.json").write_text(json.dumps(items,indent=2))
print(json.dumps(items,indent=2))
