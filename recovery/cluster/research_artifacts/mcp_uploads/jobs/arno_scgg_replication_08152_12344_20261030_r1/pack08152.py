from zipfile import ZipFile,ZIP_DEFLATED
from pathlib import Path
import json,hashlib
d=Path.home()/"research_artifacts"/"mcp_uploads/jobs/arno_scgg_replication_08152_12344_20261030_r1"
root=Path.home()/"research_artifacts/mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2/run_zips"
files=["package.json","tsconfig.json","src/agent/agent.ts","src/types/index.ts","src/index.ts","src/telegram/bridge.ts","src/telegram/index.ts","src/telegram/limits.ts","src/telegram/pairing.ts","src/telegram/preview-stream.ts","src/telegram/turn-coordinator.ts","src/telegram/typing-refresh.ts","src/grok/client.ts","src/grok/media.ts","src/grok/models.ts","src/grok/tools.ts","src/grok/media.test.ts","src/telegram/limits.test.ts"]
dest=d/"ORIGINAL_SOURCE_08152.zip"
with ZipFile(root/"RPL7_RUN_23E9AAB8295A.zip") as z:
 assert z.testzip() is None
 with ZipFile(dest,"x",ZIP_DEFLATED,compresslevel=8) as out:
  for f in files:out.writestr("REPO/"+f,z.read("REPO/"+f))
(d/"SOURCE_08152_LIST.json").write_text(json.dumps(files,indent=2))
print(json.dumps({"files":len(files),"bytes":dest.stat().st_size,"sha256":hashlib.sha256(dest.read_bytes()).hexdigest()}))
