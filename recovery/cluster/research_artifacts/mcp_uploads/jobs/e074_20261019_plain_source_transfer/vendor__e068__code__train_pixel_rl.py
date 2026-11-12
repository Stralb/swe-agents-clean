"""Actual native-reward training with explicit BC / AWR / shuffled controls.

This is offline advantage-weighted regression (AWR), NOT PPO and NOT a
fully demonstrated unseen-game RL agent. Inputs are only permitted native
observation frames and legal actions. No game identifier or route input.
"""
from __future__ import annotations
import argparse,hashlib,json,math,random
from pathlib import Path
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
BASE=Path(__file__).resolve().parents[1]
DATA=BASE/'data'/'native_self_play_5.npz'
TRAIN_FAMILIES=['sb26','s5i5','lf52','tn36','g50t']

class PixelPolicy(nn.Module):
 def __init__(self):
  super().__init__()
  self.enc1=nn.Sequential(nn.Conv2d(16,24,3,stride=1,padding=1),nn.GroupNorm(6,24),nn.SiLU())
  self.enc2=nn.Sequential(nn.Conv2d(24,32,3,stride=1,padding=1),nn.GroupNorm(8,32),nn.SiLU())
  self.enc3=nn.Sequential(nn.Conv2d(32,48,3,stride=2,padding=1),nn.GroupNorm(8,48),nn.SiLU())
  self.head=nn.Sequential(nn.Linear(48,96),nn.SiLU(),nn.Linear(96,8))
  self.click=nn.Conv2d(32,1,1)
  self.value=nn.Sequential(nn.Linear(48,64),nn.SiLU(),nn.Linear(64,1))
 def forward(self,frames):
  f=frames[:,::4,::4].long().clamp(0,15)
  z=F.one_hot(f,16).permute(0,3,1,2).float()
  x=self.enc1(z);x=self.enc2(x)
  point=self.click(x).flatten(1)
  state=F.adaptive_avg_pool2d(self.enc3(x),(1,1)).flatten(1)
  return self.head(state),point,self.value(state).squeeze(-1)

def returns(d,reward_override=None,gamma=.98):
 """Discounted *observed* native level increments, never synthetic L1 labels.
 Reward cannot cross native WIN, GAME_OVER, level increments, paid reset or
 family/session boundaries; stored SDK `session_step` preserves skipped RESET.
 """
 r=d['reward'] if reward_override is None else reward_override
 f=d['family'];steps=d['session_step'];terminal=d['terminal'];n=len(r)
 q=np.zeros(n,dtype=np.float32);val=0.
 for i in range(n-1,-1,-1):
  if i==n-1 or f[i]!=f[i+1] or steps[i+1]!=steps[i]+1 or terminal[i]:val=0.
  val=float(r[i])+gamma*val
  q[i]=val
 return q

def shuffled_rewards(d,seed=2068):
 rng=np.random.default_rng(seed)
 r=np.asarray(d['reward'],dtype=np.float32).copy()
 # shuffle positive events within each original game-family group; don't
 # create new positive rewards or import evaluation game trajectories.
 for family in np.unique(d['family']):
  ids=np.flatnonzero(d['family']==family)
  r[ids]=rng.permutation(r[ids])
 assert r.sum()==d['reward'].sum()
 return r

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as fp:
  while b:=fp.read(1<<20):h.update(b)
 return h.hexdigest()

def train(mode='bc',seed=2068,steps=850,batch=96,dataset_path=None,output_dir=None,source_type=None):
 if mode not in ('bc','awr','shuffled'):raise ValueError(mode)
 torch.set_num_threads(2);torch.manual_seed(seed);rng=np.random.default_rng(seed)
 dataset_path=Path(dataset_path) if dataset_path is not None else DATA
 output_dir=Path(output_dir) if output_dir is not None else BASE/'checkpoints'
 d=np.load(dataset_path,allow_pickle=False)
 assert set(d.files)==set(['frame','next_frame','action','xy','reward','terminal','legal','next_legal','family','session_step'])
 assert set(np.unique(d['family']))==set(range(5))
 native_returns=returns(d)
 sreturn=returns(d,shuffled_rewards(d,seed)) if mode=='shuffled' else native_returns
 training_weights=np.ones(len(sreturn),dtype=np.float32)
 if mode!='bc':training_weights=np.exp(np.minimum(2.,4.*sreturn)).astype(np.float32)
 model=PixelPolicy();opt=torch.optim.AdamW(model.parameters(),lr=.0006,weight_decay=.0001)
 loss_trace=[];obs=d['frame'];act=d['action'];valid=d['legal'];coords=d['xy'];clicks=(act==6)
 for j in range(steps):
  ids=rng.integers(0,len(act),size=batch)
  x=torch.from_numpy(obs[ids]);a=torch.from_numpy(act[ids].astype(np.int64))
  legal=torch.from_numpy(valid[ids]);w=torch.from_numpy(training_weights[ids])
  alog,point,v=model(x)
  alog=alog.masked_fill(~legal,-1e4)
  loss_a=F.cross_entropy(alog,a,reduction='none')
  loss_a=(loss_a*w).sum()/w.sum().clamp(min=1.)
  cmask=np.flatnonzero(clicks[ids] & (coords[ids,0]>=0) & (coords[ids,1]>=0))
  if len(cmask):
   pos=(coords[ids[cmask],1]//4)*16 + coords[ids[cmask],0]//4
   ce=F.cross_entropy(point[cmask],torch.from_numpy(pos.astype(np.int64)),reduction='none')
   ww=w[cmask];loss_xy=(ce*ww).sum()/ww.sum().clamp(min=1.)
  else:loss_xy=torch.tensor(0.)
  qtarget=torch.from_numpy(sreturn[ids]);vloss=F.smooth_l1_loss(v,qtarget)
  loss=loss_a+0.3*loss_xy+(0.15*vloss if mode!='bc' else 0.)
  opt.zero_grad();loss.backward();nn.utils.clip_grad_norm_(model.parameters(),1.);opt.step()
  if (j+1)%100==0:loss_trace.append({'update':j+1,'action_loss':round(float(loss_a.detach()),4),'point_loss':round(float(loss_xy.detach()),4),'value_loss':round(float(vloss.detach()),4)})
 path=output_dir/f'native_pixel_{mode}.pt'
 path.parent.mkdir(parents=True,exist_ok=True)
 torch.save({'state_dict':model.state_dict(),'mode':mode,'steps':steps,'seed':seed,
             'dataset_sha256':sha(dataset_path),'train_families':TRAIN_FAMILIES,
             'native_positive_events':int(d['reward'].sum()),
             'method':'BC' if mode=='bc' else 'reward-weighted offline actor critic (AWR)' if mode=='awr' else 'AWR with shuffled native rewards'},path)
 audit={'checkpoint':str(path),'sha256':sha(path),'native_dataset':sha(dataset_path),
        'source_type':source_type or 'agent-generated native SDK, no teacher demonstrations',
        'mode':mode,'seed':seed,'updates':steps,'native_reward_events':int(d['reward'].sum()),
        'training_examples':len(d['action']),'clicked_examples':int(clicks.sum()),
        'discounted_nonzero_returns':int((sreturn>0).sum()),
        'reward_weights_nontrivial':int(np.count_nonzero(training_weights!=1.)),
        'loss_trace':loss_trace}
 (output_dir/f'pixel_{mode}_training.json').write_text(json.dumps(audit,indent=2)+'\n')
 print('TRAINED',mode,json.dumps(audit,default=str),flush=True)
 return audit

def load_model(path):
 ck=torch.load(path,map_location='cpu',weights_only=False);m=PixelPolicy();m.load_state_dict(ck['state_dict']);m.eval();return m,ck

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['bc','awr','shuffled','all'],default='all');p.add_argument('--steps',type=int,default=850);a=p.parse_args()
 for mode in ['bc','awr','shuffled'] if a.mode=='all' else [a.mode]:train(mode=mode,steps=a.steps)
