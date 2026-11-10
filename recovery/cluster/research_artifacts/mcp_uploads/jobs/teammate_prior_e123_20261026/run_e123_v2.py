#!/usr/bin/env python3
"""E123: transfer the teammate's frozen one-hot CNN action-effect prior into N117.
Original N117 reward, policy weights, candidate set and Bellman updates unchanged.
No game-identifier dispatch, LLM, game-engine access or uncharged probes.
"""
from __future__ import annotations
import argparse,collections,functools,hashlib,json,math,os,sys,traceback
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from torch import nn
from scipy import ndimage as ndi
E121=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026')
BASE=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/teammate_prior_e123_20261026')
PEER_ROOT=Path('/home-mscluster/astrauss/RL-ARC-AGI-3-Project')
CKPT=PEER_ROOT/'assets/dqn_v1/checkpoints/E-onehotcnn__T-stack2__A-vector__U-effect__f0__s11.pt'
CKPT_SHA='c5882f664b082aa131023ac1ffaebeb771ba7fe181fa909730fe1c641e5978b9'
sys.path.insert(0,str(E121))
import run_e121 as R
PARENT=R.original.AuditedCrossLevelCore
R.ARMS=tuple(dict.fromkeys(R.ARMS+('baseline','peer_salience','peer_random','peer_trained','peer_gated','peer_trained_salience')))
R.apply_arm=lambda arm:setattr(R.original.PortableAgentCore,'candidates',R.ORIGINAL_CANDIDATES)
ACTIVE='baseline'
LAST=None
GLOB=128
SPAT=96

# Exactly the pretrained model graph in the user's teammate ZIP
# src/dqn_v1/prior.py (the cluster checkout source has drifted, so do not import it).
class OneHotCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv=nn.Sequential(nn.Conv2d(16,32,5,2,2),nn.GELU(),
                                nn.Conv2d(32,64,3,2,1),nn.GELU(),
                                nn.Conv2d(64,SPAT,3,2,1),nn.GELU())
        self.proj=nn.Linear(SPAT,GLOB)
    def encode(self,grid):
        x=F.one_hot(grid.long().clamp(0,15),num_classes=16).float().permute(0,3,1,2).contiguous()
        s=self.conv(x)
        return self.proj(s.mean((2,3))),s
class Stack2Temporal(nn.Module):
    def __init__(self):
        super().__init__()
        self.base=OneHotCNN()
        self.gf=nn.Linear(GLOB*2,GLOB)
        self.sf=nn.Conv2d(SPAT*2,SPAT,1)
    def forward(self,grid,prev_grid,hist_grid,hist_mask):
        g,s=self.base.encode(grid)
        pg,ps=self.base.encode(prev_grid)
        return self.gf(torch.cat([g,pg],-1)),self.sf(torch.cat([s,ps],1))
class GenericActionContext(nn.Module):
    def __init__(self):
        super().__init__()
        self.aid=nn.Embedding(8,16)
        self.x=nn.Embedding(65,16)
        self.y=nn.Embedding(65,16)
        self.mlp=nn.Sequential(nn.Linear(48,64),nn.GELU(),nn.Linear(64,64))
    def forward(self,action):
        aid=action[:,0].long().clamp(0,7)
        is6=aid==6
        xi=torch.where(is6,(action[:,1].clamp(0,1)*63).round().long(),torch.full_like(aid,64))
        yi=torch.where(is6,(action[:,2].clamp(0,1)*63).round().long(),torch.full_like(aid,64))
        return self.mlp(torch.cat([self.aid(aid),self.x(xi),self.y(yi)],-1))
class VectorInterface(nn.Module):
    def __init__(self):
        super().__init__()
        self.ctx=GenericActionContext()
        self.head=nn.Sequential(nn.Linear(GLOB+64,128),nn.GELU(),nn.Linear(128,1))
    def forward(self,g,s,action):
        c=self.ctx(action)
        return self.head(torch.cat([g,c],-1)).squeeze(-1),c
class SelectedEffectModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.temporal=Stack2Temporal()
        self.action=VectorInterface()

@functools.lru_cache(maxsize=2)
def model_for(kind):
    if kind=='trained':
        if hashlib.sha256(CKPT.read_bytes()).hexdigest()!=CKPT_SHA:
            raise RuntimeError('Teammate checkpoint changed versus uploaded source archive')
        ck=torch.load(CKPT,map_location='cpu',weights_only=True)
        assert isinstance(ck,dict) and 'state_dict' in ck
        m=SelectedEffectModel()
        m.load_state_dict(ck['state_dict'],strict=True)
    elif kind=='random':
        state=torch.random.get_rng_state()
        torch.manual_seed(20240)
        m=SelectedEffectModel()
        torch.random.set_rng_state(state)
    else:raise ValueError(kind)
    m.eval()
    for p in m.parameters():p.requires_grad_(False)
    return m

def peer_scores(model,frame,previous,acts):
    acts=np.asarray(acts,dtype=np.int64)
    a_ids=np.where(acts<6,np.asarray([1,2,3,4,5,7],np.int64)[np.minimum(acts,5)],6)
    values=np.full((len(acts),3),-1.,dtype=np.float32)
    values[:,0]=a_ids.astype(np.float32)
    clicks=acts>=6
    values[clicks,1]=((acts[clicks]-6)%64).astype(np.float32)/63.
    values[clicks,2]=((acts[clicks]-6)//64).astype(np.float32)/63.
    current=torch.from_numpy(np.asarray(frame,np.int64)).unsqueeze(0)
    prev=torch.from_numpy(np.asarray(previous,np.int64)).unsqueeze(0)
    hist=torch.zeros((1,4,64,64),dtype=torch.long)
    mask=torch.zeros((1,4),dtype=torch.bool)
    with torch.inference_mode():
        g,s=model.temporal(current,prev,hist,mask)
        actions=torch.from_numpy(values)
        logits,_=model.action(g.expand(len(acts),-1),s.expand(len(acts),-1,-1,-1),actions)
    raw=logits.cpu().numpy().astype(np.float64)
    assert raw.shape==(len(acts),) and np.isfinite(raw).all(),raw
    result=np.zeros(len(acts),dtype=np.float64)
    # Per-type normalization preserves the base distinction between clicks
    # and primitive actions; avoids model-specific raw-logit calibration.
    for inds in (np.flatnonzero(acts<6),np.flatnonzero(acts>=6)):
        if len(inds)<2:continue
        v=raw[inds]
        sd=float(v.std())
        if sd>1e-8:result[inds]=np.clip((v-v.mean())/sd,-2.,2.)
    return dict(zip(map(int,acts),map(float,result)))

def salience_scores(frame,acts):
    # Teammate's D14: rarity + .35 boundary contrast + .5 component rarity.
    f=np.asarray(frame,dtype=np.int64)
    palette,hist=np.unique(f,return_counts=True)
    freq=dict(zip(palette.tolist(),hist.tolist()))
    rarity=np.zeros((64,64),dtype=np.float64)
    components=np.zeros_like(rarity)
    for c in palette:
        active=f==c
        rarity[active]=-math.log((freq[int(c)]+1.)/(4096.+16.))
        labels,num=ndi.label(active)
        counts=np.bincount(labels.ravel(),minlength=num+1)
        # Value at each belonging pixel is the rarity of its connected component.
        components[active]=-np.log((counts[labels[active]]+1.)/4097.)
    contrast=np.zeros_like(rarity)
    contrast[1:,:]+=(f[1:,:]!=f[:-1,:])
    contrast[:-1,:]+=(f[:-1,:]!=f[1:,:])
    contrast[:,1:]+=(f[:,1:]!=f[:,:-1])
    contrast[:,:-1]+=(f[:,:-1]!=f[:,1:])
    sal=rarity+.35*contrast+.5*components
    acts=np.asarray(acts,dtype=np.int64)
    out=np.zeros(len(acts),dtype=np.float64)
    clicks=np.flatnonzero(acts>=6)
    if len(clicks)>=2:
        ca=acts[clicks]
        v=sal[(ca-6)//64,(ca-6)%64]
        sd=float(v.std())
        if sd>1e-8:out[clicks]=np.clip((v-v.mean())/sd,-2.,2.)
    return dict(zip(map(int,acts),map(float,out)))

class PeerCore(PARENT):
    def __init__(self,*args,**kwargs):
        global LAST
        super().__init__(*args,**kwargs)
        self.e123_arm=ACTIVE
        self.e123_active_scores=None
        self.e123_salience=None
        self.e123_actions_scored=0
        self.e123_logits_batches=0
        self.e123_model_used=False
        self.e123_active_count=0
        LAST=self

    def choose(self,f,legal):
        self.e123_active_scores=None
        self.e123_salience=None
        if self.level>=1 and self.e123_arm!='baseline':
            s=self.node(np.asarray(f,np.uint8),np.asarray(legal,bool))
            acts=self.nodes[s]['actions']
            if self.e123_arm in ('peer_random','peer_trained','peer_gated','peer_trained_salience'):
                kind='random' if self.e123_arm=='peer_random' else 'trained'
                m=model_for(kind)
                prior=self.prev if self.prev is not None else f
                self.e123_active_scores=peer_scores(m,f,prior,acts)
                self.e123_logits_batches+=1
                self.e123_model_used=True
            if self.e123_arm in ('peer_salience','peer_trained_salience'):
                self.e123_salience=salience_scores(f,acts)
        return super().choose(f,legal)

    def _memory_bonus(self,frame,a,mode):
        b1,b2,desc,past_n,current_n=super()._memory_bonus(frame,a,mode)
        if self.level<1:return b1,b2,desc,past_n,current_n
        a=int(a)
        if self.e123_active_scores is not None:
            x=self.e123_active_scores.get(a,0.)
            weight=.025
            if self.e123_arm=='peer_gated':
                # Transfer only for candidates without current-level evidence.
                weight*=1. if current_n==0 else 0.
            b2+=weight*x
            self.e123_active_count+=1
        if self.e123_salience is not None and a>=6:
            b2+=.020*self.e123_salience.get(a,0.)
            self.e123_active_count+=1
        return b1,b2,desc,past_n,current_n

    def report_e123(self):
        return {'arm':self.e123_arm,'trained_model_loaded':bool(self.e123_model_used),
                'inference_batches':self.e123_logits_batches,
                'prior_adjusted_candidates':self.e123_active_count}

R.original.AuditedCrossLevelCore=PeerCore
def run_one(game,arm,seed):
    global ACTIVE,LAST
    ACTIVE=arm
    LAST=None
    out=R.run(game,arm,seed_native=47,seed_policy=seed)
    out['summary']['e123']=LAST.report_e123() if LAST is not None else {}
    return out

def main():
    pa=argparse.ArgumentParser()
    arms=('baseline','peer_salience','peer_random','peer_trained','peer_gated','peer_trained_salience')
    pa.add_argument('--arm',required=True,choices=arms)
    pa.add_argument('--games',nargs='*',default=list(R.FAMILIES))
    pa.add_argument('--seed',type=int,default=76)
    pa.add_argument('--out',default=str(BASE/'results'))
    pa.add_argument('--resume',action='store_true')
    args=pa.parse_args()
    assert all(game in R.FAMILIES for game in args.games)
    out=Path(args.out)/('seed'+str(args.seed))/args.arm
    out.mkdir(parents=True,exist_ok=True)
    summaries=[]
    for game in args.games:
        f=out/(game+'.json')
        if args.resume and f.is_file():ob=json.loads(f.read_text())
        else:
            try:ob=run_one(game,args.arm,args.seed)
            except BaseException as e:
                f.write_text(json.dumps({'fatal':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()},indent=2))
                raise
            f.write_text(json.dumps(ob,indent=2)+'\n')
        s=ob['summary'];summaries.append(s)
        print('E123',args.arm,'SEED',args.seed,game,'L',s['levels_completed'],
              'A',s['charged_sdk_actions'],'PRIOR',s['e123'],flush=True)
    print('ARM_TOTAL',args.arm,'SEED',args.seed,'GAMES',len(summaries),
          'L1',sum(s['l1'] for s in summaries),'L2',sum(s['l2'] for s in summaries),
          'L3',sum(s['l3plus'] for s in summaries),
          'ACTIONS',sum(s['charged_sdk_actions'] for s in summaries),flush=True)

if __name__=='__main__':main()
