import json
from pathlib import Path
root=Path.home()/"research_artifacts"/"mcp_uploads/jobs/arno_scgg_replication_08152_12344_20261030_r1"
info=json.loads((root/"INSPECT.json").read_text())
out={}
for case,record in info.items():
 issue=next((v["text"] for v in record["documents"] if v["path"]=="ISSUE.md"),"MISSING")
 paths=[v for v in record["filenames"] if v["path"].startswith("REPO/")]
 if case=="08152":
  matches=[v for v in paths if ("telegram/" in v["path"] or "grok/" in v["path"] or v["path"].endswith("package.json") or "src/types/index.ts" in v["path"])]
 else:
  matches=[v for v in paths if ("credential" in v["path"].lower() or "byok/" in v["path"].lower() or "windows" in v["path"].lower())]
 out[case]={"issue":issue,"matches":matches[:80],"total":len(paths)}
(root/"TASK_SUMMARY.json").write_text(json.dumps(out,indent=2))
print(json.dumps({k:{"total":v["total"],"matched":len(v["matches"])} for k,v in out.items()}))
