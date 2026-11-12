from pathlib import Path
import zipfile,hashlib,json
r=Path.home()/'research_artifacts'
s=r/'prevention_pilot_phase2/owp14_allcases_packets_job71014'
d=r/'prevention_pilot_phase2/seven_case_delivery_20261020'
d.mkdir(parents=True,exist_ok=True)
out=d/'SEVEN_CASES_ALL_7_FROZEN_REPOSITORIES.zip'
ids=['03429','03581','08152','12344','22223','31207','32759']
m=[]
with zipfile.ZipFile(out,'w',allowZip64=True) as z:
 for x in ids:
  f=s/('CASE_'+x+'_O.zip')
  assert f.is_file(),str(f)
  with zipfile.ZipFile(f) as zi:
   assert 'ISSUE.md' in zi.namelist()
   assert sum(q.startswith('REPO/') for q in zi.namelist())>3
   z.writestr('ISSUES/CASE_'+x+'.md',zi.read('ISSUE.md'))
  z.write(f,'CASE_INPUTS/'+f.name,compress_type=zipfile.ZIP_STORED)
  m.append({'case':x,'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'bytes':f.stat().st_size})
 z.writestr('MANIFEST.json',json.dumps(m,indent=2))
 z.writestr('START_HERE.txt','Seven complete frozen original repositories are in CASE_INPUTS/. Pair with the previously provided SEVEN_CASES_SINGLE_CHAT_OVERNIGHT_COMPACT_20261020.zip for experiment instructions, research evidence, and P1/P2/P3 treatments. Return 21 patches plus logs and manifest; do not claim CodeQL outcomes.\n')
with zipfile.ZipFile(out) as z:assert z.testzip() is None
print('SUCCESS',out,out.stat().st_size)
