"""E069: observation/history-conditioned off-policy Double DQN.

Native SDK level advancement is the sole external reward. Training consumes
only source-five native self-play or hash-verified source-five human examples.
No game id, teacher route or source-code information enters the actor.
"""
from __future__ import annotations
import argparse,hashlib,json,math,random
from pathlib import Path
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from e068_split import TRAIN_FAMILIES,TEST_FAMILIES,FORBIDDEN,sha

HISTORY=4
ACTIONS=8
FIELDS=('frame','next_frame','action','xy','reward','terminal','legal','next_legal','family','session_step')


def coarse(frame):
    """Fixed 16x16 subsampling of public 64x64 4-bit palette observations."""
    z=np.asarray(frame,dtype=np.uint8)
    if z.shape[-2:]!=(64,64):raise ValueError('Expected 64x64 ARC public observation')
    if z.max()>15:raise ValueError('Unexpected palette')
    return z[...,2::4,2::4].copy()


def prep_data(path):
    with np.load(path,allow_pickle=False) as z: d={k:z[k] for k in z.files}
    if set(d)!=set(FIELDS):raise ValueError('Invalid native observation/action dataset')
    if set(int(x) for x in np.unique(d['family']))!=set(range(5)):
        raise PermissionError('All and only the five source-fitting families required')
    n=len(d['action'])
    if not n or any(len(v)!=n for v in d.values()):raise ValueError('Dataset arrays do not align')
    if d['frame'].shape!=(n,64,64) or d['next_frame'].shape!=(n,64,64):
        raise ValueError('Invalid frame geometry')
    if (d['reward']<0).any():raise ValueError('Negative native reward')
    if np.any(d['legal'][np.arange(n),d['action']]!=True):
        raise ValueError('Illegal dataset action')
    if np.any(d['action']==0):raise ValueError('RESET is not a trained policy action')
    if np.any(np.diff(d['session_step'])==0):raise ValueError('Repeated timestamps')
    return d


def sequence_arrays(d,h=HISTORY):
    n=len(d['action']);z=coarse(d['frame']);post=coarse(d['next_frame'])
    hs=np.zeros((n,h,16,16),dtype=np.uint8);hn=np.zeros_like(hs)
    ha=np.zeros((n,h),dtype=np.int64);hna=np.zeros_like(ha)
    hp=np.zeros((n,h,2),dtype=np.float32);hnp=np.zeros_like(hp)
    for i in range(n):
        seg=[i];j=i
        while len(seg)<h and j>0:
            k=j-1
            if (d['family'][k]!=d['family'][j] or
                d['session_step'][j]!=d['session_step'][k]+1 or
                bool(d['terminal'][k])):break
            seg.insert(0,k);j=k
        m=len(seg)
        hs[i,-m:]=z[seg]
        hn[i,-m:]=np.concatenate((z[seg[1:]],post[i:i+1]),axis=0)
        # Previous input actions, NEVER the current chosen action at s_t.
        # Invalid/unknown history token 0 on the first state of a segment.
        if m>1:
            ha[i,-(m-1):]=np.asarray(d['action'][seg[:-1]],dtype=np.int64)
            hp[i,-(m-1):]=np.where(np.asarray(d['xy'][seg[:-1]])>=0,
                    np.asarray(d['xy'][seg[:-1]])/63.,0.)
        # Next observation is one step later; align each previous action
        # to the state it produced rather than reusing current-state slots.
        hna[i,:-1]=ha[i,1:]
        hnp[i,:-1]=hp[i,1:]
        hna[i,-1]=int(d['action'][i])
        hnp[i,-1]=np.where(d['xy'][i]>=0,d['xy'][i]/63.,0.)
    # Distinguish zero padding from actual all-zero ARC frame by explicit masks.
    return {'s':hs,'s_next':hn,'a_prev':ha,'a_nextprev':hna,
            'xy_prev':hp,'xy_nextprev':hnp}


class HistoryQ(nn.Module):
    def __init__(self,h=HISTORY,use_history=True):
        super().__init__();self.h=h;self.use_history=use_history
        self.encoder=nn.Sequential(nn.Conv2d(16,24,3,2,1),nn.SiLU(),
            nn.Conv2d(24,32,3,2,1),nn.SiLU(),nn.Flatten(),nn.Linear(32*4*4,64),nn.SiLU())
        self.gru=nn.GRU(64+8+2,64,batch_first=True)
        self.policy=nn.Sequential(nn.Linear(64,64),nn.SiLU(),nn.Linear(64,ACTIONS))
        self.click=nn.Sequential(nn.Linear(64,128),nn.SiLU(),nn.Linear(128,256))
    def forward(self,frame,a_prev,xy_prev):
        b,t,h,w=frame.shape
        pal=F.one_hot(frame.long().clamp(0,15),16).permute(0,1,4,2,3).float().reshape(b*t,16,h,w)
        embed=self.encoder(pal).reshape(b,t,64)
        if not self.use_history:
            embed=embed[:,-1:];a_prev=a_prev[:,-1:]*0;xy_prev=xy_prev[:,-1:]*0
        a=F.one_hot(a_prev.long().clamp(0,ACTIONS-1),ACTIONS).float()
        z=torch.cat((embed,a,xy_prev),dim=-1)
        output,_=self.gru(z)
        state=output[:,-1]
        return self.policy(state),self.click(state)


def reward_shuffled(d,seed):
    rng=np.random.default_rng(seed);r=np.asarray(d['reward'],dtype=np.float32).copy()
    # Shuffle labels independently within each family. This is the ONLY label used
    # by this control, including replay priorities; no ground-truth stratification.
    for f in np.unique(d['family']):
        ids=np.flatnonzero(d['family']==f)
        r[ids]=rng.permutation(r[ids])
    assert r.sum()==d['reward'].sum()
    return r


def train(path,out,mode,seed=2069,updates=400,batch=64,lr=.0003,
          gamma=.98,history=HISTORY,device='cpu',verified_manifest=None):
    if mode not in ('bc','ddqn','shuffled','no_history'):raise ValueError(mode)
    torch.set_num_threads(2);torch.manual_seed(seed);np.random.seed(seed)
    rng=np.random.default_rng(seed)
    from source_audit import audit_source
    provenance=audit_source(path,verified_manifest)
    d=prep_data(Path(path))
    seq=sequence_arrays(d,history);r=(reward_shuffled(d,seed) if mode=='shuffled'
                                     else np.asarray(d['reward'],dtype=np.float32))
    n=len(r);a=d['action'].astype(np.int64);legal=d['legal'].astype(bool)
    nl=d['next_legal'].astype(bool)
    term=d['terminal'].astype(bool)
    model=HistoryQ(history,use_history=(mode!='no_history')).to(device)
    target=HistoryQ(history,use_history=(mode!='no_history')).to(device)
    target.load_state_dict(model.state_dict());target.eval()
    opt=torch.optim.AdamW(model.parameters(),lr=lr)
    buf={k:torch.from_numpy(v).to(device) for k,v in seq.items()}
    # Episodes with no next legal actions should not bootstrap.
    loss_trace=[];td_updates=0
    for step in range(updates):
        ids=rng.integers(0,n,size=batch)
        def get(name):return buf[name][ids]
        valid=torch.from_numpy(legal[ids]).to(device)
        selected=torch.from_numpy(a[ids]).long().to(device)
        q,pt=model(get('s'),get('a_prev'),get('xy_prev'))
        restricted=q.masked_fill(~valid,-1e5)
        loss_bc=F.cross_entropy(restricted,selected)
        where=np.flatnonzero((a[ids]==6)&(d['xy'][ids,0]>=0)&(d['xy'][ids,1]>=0))
        if len(where):
            pos=d['xy'][ids[where]].astype(int)
            labels=torch.from_numpy((pos[:,1]//4*16+pos[:,0]//4).clip(0,255)).long().to(device)
            loss_xy=F.cross_entropy(pt[where],labels)
        else:loss_xy=q.sum()*0
        if mode=='bc':
            loss=loss_bc+.25*loss_xy;td_loss=q.sum()*0;cql=q.sum()*0
        else:
            with torch.no_grad():
                oq,_=model(get('s_next'),get('a_nextprev'),get('xy_nextprev'))
                nq,_=target(get('s_next'),get('a_nextprev'),get('xy_nextprev'))
                nvalid=torch.from_numpy(nl[ids]).to(device)
                can=nvalid.any(dim=1)
                best=oq.masked_fill(~nvalid,-1e5).argmax(dim=1)
                rvec=torch.from_numpy(r[ids]).to(device)
                boot=nq.gather(1,best[:,None]).squeeze(1)
                alive=torch.from_numpy(~term[ids]).to(device)&can
                y=rvec+gamma*boot*alive.float()
            selected_q=q.gather(1,selected[:,None]).squeeze(1)
            w=1.+4.*torch.from_numpy(r[ids]).to(device)
            td_loss=(F.smooth_l1_loss(selected_q,y,reduction='none')*w).mean()
            cql=(torch.logsumexp(restricted,dim=1)-selected_q).mean()
            loss=td_loss+.15*cql+.20*loss_bc+.05*loss_xy
            td_updates+=1
        opt.zero_grad();loss.backward();nn.utils.clip_grad_norm_(model.parameters(),1.);opt.step()
        if step%60==0:target.load_state_dict(model.state_dict())
        if (step+1)%100==0 or step==0:
            loss_trace.append({'update':step+1,'loss':round(float(loss.detach()),5),
              'td':round(float(td_loss.detach()),5),'bc':round(float(loss_bc.detach()),5),
              'cql':round(float(cql.detach()),5)})
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    dst=out/f'history_{mode}.pt'
    payload={'model':model.state_dict(),'mode':mode,'seed':seed,'updates':updates,
             'train_families':TRAIN_FAMILIES,'dataset_hash':sha(path),
             'source_type':provenance['kind'],
             'rewards':int(d['reward'].sum()),'training_objective':'BC+DDQN+CQL' if mode!='bc' else 'BC',
             'history':history,'model_name':'HistoryQ','reward_control':mode=='shuffled'}
    torch.save(payload,dst)
    audit={'mode':mode,'checkpoint':str(dst),'sha256':sha(dst),'training_rows':int(n),
           'true_native_level_events':int(d['reward'].sum()),'train_families':list(TRAIN_FAMILIES),
           'fit_excluded_families':list(TEST_FAMILIES),'untouched_dev_protected':list(FORBIDDEN),
           'losses':loss_trace,'genuine_td_updates':int(td_updates),'source_provenance':provenance,
           'real_rewards_used_in_target':mode in ('ddqn','no_history'),
           'reward_control':mode=='shuffled','dataset_sha256':sha(path)}
    (out/f'history_{mode}_training.json').write_text(json.dumps(audit,indent=2)+'\n')
    return audit


def load(path):
    v=torch.load(path,map_location='cpu',weights_only=True)
    if tuple(v['train_families'])!=TRAIN_FAMILIES:raise PermissionError('Checkpoint training split changed')
    m=HistoryQ(v['history'],use_history=v['mode']!='no_history')
    m.load_state_dict(v['model']);m.eval();return m,v

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--mode',default='all',choices=['all','bc','ddqn','shuffled','no_history'])
    p.add_argument('--updates',type=int,default=400)
    p.add_argument('--verified-manifest',type=Path);args=p.parse_args()
    for mode in (('bc','ddqn','shuffled','no_history') if args.mode=='all' else (args.mode,)):
        print(json.dumps(train(args.source,args.out,mode,updates=args.updates,verified_manifest=args.verified_manifest),indent=2),flush=True)
