#!/usr/bin/env python3
from pathlib import Path
import zipfile,json,hashlib,subprocess,tempfile,shutil
root=Path.home()/'research_artifacts/prevention_pilot_phase2/issue_recipe_two_cases_20261019'
manifest=json.loads((root/'RESULT_MANIFEST.json').read_text())
assert len(manifest)==8
master=root/'MASTER_8_ISSUE_RECIPE_ABLATION_INPUTS.zip'
assert master.exists()
bycase={}
with zipfile.ZipFile(master) as mz:
 assert mz.testzip() is None
 for m in manifest:
  path=root/m['name']
  assert hashlib.sha256(path.read_bytes()).hexdigest()==m['sha256']
  assert mz.read(m['name'])==path.read_bytes()
  with zipfile.ZipFile(path) as z:
   assert z.testzip() is None
   repo={x:z.read(x) for x in z.namelist() if x.startswith('REPO/') and not x.endswith('/')}
   hashes={name:hashlib.sha256(data).hexdigest() for name,data in repo.items()}
   assert len(repo)==m['repo_files']
   assert z.read('OUTPUT_FILENAME.txt').decode().strip()==f"CASE_{m['case']}_{m['condition']}_rep{m['replicate']}.patch"
   assert z.read('RUNLOG_FILENAME.txt').decode().strip()==f"CASE_{m['case']}_{m['condition']}_rep{m['replicate']}_runlog.txt"
   assert z.read('ISSUE.md')== (root/f"CASE_{m['case']}_{'ORIGINAL' if m['condition']=='O' else 'PROBLEM_ONLY'}_ISSUE.md").read_bytes()
   case=m['case'];bycase.setdefault(case,[]).append((m['condition'],m['replicate'],hashes,hashlib.sha256(z.read('RUN_INSTRUCTIONS.md')).hexdigest()))
 for c,arr in bycase.items():
  assert len(arr)==4
  first=arr[0]
  assert all(item[2]==first[2] and item[3]==first[3] for item in arr),c
test={}
for c in ('03429','03581'):
 record=next(x for x in manifest if x['case']==c and x['condition']=='P' and x['replicate']==1)
 with tempfile.TemporaryDirectory(prefix='smoke_'+c+'_') as td:
  cwd=Path(td)
  with zipfile.ZipFile(root/record['name']) as z:z.extractall(cwd)
  prep=subprocess.run(['python3','PREPARE_WORKTREE.py'],cwd=cwd,capture_output=True,text=True)
  assert prep.returncode==0,(c,prep.stderr)
  readme=cwd/'WORK/README.md';readme.write_bytes(readme.read_bytes()+b'\n\nTemporary researcher smoke marker.\n')
  export=subprocess.run(['python3','EXPORT_PATCH.py'],cwd=cwd,capture_output=True,text=True)
  assert export.returncode==0,(c,export.stderr)
  patch=cwd/f"CASE_{c}_P_rep1.patch"
  assert patch.is_file() and patch.stat().st_size>20
  test[c]={'prep':'PASS','export':'PASS','patch_bytes':patch.stat().st_size}
print(json.dumps({'status':'ALL_PASS','packets':8,'master_bytes':master.stat().st_size,'master_sha256':hashlib.sha256(master.read_bytes()).hexdigest(),'case_repo_files':{c:len(arr[0][2]) for c,arr in bycase.items()},'smoke':test},indent=2))
