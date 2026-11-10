#!/usr/bin/env python3
"""Release-gate tests: frozen source, pretrained checkpoint, score exactness,
official notebook structure, and native trace parity against stored E126.
"""
import hashlib,importlib.util,json,os,sys
from pathlib import Path
ROOT=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs')
BASE=ROOT/'e128_release_20261027'
OUT=BASE/'release'
E121=ROOT/'click_diversity_e121_20261026'
E126=ROOT/'click_hybrid_e126_20261026'
FROZEN=ROOT/'n117_kaggle_20261026_dataset1/private_dataset/my_agent.py'
sys.path.insert(0,str(E121))
import run_e121 as R
import numpy as np
import torch

def loaded_module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m
    spec.loader.exec_module(m)
    return m

release_source=OUT/'my_agent.py'
source=release_source.read_text()
assert source.startswith(FROZEN.read_text())
assert hashlib.sha256(FROZEN.read_bytes()).hexdigest()==R.SHA
assert '/home-mscluster/' not in source
assert 'self.game_id.split' not in source[len(FROZEN.read_text()):]
m=loaded_module(release_source,'e128_submission_agent')
assert m._PEER_SHA_126=='c5882f664b082aa131023ac1ffaebeb771ba7fe181fa909730fe1c641e5978b9'
trained=m._effect_model_126()
assert type(trained).__name__=='_Effect126'
ref=torch.load(OUT/'e126_effect_prior.pt',map_location='cpu',weights_only=True)['state_dict']
assert set(trained.state_dict())==set(ref)
assert all(torch.equal(v,ref[k]) for k,v in trained.state_dict().items())
print('CHECKPOINT_AND_MODEL_HASH_OK',flush=True)
# Reference model is the exact E123, not a separately inferred architecture.
E123=ROOT/'teammate_prior_e123_20261026'
sys.path.insert(0,str(E123))
import run_e123_v2 as P
g=np.zeros((64,64),np.uint8)
g[10:20,10:20]=4
g[31:34,35:38]=12
prev=np.roll(g,1,axis=1)
actions=np.asarray([0,1,2,3,4,5,6+10*64+10,6+18*64+12,6+32*64+36,6+40*64+40])
truth=P.peer_scores(P.model_for('trained'),g,prev,actions)
actual=m._effect_scores_126(trained,g,prev,actions)
assert set(truth)==set(actual)
assert max(abs(truth[k]-actual[k]) for k in truth)<1e-10
print('EXACT_E123_PEER_SCORE_PARITY_OK',flush=True)
notebook=json.loads((OUT/'E126_Kaggle_Candidate.ipynb').read_text())
assert len(notebook['cells'])==5 and notebook['nbformat']==4
assert notebook['metadata']['kaggle']['isInternetEnabled'] is False
assert notebook['cells'][2]['source']=='%%writefile /tmp/my_agent.py\n'+source
assert 'KAGGLE_IS_COMPETITION_RERUN' in notebook['cells'][3]['source']
assert '/kaggle/input/competitions/arc-prize-2026-arc-agi-3/' in notebook['cells'][1]['source']
assert notebook['metadata']['kaggle']['isGpuEnabled'] is False
print('OFFLINE_NOTEBOOK_STRUCTURE_OK',flush=True)

# Reference E126 experiment is intentionally NOT imported here: we verify
# candidate from its independently generated module against frozen traces.
# R.original is the frozen agent module used by original E121 runner.
R.original.AuditedCrossLevelCore=m.E126Core
R.ARMS=tuple(dict.fromkeys(R.ARMS+('hybrid_trained',)))
R.apply_arm=lambda arm:None

def one(seed,game):
    actual=R.run(game,'hybrid_trained',seed_policy=seed,seed_native=47)
    stored=json.loads((E126/'results'/('seed'+str(seed))/'hybrid_trained'/(game+'.json')).read_text())
    got=actual['trajectory'];target=stored['trajectory']
    assert len(got)==len(target),(seed,game,'length',len(got),len(target))
    for i,(a,b) in enumerate(zip(got,target),1):
        for key in ('a','pre','post','reward','level'):
            assert a[key]==b[key],(seed,game,i,key,a[key],b[key])
    x=actual['summary'];y=stored['summary']
    for key in ('levels_completed','charged_sdk_actions','wins','l1','l2','l3plus'):
        assert x[key]==y[key],(seed,game,key,x[key],y[key])
    print('NATIVE_TRACE_PARITY',seed,game,'levels',x['levels_completed'],
          'actions',x['charged_sdk_actions'],flush=True)
    return len(got)
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--full',action='store_true')
    parser.add_argument('--seeds',nargs='*',type=int,default=[76,77,78])
    args=parser.parse_args()
    games=list(R.FAMILIES) if args.full else ['lf52','s5i5','vc33','tn36','r11l']
    total=0;count=0
    for seed in args.seeds:
        for game in games:
            total+=one(seed,game)
            count+=1
    print('E128_PARITY_SUCCESS',count,'EPISODES',total,'ACTIONS',flush=True)
