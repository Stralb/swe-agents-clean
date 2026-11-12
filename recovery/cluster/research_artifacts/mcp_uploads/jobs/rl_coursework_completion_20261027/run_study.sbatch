#!/bin/bash
#SBATCH --job-name=rl-six-arm-native
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:45:00
#SBATCH --array=0-23%8
set -euo pipefail
umask 077
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/rl_coursework_completion_20261027
export PYTHONPATH=/home-mscluster/astrauss/RL-ARC-AGI-3-Project:/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026/runtime/python_site
cd /home-mscluster/astrauss/RL-ARC-AGI-3-Project
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
"$PY" - "$SLURM_ARRAY_TASK_ID" "$ROOT/records" <<'PY'
import collections,dataclasses,hashlib,json,math,sys
from pathlib import Path
import numpy as np
from src.ppo import PPO
from src.dqn_v1.learner import DQNV1
from src.config import RunConfig
from src.run import run

class PPOVariant(PPO):
    def __init__(self,arch,params,variant):
        super().__init__(arch,params)
        self.variant=variant
    def start_run(self,seed):
        super().start_run(seed)
        self.count=collections.Counter();self.bonus_sum=0.;self.click_count=0;self.fg_click=0;self.mask_count=0
    def act(self,o):
        if self.variant=='I2' and np.any(o.mask[6:]):
            flat=o.frame.reshape(-1).astype(np.int64)
            hist=np.bincount(flat,minlength=16)
            if hist.max()>=0.65*flat.size:
                fg=(flat!=int(hist.argmax()))
                mask=o.mask.copy();mask[6:] &= fg
                if mask[6:].sum()>=4:
                    o=dataclasses.replace(o,mask=mask);self.mask_count+=1
        idx=super().act(o)
        if idx>=6:
            self.click_count+=1
            flat=o.frame.reshape(-1).astype(np.int64)
            self.fg_click+=int(flat[idx-6]!=np.bincount(flat,minlength=16).argmax())
        return idx
    def observe(self,t):
        if self.variant!='V0':
            key=hashlib.blake2s(t.next_obs.frame[::4,::4].tobytes(),digest_size=12).digest()
            self.count[key]+=1
            if t.info.get('frame_changed',False):
                bonus=.02/math.sqrt(self.count[key]);self.bonus_sum+=bonus
                t=dataclasses.replace(t,reward=t.reward+bonus)
        return super().observe(t)
    def diagnostics(self):
        return {**super().diagnostics(),'variant':self.variant,'intrinsic_bonus':self.bonus_sum,
                'distinct_coarse_frames':len(self.count),'masked_states':self.mask_count,
                'fg_click_fraction':self.fg_click/max(self.click_count,1)}

class StallDQN(DQNV1):
    def start_run(self,seed):
        super().start_run(seed);self.rescued=0
    def act(self,o):
        if self.since_progress<96:return super().act(o)
        old=self.agent.epsilon
        self.agent.epsilon=lambda:max(.75,old())
        try:
            self.rescued+=1
            return super().act(o)
        finally:self.agent.epsilon=old
    def diagnostics(self):
        return {**super().diagnostics(),'variant':'I2','rescue_trigger':96,
                'epsilon_floor':.75,'rescue_decisions':self.rescued}

task=int(sys.argv[1]);root=Path(sys.argv[2]);root.mkdir(parents=True,exist_ok=True)
games=['ar25','g50t','s5i5','vc33'];seeds=[301,302,303]
algo='dqn' if task<12 else 'ppo'; i=task%12;game=games[i%4];seed=seeds[i//4]
print('TASK',task,algo,game,seed,flush=True)
for arm in ('V0','I1','I2'):
    dest=root/f'{algo}_{arm}_{game}_{seed}.json'
    if dest.exists():
        print('ALREADY_PRESENT',dest.name,flush=True);continue
    if algo=='ppo':
        c=RunConfig(algo='ppo',version=arm,game=game,seed=seed,env_seed=47,budget=256,threads=1,
                    params={'rollout':64},tag='matched_public_20261027')
        lr=PPOVariant(c.resolved().arch,c.resolved().params,arm)
    elif arm=='V0':
        c=RunConfig(algo='dqn',version='V0',game=game,seed=seed,env_seed=47,budget=256,threads=1,
                    params={'warmup':16,'batch':8,'train_every':8,'target_update':80,
                            'replay_capacity':2048,'eps_decay_actions':300},tag='matched_public_20261027')
        lr=None
    else:
        c=RunConfig(algo='dqn',version='V1',game=game,seed=seed,env_seed=47,budget=256,threads=1,
                    tag='matched_public_20261027_'+arm)
        lr=StallDQN(game,c.resolved().params) if arm=='I2' else DQNV1(game,c.resolved().params)
    rec=run(c,learner=lr)
    rec.pop('_learner',None);rec.pop('scorecard',None)
    rec['study']={'game':game,'algorithm':algo,'arm':arm,'policy_seed':seed,
                  'native_seed':47,'public_exposure':'previously studied public',
                  'max_scorer_actions':256}
    dest.write_text(json.dumps(rec,indent=2,default=float))
    print('RESULT',dest.name,'status',rec['status'],'error',rec['error'],
          'score',(rec['official_score'] or {}).get('score'),
          'levels',(rec['official_score'] or {}).get('levels_completed'),
          'actions',rec['counters']['scorer_actions'],
          'grad_steps',rec['learner'].get('gradient_steps'),
          'wall',rec['cost']['wall_s'],flush=True)
print('TASK_COMPLETE',task,flush=True)
PY
