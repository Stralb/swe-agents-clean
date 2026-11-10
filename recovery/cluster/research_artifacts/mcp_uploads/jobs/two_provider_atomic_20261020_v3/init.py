from pathlib import Path
import zipfile,io,subprocess,sys
cid=sys.argv[1]
root=Path.home()/'research_artifacts'
out=root/'prevention_pilot_phase2/provider_variants_20261020_retry'/cid
out.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(root/'prevention_pilot_phase2/seven_case_delivery_20261020/SEVEN_CASES_ALL_7_FROZEN_REPOSITORIES.zip') as z:raw=z.read('CASE_INPUTS/CASE_'+cid+'_O.zip')
with zipfile.ZipFile(io.BytesIO(raw)) as z:z.extractall(out/'baseline')
repo=out/'baseline/REPO'
for a in [['git','init','-q'],['git','config','user.email','study@invalid.example'],['git','config','user.name','Study'],['git','add','-A'],['git','-c','core.hooksPath=/dev/null','commit','-qm','Original']]:subprocess.run(a,cwd=repo,check=True)
patch=root/'prevention_pilot_phase2/seven_case_scans_20261020'/cid/('CASE_'+cid+'_P1_r01.patch')
subprocess.run(['git','apply','--check',str(patch)],cwd=repo,check=True)
subprocess.run(['git','apply',str(patch)],cwd=repo,check=True)
print('PREPARED',cid)
