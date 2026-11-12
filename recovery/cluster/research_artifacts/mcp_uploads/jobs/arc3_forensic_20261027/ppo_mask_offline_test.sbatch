#!/bin/bash
#SBATCH --job-name=arc3-ppo-audit
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:07:00
set -euo pipefail
umask 077
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH=/home-mscluster/astrauss/RL-ARC-AGI-3-Project:/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026/runtime/python_site
cd /home-mscluster/astrauss/RL-ARC-AGI-3-Project
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
"$PY" - <<'PY'
from pathlib import Path
import hashlib,math,sys,torch
import numpy as np
from src.adapter import Observation,Transition,N_SIMPLE,N_ACTIONS
from src.config import RunConfig
from src.model import collate
from src.ppo import evaluate_actions,compute_gae
from src.dqn_v1.agent import DQNAgent
p=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/rl_coursework_completion_20261027/run_study.sbatch')
src=p.read_text();head=src.split("<<'PY'\n",1)[1].rsplit('\nPY',1)[0].split('task=int(sys.argv[1])')[0]
ns={};exec(compile(head,'frozen_matched_study','exec'),ns)
PPOVariant=ns['PPOVariant']
c=RunConfig(algo='ppo',game='s5i5',version='I2',seed=302,env_seed=47,params={'rollout':8}).resolved()
frame=np.zeros((64,64),dtype=np.int8)
frame[2:6,2:6]=1
frame[12:14,12:14]=2
m=np.zeros(N_ACTIONS,dtype=bool);m[N_SIMPLE:]=True
obs=Observation(frame=frame,prev_frame=frame,mask=m,prev_action=-1,progress=0,high_water=0,win_levels=6)
model=PPOVariant(c.arch,c.params,'I2')
model.start_run(302)
before={k:v.detach().clone() for k,v in model.net.state_dict().items()}
obs_list=[]
for i in range(8):
    idx=model.act(obs)
    used,selected,old_lp,val=model._pending
    assert idx>=N_SIMPLE and frame[(idx-N_SIMPLE)//64,(idx-N_SIMPLE)%64]!=0,(i,idx)
    assert int(used.mask[N_SIMPLE:].sum())==20
    assert used.mask[:N_SIMPLE].tolist()==m[:N_SIMPLE].tolist()
    lp,ent,_=evaluate_actions(model.net,collate([used]),torch.tensor([idx]))
    assert math.isfinite(float(lp[0])) and math.isfinite(float(ent[0]))
    assert abs(float(lp[0])-old_lp)<1e-5,('mismatched_logprobs',i,float(lp[0]),old_lp)
    nxt=Transition(obs=obs,action=idx,reward=0.0,next_obs=obs,terminal=False,truncated=False,
                   info={'frame_changed':False,'state':'NOT_FINISHED'})
    model.observe(nxt)
print('PPO_I2_RECOMPUTED_MASKED_LOGP_PASS',8,'foreground_count',int(used.mask[N_SIMPLE:].sum()),flush=True)
print('PPO_I2_TRAINING_UPDATES',model.diagnostics()['gradient_steps'],
      'rollout_events',model.diagnostics()['rollout_update_events'],flush=True)
assert model.diagnostics()['gradient_steps']>0
params_changed=sum(not torch.equal(before[k],v) for k,v in model.net.state_dict().items())
print('PPO_I2_TRAINABLE_TENSORS_CHANGED',params_changed,flush=True)
assert params_changed>0
s=compute_gae(np.array([1.,2.,3.],np.float32),np.array([.1,.2,.3],np.float32),np.array([0.,1.,0.],np.float32),
              0.4,0.99,0.95)
assert np.isfinite(s).all()
assert abs(float(s[1]) - (2-.2))<1e-6
print('PPO_GAE_TERMINAL_BOUNDARY_PASS',s.tolist(),flush=True)
for n in (90,100,112,160,255):
    base=max(.1,1.0+(0.1-1.0)*n/400)
    print('DQN_I2_EPSILON_AT_ACTION',n,'baseline',round(base,5),
          'stall_ge96',round(max(.75,base),5),
          'floor_changes_probability',bool(n>=96 and base<.75),flush=True)
print('SRC_SHA256',{k:hashlib.sha256(Path(k).read_bytes()).hexdigest() for k in ['src/ppo.py','src/dqn.py','src/dqn_v1/agent.py','src/dqn_v1/learner.py','src/model.py','src/adapter.py']},flush=True)
print('OFFLINE_POLICY_PROBABILITY_TEST_COMPLETE',flush=True)
PY