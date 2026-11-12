#!/bin/bash
#SBATCH --job-name=arno_b64diag
#SBATCH --partition=stampede
#SBATCH --time=00:04:00
#SBATCH --mem=1G
python3 - <<'PY'
from pathlib import Path
import json,re,collections
R=Path.home()/'research_artifacts'
out=R/'mcp_uploads/jobs/arno_owp_base64_diagnostic_20261028'
out.mkdir(parents=True,exist_ok=True)
res=[]
for arm,p in [('O','owp14_20261018_transfer_v1'),('W','owp14_w14_20261018_transfer_v1'),('P','owp14_user_p14_20261018_transfer_v1')]:
 for f in sorted((R/'mcp_uploads'/p).glob('chunk_*.txt')):
  b=f.read_bytes()
  bad=[(i,chr(c)) for i,c in enumerate(b) if c not in b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=\r\n\t ']
  res.append({'arm':arm,'name':f.name,'size':len(b),'non_base64':bad[:8],
              'start':repr(b[:35]),'end':repr(b[-35:])})
(out/'DIAGNOSTIC.json').write_text(json.dumps(res,indent=2)+'\n')
print(json.dumps(res,indent=2),flush=True)
PY