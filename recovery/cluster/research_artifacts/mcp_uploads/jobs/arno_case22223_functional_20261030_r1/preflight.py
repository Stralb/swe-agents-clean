#!/usr/bin/env python3
from pathlib import Path
import json,zipfile,hashlib,subprocess,shutil
R=Path.home()/"research_artifacts"
SRC=R/"mcp_uploads/jobs/arno_v6_20261030_case22223_three_pilots/ready/ARNO_22223_A_MECHANISM_UPLOAD.zip"
OUT=R/"mcp_uploads/jobs/arno_case22223_functional_20261030_r1"
OUT.mkdir(exist_ok=True)
def tool(name):
 p=shutil.which(name)
 if not p:return {"path":None}
 try:
  q=subprocess.run([p,"--version"],capture_output=True,text=True,timeout=12)
  return {"path":p,"exit":q.returncode,"output":(q.stdout+q.stderr)[-500:]}
 except Exception as e:return {"path":p,"error":str(e)}
with zipfile.ZipFile(SRC) as z:
 paths=z.namelist()
 pkg="REPO/package.json"
 pjson=json.loads(z.read(pkg)) if pkg in paths else {}
 data={
  "original_issue":z.read("ISSUE.md").decode("utf-8","replace")[:14000],
  "scripts":pjson.get("scripts"),"package_manager":pjson.get("packageManager"),
  "dev_dependencies":pjson.get("devDependencies"),
  "dependencies":pjson.get("dependencies"),
  "node_and_pnpm":{x:tool(x) for x in ("node","pnpm","npm","corepack","git","tsc","npx")},
  "file_census":len([p for p in paths if p.startswith("REPO/")]),
  "lock_files":[p for p in paths if any(p.endswith(x) for x in ("lock.yaml","lock.json","yarn.lock","tsconfig.json","vitest.config.ts","jest.config.js"))],
  "tests":[p for p in paths if p.startswith("REPO/tests/")][:180],
  "node_modules_candidates":[str(p) for p in (Path.home()/"new/malicious-issue-miner-rate-smart/node_modules",Path.home()/"tools/node",R/"mcp_uploads") if p.exists()]
 }
 (OUT/"PREFLIGHT.json").write_text(json.dumps(data,indent=2))
 print(json.dumps({k:v for k,v in data.items() if k not in ("dev_dependencies","dependencies","original_issue","tests")},indent=2),flush=True)
