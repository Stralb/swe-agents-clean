#!/usr/bin/env python3
from pathlib import Path
import shutil,subprocess,json
R=Path.home()/"research_artifacts"
O=R/"mcp_uploads/jobs/arno_six_case_abc_preparation_20261030_r1"
out={}
for name in ("codex","claude","aider","ollama","vllm","node"):
 p=shutil.which(name);o={"path":p}
 if p:
  try:
   a=subprocess.run([p,"--version"],capture_output=True,text=True,timeout=8)
   o["exit"]=a.returncode;o["version"]=(a.stdout+a.stderr)[-300:]
  except Exception as e:o["error"]=repr(e)
 out[name]=o
for root in [Path.home()/".codex",Path.home()/".local/bin",Path.home()/"tools"]:
 out[str(root)]={"exists":root.exists(),"children":[p.name for p in root.iterdir()][:50] if root.is_dir() else []}
(O/"MODEL_RUNTIME_INVENTORY.json").write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
