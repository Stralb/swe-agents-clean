from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import json,hashlib
d=Path.home()/"research_artifacts"/"mcp_uploads/jobs/arno_scgg_replication_08152_12344_20261030_r1"
files=["package.json","apps/daemon/package.json","apps/daemon/src/byok/credential-service.ts","apps/daemon/src/routes/byok-credentials.ts","apps/daemon/src/app-config.ts","apps/daemon/tests/byok/credential-service.test.ts","apps/daemon/tests/byok/credential-routes.test.ts","apps/web/package.json","apps/web/src/components/SettingsDialog.tsx","apps/web/src/components/byok/ByokKeyField.tsx","apps/web/src/components/byok/validation.ts","apps/web/src/utils/byokProvider.ts","packages/contracts/src/api/byok-credentials.ts"]
with ZipFile(d/"ORIGINAL_SOURCE_12344.zip") as source:
 with ZipFile(d/"ORIGINAL_SOURCE_12344_LITE.zip","x",ZIP_DEFLATED,compresslevel=9) as out:
  for rel in files:out.writestr("REPO/"+rel,source.read("REPO/"+rel))
(d/"SOURCE_12344_LITE_LIST.json").write_text(json.dumps(files,indent=2))
print("done",len(files))
