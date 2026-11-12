#!/usr/bin/env python3
"""Package verified E126 as a self-contained offline Kaggle notebook and agent."""
from __future__ import annotations
import base64,hashlib,json,runpy,shutil,textwrap,zlib
from pathlib import Path
ROOT=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs')
HERE=ROOT/'e128_release_20261027'
OUT=HERE/'release'
OUT.mkdir(parents=True,exist_ok=True)
FROZEN=ROOT/'n117_kaggle_20261026_dataset1/private_dataset/my_agent.py'
PEER=Path('/home-mscluster/astrauss/RL-ARC-AGI-3-Project/assets/dqn_v1/checkpoints/E-onehotcnn__T-stack2__A-vector__U-effect__f0__s11.pt')
FSHA='0663845070e47a053076db54243c3445921a06b4bf0908b7b233c263da423bfa'
PSHA='c5882f664b082aa131023ac1ffaebeb771ba7fe181fa909730fe1c641e5978b9'
assert hashlib.sha256(FROZEN.read_bytes()).hexdigest()==FSHA
assert hashlib.sha256(PEER.read_bytes()).hexdigest()==PSHA
frozen=FROZEN.read_text()
template=runpy.run_path(str(HERE/'e126_template.py'))['E126_EXTENSION']
compressed=zlib.compress(PEER.read_bytes(),level=9)
encoded=base64.b85encode(compressed).decode('ascii')
weights="\n".join('    '+repr(part) for part in textwrap.wrap(encoded,110))
assert template.count('__E126_B85__')==1
extension=template.replace('__E126_B85__',weights)
full=frozen+'\n'+extension+'\n'
assert full.startswith(frozen)
compile(full,str(OUT/'my_agent.py'),'exec')
(OUT/'my_agent.py').write_text(full)
shutil.copyfile(PEER,OUT/'e126_effect_prior.pt')
def cell(source):
    return {'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],'source':source}
def md(source):
    return {'cell_type':'markdown','metadata':{},'source':source}

install=('!pip install --no-index --find-links '
  '/kaggle/input/competitions/arc-prize-2026-arc-agi-3/arc_agi_3_wheels '
  'arc-agi python-dotenv')

# Official ARC-AGI-3-Kaggle-Starter code-competition notebook workflow.
run="""import os
if os.getenv('KAGGLE_IS_COMPETITION_RERUN'):
    !curl --fail --retry 999 --retry-all-errors --retry-delay 5 --retry-max-time 600 http://gateway:8001/api/games
    !cp -r /kaggle/input/competitions/arc-prize-2026-arc-agi-3/ARC-AGI-3-Agents /kaggle/working/ARC-AGI-3-Agents
    !cp /tmp/my_agent.py /kaggle/working/ARC-AGI-3-Agents/agents/templates/my_agent.py
    with open('/kaggle/working/ARC-AGI-3-Agents/agents/__init__.py','w') as f:
        f.write('''from typing import Type
from dotenv import load_dotenv
from .agent import Agent, Playback
from .swarm import Swarm
from .templates.random_agent import Random
from .templates.my_agent import MyAgent

load_dotenv()
AVAILABLE_AGENTS: dict[str, Type[Agent]] = {
    'random': Random,
    'myagent': MyAgent,
}
''')
    with open('/kaggle/working/ARC-AGI-3-Agents/.env','w') as f:
        f.write('''SCHEME=http
HOST=gateway
PORT=8001
ARC_API_KEY=REDACTED_CREDENTIAL
ARC_BASE_URL=http://gateway:8001/
OPERATION_MODE=online
ENVIRONMENTS_DIR=
RECORDINGS_DIR=/kaggle/working/server_recording
''')
    !cd /kaggle/working/ARC-AGI-3-Agents && MPLBACKEND=agg python main.py --agent myagent
"""
fallback="""import os
if not os.getenv('KAGGLE_IS_COMPETITION_RERUN'):
    import pandas as pd
    dummy = pd.DataFrame(
        [['1_0','1',True,1]],
        columns=['row_id','game_id','end_of_game','score'])
    dummy.to_parquet('/kaggle/working/submission.parquet',index=False)
    dummy.head()
"""
notebook={
 'nbformat':4,
 'nbformat_minor':5,
 'metadata':{
    'kernelspec':{'name':'python3','display_name':'Python 3','language':'python'},
    'language_info':{'name':'python'},
    'kaggle':{'accelerator':'none','isGpuEnabled':False,
             'isInternetEnabled':False,'language':'python','sourceType':'notebook'},
 },
 'cells':[
    md('# E126 ARC-AGI-3 candidate (NOT SUBMITTED)\n\n'
       'N117 + trained teammate effect prior on sparse click-only scenes, '
       'with local action-effect/rarity ranking elsewhere. '
       'Public SDK improvement does not establish hidden Kaggle improvement.'),
    cell(install),
    cell('%%writefile /tmp/my_agent.py\n'+full),
    cell(run),
    cell(fallback)
 ]
}
nb=OUT/'E126_Kaggle_Candidate.ipynb'
nb.write_text(json.dumps(notebook,separators=(',',':')))
summary={
 'variant':'E126 hybrid_trained','status':'candidate_not_submitted',
 'frozen_n117_sha256':FSHA,'peer_effect_checkpoint_sha256':PSHA,
 'full_agent_sha256':hashlib.sha256(full.encode()).hexdigest(),
 'notebook_sha256':hashlib.sha256(nb.read_bytes()).hexdigest(),
 'git_blob_sha1_of_frozen_source':hashlib.sha1(b'blob '+str(len(FROZEN.read_bytes())).encode()+b'\0'+FROZEN.read_bytes()).hexdigest(),
 'policy_seed':76,'modal_colour_threshold':.80,'no_inference_network':True,
 'public_games':25,'official_kaggle_submission':False,
 'local_public_sdk_seed76_to78':[2.2115182587,2.2239424189,2.2407370400],
 'local_public_sdk_baseline_seed76_to78':[2.0932423408,2.054775023,2.0964346368],
 'caveat':'The 80 percent threshold was selected using previously exposed games; no hidden score guarantee.'
}
(OUT/'manifest.json').write_text(json.dumps(summary,indent=2)+'\n')
for p in sorted(OUT.iterdir()):
    if p.is_file():
        print('E128_ARTIFACT',p.name,p.stat().st_size,
          hashlib.sha256(p.read_bytes()).hexdigest(),flush=True)
print('E128_FROZEN_GIT_BLOB',summary['git_blob_sha1_of_frozen_source'],flush=True)
print('E128_BUILD_COMPLETE',flush=True)
