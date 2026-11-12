#!/bin/bash
#SBATCH --job-name=E108_frame_contract
#SBATCH --partition=stampede
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:08:00
set -euo pipefail
umask 077
export OPENBLAS_NUM_THREADS=1 PYTHONUNBUFFERED=1
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
from pathlib import Path
import sys,json,logging,hashlib,numpy as np
logging.disable(logging.CRITICAL)
H=Path('/home-mscluster/astrauss');S=H/'research_artifacts/mcp_uploads/jobs/e108_20261020_random_rounds'
sys.path[:0]=[str(H/'RL-ARC-AGI-3-Project'),str(S),str(H/'research_artifacts/mcp_uploads/jobs/e106_20261020_general_agent')]
from src.adapter import ArcSession,RawFrame
from E106_perception_v0 import candidates,descriptor
from policy_r3 import Agent
class SnapshotSession(ArcSession):
 def _send(self,action_id,xy):
  r=super()._send(action_id,xy)
  return RawFrame([np.array(f,copy=True) for f in r.frames],r.state,r.levels_completed,r.win_levels,list(r.available_actions))
 def _reset(self):
  r=super()._reset()
  return RawFrame([np.array(f,copy=True) for f in r.frames],r.state,r.levels_completed,r.win_levels,list(r.available_actions))
selection=json.loads((H/'e108_random_development_rounds/round_04/SELECTION_FROZEN.json').read_text())
records=[]
for game in selection['selected_games']:
 for kind,cls in [('original',ArcSession),('snapshot',SnapshotSession)]:
  s=cls();s.start_run(game,40,0);a=Agent(28901,candidates,descriptor)
  errors=[];states=[];transitions=0
  while not s.done:
   before=np.array(s.obs.frame,copy=True)
   idx,why,belief=a.decide(s.obs.frame,s.obs.mask)
   t=s.step(idx);transitions+=1
   mutated=int(np.count_nonzero(before!=t.obs.frame))
   if mutated:errors.append({'decision':transitions,'action_index':idx,'previous_observation_pixels_changed':mutated})
   try:a.update(t.obs.frame,t.next_obs.frame,idx,t.reward,t.reward>0,t.terminal)
   except AssertionError:
    a.episode_reset()
   if t.terminal and not s.done:a.episode_reset()
   states.append(hashlib.sha256(before.tobytes()).hexdigest())
  rec={'game':game,'condition':kind,'public_transition_old_frame_mutations':errors,'transitions':transitions,'gameplay_actions':s.tracker.actions}
  records.append(rec);print('FRAME_CONTRACT_RESULT',json.dumps(rec,sort_keys=True),flush=True)
assert all(not r['public_transition_old_frame_mutations'] for r in records if r['condition']=='snapshot')
assert any(r['public_transition_old_frame_mutations'] for r in records if r['condition']=='original')
p=H/'research_artifacts/mcp_uploads/jobs/e108_20261020_frame_contract/FRAME_ALIAS_FINDINGS.json'
with p.open('x') as f:json.dump({'scope':'public before/after observations only','records':records},f,indent=2)
print('FRAME_SNAPSHOT_FIX_VERIFIED',str(p),flush=True)
PY
