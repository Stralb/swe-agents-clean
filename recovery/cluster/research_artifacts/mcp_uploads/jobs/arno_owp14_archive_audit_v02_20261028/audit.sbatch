#!/bin/bash
#SBATCH --job-name=arno_owp14_audit
#SBATCH --partition=stampede
#SBATCH --time=00:08:00
#SBATCH --mem=3G
python3 - <<'PY'
from pathlib import Path
import json,io,csv,zipfile,base64,hashlib,collections,re
R=Path.home()/'research_artifacts'
D=R/'mcp_uploads/jobs/arno_owp14_archive_audit_v02_20261028'
D.mkdir(parents=True,exist_ok=True)
sha=lambda b:hashlib.sha256(b).hexdigest()
groups=[('O','mcp_uploads/owp14_20261018_transfer_v1',6),('W','mcp_uploads/owp14_w14_20261018_transfer_v1',5),('P','mcp_uploads/owp14_user_p14_20261018_transfer_v1',4)]
report={'groups':[],'errors':[]}
summary=json.loads((R/'prevention_pilot_phase2/owp14_allarm_comparison_job71212/OWP14_SUMMARY.json').read_text())
cases={int(q['case_id']):q for q in summary['cases']}
for arm,folder,n in groups:
  paths=sorted((R/folder).glob('chunk_*.txt'))
  if len(paths)!=n:raise ValueError('Unexpected '+arm+' chunk count '+str(len(paths)))
  for i,p in enumerate(paths,1):
    if p.name!=f'chunk_{i:02d}.txt':raise ValueError('Fragment out of order '+p.name)
  raw=base64.b64decode(re.sub(rb'\\s+',b'',b''.join(p.read_bytes() for p in paths)),validate=True)
  entries=[]
  with zipfile.ZipFile(io.BytesIO(raw)) as z:
    assert z.testzip() is None
    for m in z.infolist():
      if m.is_dir():continue
      b=z.read(m.filename)
      match=re.search(r'CASE_([0-9]+)_([OWP])\.patch$',m.filename,re.I)
      ident=int(match.group(1)) if match else None
      group=match.group(2).upper() if match else None
      expected=cases.get(ident,{}).get(arm+'_patch_sha256') if ident is not None else None
      entries.append({'filename':m.filename,'case_id':ident,'parsed_arm':group,'bytes':len(b),'sha256':sha(b),'expected_sha256':expected,'summary_hash_match':(sha(b)==expected) if expected else None})
  report['groups'].append({'arm':arm,'original_zip_sha256':sha(raw),'members':entries,'count':len(entries),
                            'hash_matches':sum(e['summary_hash_match'] is True for e in entries)})
report['summary_cases']=len(cases)
report['status']='INSPECTED'
(D/'OWP14_ARCHIVE_REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'status':report['status'],'groups':[{'arm':g['arm'],'count':g['count'],'hash_matches':g['hash_matches'],'name_samples':[e['filename'] for e in g['members'][:4]],'mismatches':[e['filename'] for e in g['members'] if e['summary_hash_match'] is False]} for g in report['groups']]},indent=2),flush=True)
PY