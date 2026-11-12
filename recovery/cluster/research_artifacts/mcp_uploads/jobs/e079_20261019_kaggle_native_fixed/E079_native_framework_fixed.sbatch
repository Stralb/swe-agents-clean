#!/bin/bash
#SBATCH --job-name=E079_kaggle_fixed
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:15:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
"$PY" - <<'PY'
import hashlib,importlib.util,json,sys,types
from pathlib import Path
ROOT=Path('/home-mscluster/astrauss/RL-ARC-AGI-3-Project')
SOURCE=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e079_20261019_kaggle_contract/my_agent.py')
EXP='2702a91dfd56423776dd7fd5db641e5e492c22b81260d2c0e31c159090b4f989'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==EXP
vendor=ROOT/'vendor/ARC-AGI-3-Agents/agents'
if not (vendor/'agent.py').is_file():
 raise FileNotFoundError('Missing official Agents framework in project vendor: '+str(vendor))
pkg=types.ModuleType('agents');pkg.__path__=[str(vendor)];sys.modules['agents']=pkg
import arc_agi
from arc_agi import OperationMode
from arcengine import GameState
spec=importlib.util.spec_from_file_location('kaggle_candidate_exact',SOURCE)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
agentcls=mod.MyAgent
assert agentcls.MAX_ACTIONS==240
arc=arc_agi.Arcade(operation_mode=OperationMode.NORMAL)
env=arc.make('vc33')
agent=agentcls(card_id='E079_source_only',game_id='vc33',agent_name='E079_candidate',
  ROOT_URL='',record=False,arc_env=env,tags=['E079_course_dev'])
agent.MAX_ACTIONS=160
old_take=agent.take_action
actions=[]
def take(action):
 raw=old_take(action)
 data=action.action_data.model_dump()
 actions.append({'a':int(action.value),'xy':[data.get('x'),data.get('y')] if int(action.value)==6 else None,
   'levels':int(raw.levels_completed),'state':str(raw.state.value)})
 return raw
agent.take_action=take
print('E079_VALIDATED_KAGGLE_CALLBACK_START','seed',mod.SEED,'game','vc33',flush=True)
agent.main()
counter=agent.action_counter
res={'job':'E079_NATIVE_AGENTS_FRAMEWORK_DEV',
 'kaggle_src_sha256':EXP,'game':'vc33','seed':mod.SEED,
 'callbacks_executed':counter,'actions_observed':len(actions),
 'real_levels':int(agent.levels_completed),
 'win':bool(agent.state is GameState.WIN),
 'event_repeat_stats':dict(agent.controller.stats),
 'legal_click_count':sum(a['a']==6 for a in actions),
 'no_train_updates':True,'one_public_development_game_only':True,
 'kaggle_submission_committed':False,'kaggle_score_claimed':False,
 'first_12_actions':actions[:12]}
print('E079_NATIVE_RESULT',json.dumps(res,sort_keys=True),flush=True)
assert len(actions)>0
assert all(a['a'] in range(0,8) for a in actions)
assert len(actions)==agent.action_counter
PY