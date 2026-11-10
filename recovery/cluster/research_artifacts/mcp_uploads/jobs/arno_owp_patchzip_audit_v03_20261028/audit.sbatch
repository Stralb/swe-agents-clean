#!/bin/bash
#SBATCH --job-name=arno_owp_zip_v03
#SBATCH --partition=stampede
#SBATCH --time=00:07:00
#SBATCH --mem=2G
python3 - <<'PY'
from pathlib import Path
import json,base64,zipfile,io,re,hashlib
R=Path.home()/'research_artifacts'
D=R/'mcp_uploads/jobs/arno_owp_patchzip_audit_v03_20261028'
D.mkdir(parents=True,exist_ok=True)
summary=json.loads((R/'prevention_pilot_phase2/owp14_allarm_comparison_job71212/OWP14_SUMMARY.json').read_text())
known={int(x['case_id']):x for x in summary['cases']}
out=[]
for arm,folder in [('O','owp14_20261018_transfer_v1'),('W','owp14_w14_20261018_transfer_v1'),('P','owp14_user_p14_20261018_transfer_v1')]:
 fs=sorted((R/'mcp_uploads'/folder).glob('chunk_*.txt'))
 data=b''.join(x.read_bytes().strip() for x in fs)
 data=re.sub(rb'\s+',b'',data)
 zip_bytes=base64.b64decode(data,validate=True)
 entries=[]
 with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
  if z.testzip():raise ValueError('Archive CRC fail')
  for inf in z.infolist():
   if inf.is_dir():continue
   b=z.read(inf.filename)
   m=re.search(r'CASE_([0-9]+)_([OWP])\.patch$',inf.filename,re.I)
   cid=int(m.group(1)) if m else None
   arm_from_name=m.group(2).upper() if m else None
   expected=known.get(cid,{}).get(arm+'_patch_sha256') if cid else None
   actual=hashlib.sha256(b).hexdigest()
   entries.append({'name':inf.filename,'case_id':cid,'filename_arm':arm_from_name,'sha256':actual,'expected':expected,'matched':actual==expected if expected else None,'bytes':len(b)})
 out.append({'arm':arm,'zip_sha256':hashlib.sha256(zip_bytes).hexdigest(),'members':entries,'n':len(entries)})
(D/'AUDIT.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps([{'arm':x['arm'],'n':x['n'],'names':[y['name'] for y in x['members'][:4]],'hashmatches':sum(y['matched']==True for y in x['members'])} for x in out],indent=2),flush=True)
PY