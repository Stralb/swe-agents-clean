from zipfile import ZipFile,ZIP_DEFLATED
from pathlib import Path
import json,hashlib
d=Path.home()/"research_artifacts"/"mcp_uploads/jobs/arno_scgg_replication_08152_12344_20261030_r1"
root=Path.home()/"research_artifacts/mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2/run_zips"
files=["package.json","pnpm-workspace.yaml","apps/daemon/package.json","apps/daemon/tsconfig.json","apps/daemon/src/byok/credential-service.ts","apps/daemon/src/routes/byok-credentials.ts","apps/daemon/src/app-config.ts","apps/daemon/src/byok-tools.ts","apps/daemon/src/runtimes/byok-opencode.ts","apps/daemon/tests/byok/credential-service.test.ts","apps/daemon/tests/byok/credential-routes.test.ts","apps/daemon/tests/byok/credential-service.node-pty-boundary.test.ts","apps/daemon/tests/byok/run-input-boundary.test.ts","apps/web/package.json","apps/web/tsconfig.json","apps/web/src/components/SettingsDialog.tsx","apps/web/src/components/byok/ByokKeyField.tsx","apps/web/src/components/byok/ByokProviderPicker.tsx","apps/web/src/components/byok/ByokConnectionTestControl.tsx","apps/web/src/components/byok/ByokModelField.tsx","apps/web/src/components/byok/ByokProviderBaseUrl.tsx","apps/web/src/components/byok/preflight.ts","apps/web/src/components/byok/validation.ts","apps/web/src/utils/byokProvider.ts","packages/contracts/src/api/byok-credentials.ts"]
dest=d/"ORIGINAL_SOURCE_12344.zip"
with ZipFile(root/"RPL7_RUN_E0EDE434153B.zip") as z:
 assert z.testzip() is None
 with ZipFile(dest,"x",ZIP_DEFLATED,compresslevel=8) as out:
  for f in files:out.writestr("REPO/"+f,z.read("REPO/"+f))
(d/"SOURCE_12344_LIST.json").write_text(json.dumps(files,indent=2))
print(json.dumps({"files":len(files),"bytes":dest.stat().st_size,"sha256":hashlib.sha256(dest.read_bytes()).hexdigest()}))
