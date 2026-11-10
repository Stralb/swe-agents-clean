#!/usr/bin/env python3
"""Stage the verified E126 controller for the known-working ARC-AGI-3 Kaggle notebook workflow."""
import ast,hashlib,json,shutil
from pathlib import Path
ROOT=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs')
BASE=ROOT/'e126_kaggle_submit_20261027'
REF=ROOT/'e128_release_20261027/release'
GOOD=ROOT/'n117_kaggle_20261026_recovery1/kernel'
NEW_DATASET='arnostrauss/arc-agi-3-e126-hybrid-source-20261027'
NEW_KERNEL='arnostrauss/arc-agi-3-e126-hybrid-20261027'
HASH='84f27a2589575558ddb85dff2539f68d1937c6dc1a048cb3b133f6ae7005178c'
OLD_HASH='0663845070e47a053076db54243c3445921a06b4bf0908b7b233c263da423bfa'
source=(REF/'my_agent.py').read_bytes()
assert hashlib.sha256(source).hexdigest()==HASH
ast.parse(source.decode('utf-8'))
manifest=json.loads((REF/'manifest.json').read_text())
assert manifest['variant']=='E126 hybrid_trained'
assert manifest['full_agent_sha256']==HASH
assert manifest['frozen_n117_sha256']==OLD_HASH
assert manifest['modal_colour_threshold']==0.8
assert 'class E126Core' in source.decode()
ds=BASE/'dataset'
ds.mkdir(parents=True,exist_ok=True)
shutil.copyfile(REF/'my_agent.py',ds/'my_agent.py')
(ds/'dataset-metadata.json').write_text(json.dumps({
  'id':NEW_DATASET,
  'title':'ARC AGI 3 E126 Hybrid Agent Source 20261027',
  'subtitle':'Self-contained E126 controller and pretrained effect prior',
  'description':'Private Kaggle evaluation dataset with verified E126 hybrid_trained portable policy, frozen N117 and embedded teammate pretrained effect prior. No private game data, game identifiers, or competition gateway keys included. License terms retained by authors.',
  'licenses':[{'name':'other'}],
  'isPrivate':True
},indent=2)+'\n')
kernel=BASE/'kernel'
kernel.mkdir(parents=True,exist_ok=True)
old=json.loads((GOOD/'submission.ipynb').read_text())
assert len(old['cells'])==5
assert old['metadata']['kaggle']['isInternetEnabled'] is False
old['cells'][0]['source']=[
 '# E126 Hybrid ARC-AGI-3 Submission\n',
 'Frozen N117 local-effect RL plus click-contingency and sparse-scene pretrained effect prior.\n',
 'Offline native gateway competition rerun; previously exposed public tests do not guarantee hidden score.\n'
]
new_code=(
 'from pathlib import Path\n'
 'import hashlib\n'
 "files = [p for p in Path('/kaggle/input').rglob('my_agent.py') if "+repr(NEW_DATASET.split('/')[1])+" in str(p)]\n"
 "if len(files) != 1:\n"
 "    raise RuntimeError(f'E126 agent dataset missing or ambiguous: {len(files)} matches')\n"
 "data = files[0].read_bytes()\n"
 "if hashlib.sha256(data).hexdigest() != "+repr(HASH)+":\n"
 "    raise RuntimeError('E126 agent source SHA256 mismatch')\n"
 "Path('/tmp/my_agent.py').write_bytes(data)\n"
 "print('E126 verified portable agent source installed')\n"
)
compile(new_code,'e126_dataset_load.py','exec')
old['cells'][2]['source']=new_code.splitlines(keepends=True)
runtime=''.join(old['cells'][3]['source'])
assert runtime.count(OLD_HASH)==1
assert 'BoundedSemaphore(12)' in runtime
assert 'record=False' in runtime
assert 'KAGGLE_IS_COMPETITION_RERUN' in runtime
runtime=runtime.replace(OLD_HASH,HASH).replace('N117_','E126_')
compile(runtime,'e126_runtime.py','exec')
old['cells'][3]['source']=runtime.splitlines(keepends=True)
old['cells'][4]['source']=['import os\n',
 "if not os.getenv('KAGGLE_IS_COMPETITION_RERUN'):\n",
 '    import pandas as pd\n',
 "    submission = pd.DataFrame([['1_0','1',True,1]], columns=['row_id','game_id','end_of_game','score'])\n",
 "    submission.to_parquet('/kaggle/working/submission.parquet', index=False)\n"
]
for cell in old['cells']:
 if cell['cell_type']=='code':
  cell['outputs']=[]
  cell['execution_count']=None
old['metadata']['kaggle']['isGpuEnabled']=False
old['metadata']['kaggle']['isInternetEnabled']=False
old['metadata']['kaggle']['accelerator']='none'
kmeta=json.loads((GOOD/'kernel-metadata.json').read_text())
kmeta['id']=NEW_KERNEL
kmeta['title']='ARC AGI 3 E126 Hybrid 20261027'
kmeta['dataset_sources']=[NEW_DATASET]
kmeta['competition_sources']=['arc-prize-2026-arc-agi-3']
kmeta['is_private']=True
kmeta['enable_gpu']=False
kmeta['enable_internet']=False
(kernel/'kernel-metadata.json').write_text(json.dumps(kmeta,indent=2)+'\n')
nb=kernel/'submission.ipynb'
nb.write_text(json.dumps(old,separators=(',',':')))
assert nb.stat().st_size<30000,nb.stat().st_size
assert all(c['cell_type']=='code' for c in old['cells'][1:])
assert HASH in ''.join(old['cells'][2]['source'])
assert HASH in ''.join(old['cells'][3]['source'])
out={'controller':'E126 hybrid_trained','source_sha256':HASH,'source_bytes':len(source),
 'kernel_id':NEW_KERNEL,'dataset_id':NEW_DATASET,
 'notebook_sha256':hashlib.sha256(nb.read_bytes()).hexdigest(),
 'notebook_bytes':nb.stat().st_size,
 'frozen_source_sha256':OLD_HASH,
 'local_native_parity_verified_by':'e128_release_20261027/verify_release.py',
 'real_kaggle_score':None,'submitted':False}
(BASE/'submission_manifest.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2),flush=True)
print('E126_KAGGLE_PACKAGE_READY',flush=True)
