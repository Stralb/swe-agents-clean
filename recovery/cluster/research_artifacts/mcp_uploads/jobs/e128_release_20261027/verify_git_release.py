#!/usr/bin/env python3
"""Verify Git release exact regeneration and all staged file provenance.
Never push; fail closed if any unexpected file or frozen-baseline change.
"""
import hashlib,json,os,subprocess,sys
from pathlib import Path
H=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e128_release_20261027')
G=H/'git_checkout'
OUT=H/'git_portable_rebuild'
SRC=G/'src/e126_submission_agent.py'
NB=G/'notebooks/E126_Kaggle_Candidate.ipynb'
MODEL=G/'assets/e126/effect_prior_s11.pt'
FROZEN=G/'src/best_public_agent.py'
AGENT_SHA='84f27a2589575558ddb85dff2539f68d1937c6dc1a048cb3b133f6ae7005178c'
NOTEBOOK_SHA='6bbbbc5c4011d5c781e24065e70f8fea731250c07e994980c932fad41ee30b56'
MODEL_SHA='c5882f664b082aa131023ac1ffaebeb771ba7fe181fa909730fe1c641e5978b9'
FROZEN_SHA='0663845070e47a053076db54243c3445921a06b4bf0908b7b233c263da423bfa'
MAIN='31d5b3ad6d52f61f1e02ff1b2eddfcfd59d2c2c3'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(SRC)==AGENT_SHA
assert sha(NB)==NOTEBOOK_SHA
assert sha(MODEL)==MODEL_SHA
assert sha(FROZEN)==FROZEN_SHA
assert SRC.read_bytes().startswith(FROZEN.read_bytes()),'N117 not exact prefix'
assert (G/'experiments/E126/e126_template.py').is_file()
env=dict(os.environ,E126_OUTPUT_DIR=str(OUT),GIT_TERMINAL_PROMPT='0')
cmd=['python3',str(G/'experiments/E126/build_candidate.py')]
p=subprocess.run(cmd,text=True,capture_output=True,env=env,cwd=str(G),timeout=120)
print('PORTABLE_BUILD_EXIT',p.returncode,flush=True)
if p.returncode:
    print(p.stdout[-4000:],p.stderr[-4000:],flush=True)
    raise RuntimeError('Rebuild failed')
assert sha(OUT/'my_agent.py')==AGENT_SHA,'Agent not reproducible'
assert sha(OUT/'E126_Kaggle_Candidate.ipynb')==NOTEBOOK_SHA,'Notebook not reproducible'
assert sha(OUT/'e126_effect_prior.pt')==MODEL_SHA
nb=json.loads(NB.read_text())
assert nb['nbformat']==4 and len(nb['cells'])==5
assert nb['metadata']['kaggle']['isInternetEnabled'] is False
assert nb['metadata']['kaggle']['isGpuEnabled'] is False
assert nb['cells'][2]['source']=='%%writefile /tmp/my_agent.py\n'+SRC.read_text()
assert 'KAGGLE_IS_COMPETITION_RERUN' in nb['cells'][3]['source']
assert '/kaggle/input/competitions/arc-prize-2026-arc-agi-3/' in nb['cells'][1]['source']
assert '/home-mscluster/' not in SRC.read_text()
assert '/home-mscluster/' not in NB.read_text()
assert 'curl --fail' in nb['cells'][3]['source']
assert 'ARC-AGI-3-Agents' in nb['cells'][3]['source']
print('E128_REGENERATED_SHA256',AGENT_SHA,NOTEBOOK_SHA,MODEL_SHA,flush=True)
p=subprocess.run(['git','-C',str(G),'status','--short'],capture_output=True,text=True,check=True)
print('STAGED_GIT_STATUS',p.stdout[:9000],flush=True)
assert not p.stdout.startswith(' M src/best_public_agent.py')
# No unexpected modifications to historical N117 code.
p=subprocess.run(['git','-C',str(G),'diff','--','src/best_public_agent.py'],capture_output=True,text=True,check=True)
assert not p.stdout
files=list(G.rglob('*.py'))
assert len(files)>0
print('E128_PORTABLE_RELEASE_FULLY_VERIFIED',flush=True)
