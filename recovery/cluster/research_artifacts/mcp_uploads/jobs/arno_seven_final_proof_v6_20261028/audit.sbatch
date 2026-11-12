#!/bin/bash
#SBATCH --job-name=arno7_finalproof
#SBATCH --partition=stampede
#SBATCH --time=00:07:00
#SBATCH --mem=3G
python3 - <<'PY'
from pathlib import Path
import zipfile,json,hashlib
R=Path.home()/'research_artifacts'
src=R/'prevention_pilot_phase2/FINAL_SEVEN_CASE_RESEARCH_HANDOFF_20261020/COMPLETE_7_CASE_RESEARCH_HANDOFF_20261020.zip'
out=R/'mcp_uploads/jobs/arno_seven_final_proof_v6_20261028'
out.mkdir(parents=True,exist_ok=True)
sha=lambda b:hashlib.sha256(b).hexdigest()
report={'archive':str(src.relative_to(R)),'status':'STARTED','cases':[]}
with zipfile.ZipFile(src) as z:
 report['master_index']=json.loads(z.read('MASTER_INDEX.json'))
 names=set(z.namelist())
 for num in ['03429','03581','08152','12344','22223','31207','32759']:
  prefix=f'CASE_DETAILS/{num}/'
  final_patch=f'FINAL_PATCHES/CASE_{num}_FINAL.patch'
  doc=f'CASE_DETAILS/CASE_{num}_FINAL_RESULT.json'
  possible=[n for n in names if n.startswith(prefix) and ('FINAL' in n or 'repair' in n.lower())]
  result=json.loads(z.read(doc)) if doc in names else {}
  patch=z.read(final_patch) if final_patch in names else b''
  expected=result.get('new_patch_sha256')
  report['cases'].append({'case_id':num,'final_patch_exists':bool(patch),'final_patch_sha256':sha(patch) if patch else None,
   'final_result_keys':list(result.keys()),'final_result':result,'reported_patch_hash_matches':sha(patch)==expected if expected else None,
   'final_evidence_members':sorted(possible),'final_after_sarif_exists':prefix+'FINAL_after.sarif' in names})
 report['all_names']=[n for n in sorted(names) if not n.endswith('/')]
 report['total_members']=len(report['all_names'])
report['status']='COMPLETE'
(out/'FINAL_SEVEN_CASE_PROVENANCE_AUDIT.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'status':report['status'],'num_members':report['total_members'],
 'cases':[{'case':x['case_id'],'hash_match':x['reported_patch_hash_matches'],
          'has_sarif':x['final_after_sarif_exists'],'result_keys':x['final_result_keys'],
          'final_related':x['final_evidence_members'][:8]} for x in report['cases']]},indent=2),flush=True)
PY