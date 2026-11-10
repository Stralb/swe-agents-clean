import json
from pathlib import Path
r=Path.home()/"research_artifacts"/"mcp_uploads/jobs/arno_scgg_replication_08152_12344_20261030_r1"
i=json.loads((r/"INSPECT.json").read_text())
result={}
for case in ["08152","12344"]:
 paths=[v["path"] for v in i[case]["filenames"] if v["path"].startswith("REPO/")]
 if case=="12344":
  paths=[p for p in paths if
   (p.startswith("REPO/apps/web/src/") and any(s in p.lower() for s in ["settings","execution-mode","byok","credential"])) or
   (p.startswith("REPO/apps/daemon/src/") and any(s in p.lower() for s in ["byok","credential","config","data-dir"])) or
   p in ["REPO/apps/web/package.json","REPO/apps/daemon/package.json","REPO/package.json","REPO/pnpm-workspace.yaml","REPO/apps/web/tsconfig.json","REPO/apps/daemon/tsconfig.json"]]
 result[case]=paths[:260]
(r/"INTEGRATION_PATHS.json").write_text(json.dumps(result,indent=2))
