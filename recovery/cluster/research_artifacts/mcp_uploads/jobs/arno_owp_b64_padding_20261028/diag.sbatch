#!/bin/bash
#SBATCH --job-name=arno_b64pad
#SBATCH --partition=stampede
#SBATCH --time=00:04:00
#SBATCH --mem=1G
python3 - <<'PY'
from pathlib import Path
import re,json,base64
R=Path.home()/'research_artifacts'
D=R/'mcp_uploads/jobs/arno_owp_b64_padding_20261028'
D.mkdir(parents=True,exist_ok=True)
res=[]
for arm,dir in [('O','owp14_20261018_transfer_v1'),('W','owp14_w14_20261018_transfer_v1'),('P','owp14_user_p14_20261018_transfer_v1')]:
  files=sorted((R/'mcp_uploads'/dir).glob('chunk_*.txt'))
  text=b''.join(f.read_bytes().strip() for f in files)
  filtered=re.sub(rb'\s+',b'',text)
  equals=[i for i,x in enumerate(filtered) if x==61]
  err=None
  try:out=base64.b64decode(filtered,validate=True);ok=True
  except Exception as e:ok=False;err=type(e).__name__+': '+str(e)
  res.append({'arm':arm,'file_count':len(files),'total_len':len(filtered),'mod4':len(filtered)%4,'equals_count':len(equals),'equals_first_positions':equals[:15],'equals_last_positions':equals[-5:],'decode_valid':ok,'error':err})
(D/'B64_DIAGNOSTIC.json').write_text(json.dumps(res,indent=2)+'\n')
print(json.dumps(res,indent=2),flush=True)
PY