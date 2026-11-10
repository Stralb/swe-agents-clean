"""Self-contained E126 extension, inserted after the unchanged frozen N117 module."""
E126_EXTENSION = r'''
import torch.nn.functional as _F126
_N117_AGENT = MyAgent
_N117_CORE = AuditedCrossLevelCore
_PEER_SHA_126 = "c5882f664b082aa131023ac1ffaebeb771ba7fe181fa909730fe1c641e5978b9"
_PEER_B85_126 = (
__E126_B85__
)

class _CNN126(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv=nn.Sequential(nn.Conv2d(16,32,5,2,2),nn.GELU(),
                                nn.Conv2d(32,64,3,2,1),nn.GELU(),
                                nn.Conv2d(64,96,3,2,1),nn.GELU())
        self.proj=nn.Linear(96,128)
    def encode(self,grid):
        x=_F126.one_hot(grid.long().clamp(0,15),num_classes=16).float().permute(0,3,1,2).contiguous()
        s=self.conv(x)
        return self.proj(s.mean((2,3))),s

class _Temporal126(nn.Module):
    def __init__(self):
        super().__init__()
        self.base=_CNN126()
        self.gf=nn.Linear(256,128)
        self.sf=nn.Conv2d(192,96,1)
    def forward(self,grid,prev_grid,hist_grid,hist_mask):
        g,s=self.base.encode(grid)
        pg,ps=self.base.encode(prev_grid)
        return self.gf(torch.cat([g,pg],-1)),self.sf(torch.cat([s,ps],1))

class _ActionContext126(nn.Module):
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

class _Vector126(nn.Module):
    def __init__(self):
        super().__init__()
        self.ctx=_ActionContext126()
        self.head=nn.Sequential(nn.Linear(192,128),nn.GELU(),nn.Linear(128,1))
    def forward(self,g,s,action):
        c=self.ctx(action)
        return self.head(torch.cat([g,c],-1)).squeeze(-1),c

class _Effect126(nn.Module):
    def __init__(self):
        super().__init__()
        self.temporal=_Temporal126()
        self.action=_Vector126()

@lru_cache(maxsize=1)
def _effect_model_126():
    blob=zlib.decompress(base64.b85decode(_PEER_B85_126))
    if hashlib.sha256(blob).hexdigest()!=_PEER_SHA_126:
        raise RuntimeError("E126 peer checkpoint hash mismatch")
    ck=torch.load(io.BytesIO(blob),map_location='cpu',weights_only=True)
    if not isinstance(ck,dict) or 'state_dict' not in ck:
        raise RuntimeError("E126 peer checkpoint schema invalid")
    m=_Effect126()
    m.load_state_dict(ck['state_dict'],strict=True)
    m.eval()
    for p in m.parameters():p.requires_grad_(False)
    return m

def _effect_scores_126(model,frame,previous,acts):
    acts=np.asarray(acts,dtype=np.int64)
    aid=np.where(acts<6,np.asarray([1,2,3,4,5,7],np.int64)[np.minimum(acts,5)],6)
    vec=np.full((len(acts),3),-1.,dtype=np.float32)
    vec[:,0]=aid.astype(np.float32)
    click=acts>=6
    vec[click,1]=((acts[click]-6)%64).astype(np.float32)/63.
    vec[click,2]=((acts[click]-6)//64).astype(np.float32)/63.
    now=torch.from_numpy(np.asarray(frame,np.int64)).unsqueeze(0)
    prev=torch.from_numpy(np.asarray(previous,np.int64)).unsqueeze(0)
    hist=torch.zeros((1,4,64,64),dtype=torch.long)
    mask=torch.zeros((1,4),dtype=torch.bool)
    with torch.inference_mode():
        g,s=model.temporal(now,prev,hist,mask)
        v=torch.from_numpy(vec)
        logits,_=model.action(g.expand(len(acts),-1),s.expand(len(acts),-1,-1,-1),v)
    raw=logits.cpu().numpy().astype(np.float64)
    if raw.shape!=(len(acts),) or not np.isfinite(raw).all():
        raise RuntimeError("E126 nonfinite effect logits")
    out=np.zeros(len(acts),dtype=np.float64)
    for ii in (np.flatnonzero(acts<6),np.flatnonzero(acts>=6)):
        if len(ii)<2:continue
        val=raw[ii];sd=float(val.std())
        if sd>1e-8:out[ii]=np.clip((val-val.mean())/sd,-2.,2.)
    return dict(zip(map(int,acts),map(float,out)))

class E126Core(_N117_CORE):
    """E124 click-contingency outside E125 sparse click-only scenes."""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.contingency_obs=defaultdict(lambda:[0,0])
        self.peer_rank_calls=0
        self.local_rank_calls=0
        self.peer_actions_scored=0
        self.click_observations=0
    def start_level(self,completed,frame):
        if hasattr(self,'contingency_obs') and getattr(self,'level',-1)!=int(completed):
            self.contingency_obs.clear()
        return super().start_level(completed,frame)
    def _local_bonus(self,f,a):
        if a<6:return 0.
        x=int((a-6)%64);y=int((a-6)//64)
        col=int(f[y,x])
        frac=float(np.count_nonzero(f==col))/4096.
        rare=.045*(1.-np.sqrt(frac))
        yes,no=self.contingency_obs.get(col,(0,0))
        n=yes+no
        return float(rare+.090*((yes+1.)/(n+2.)-.5)*min(1.,n/4.))
    def _rank_e126(self,s,best_idx,peer):
        nd=self.nodes[s]
        acts=np.asarray(nd['actions'],dtype=np.int64)
        valid=acts[best_idx]
        if len(valid)==1:return int(valid[0])
        if self.prior_enabled:
            if 'prior' not in nd or len(nd['prior'])!=len(acts):
                with torch.inference_mode():
                    x=action_features(nd['f'],self.prev,nd['legal'],acts,self.last)
                    logits,_=self.model(torch.from_numpy(x))
                    nd['prior']=logits.numpy()
            priors=nd['prior'][best_idx]
            order=np.argsort(-priors,kind='stable')
            subset=list(map(int,valid[order[:min(28,len(valid))]]))
            more=self.rng.choice(valid,size=min(24,len(valid)),replace=False)
            subset+=list(map(int,more))
            subset=list(dict.fromkeys(subset))
            finite=priors[np.isfinite(priors)]
            mid=float(np.median(finite)) if len(finite) else 0.
            spread=max(.02,float(np.std(finite))) if len(finite) else 1.
            lookup={int(a):float(x) for a,x in zip(valid,priors)}
        else:
            subset=list(map(int,valid[:min(32,len(valid))]))
            if len(valid)>32:
                subset+=list(map(int,self.rng.choice(valid,size=min(24,len(valid)),replace=False)))
            subset=list(dict.fromkeys(subset))
            mid,spread,lookup=0.,1.,{}
        if peer:
            previous=self.prev if self.prev is not None else nd['f']
            extra=_effect_scores_126(_effect_model_126(),nd['f'],previous,acts)
            self.peer_rank_calls+=1
            self.peer_actions_scored+=len(subset)
        else:
            extra=None
            self.local_rank_calls+=1
        scores=[]
        for a in subset:
            b=self.beliefs.rank(nd['f'],int(a))
            ps=float(np.clip((lookup.get(a,mid)-mid)/spread,-3.,3.))
            bonus=.13*extra.get(int(a),0.) if peer else self._local_bonus(nd['f'],int(a))
            scores.append((.55*ps+.90*b+float(self.rng.uniform(0,.02))+bonus,int(a)))
        return max(scores)[1]
    def _rank_ties(self,s,best_idx):
        if self.level>=1:return super()._rank_ties(s,best_idx)
        nd=self.nodes[s];legal=np.asarray(nd['legal'],bool)
        if legal[5] and not np.any(legal[:5]):
            f=np.asarray(nd['f'],np.uint8)
            modal=float(np.bincount(f.ravel(),minlength=16).max())/4096.
            if modal>=.80:return self._rank_e126(s,best_idx,True)
        return self._rank_e126(s,best_idx,False)
    def observe(self,f,legal,completed,terminal=False):
        pending=self.pending
        if pending is not None:
            _,a,oldlevel,before=pending
            if int(completed)==int(oldlevel) and not terminal:
                after=np.asarray(f,np.uint8);orig=np.asarray(before,np.uint8)
                if int(a)>=6:
                    self.click_observations+=1
                    x=(int(a)-6)%64;y=(int(a)-6)//64
                    col=int(orig[y,x])
                    y0=max(0,y-4);y1=min(64,y+5)
                    x0=max(0,x-4);x1=min(64,x+5)
                    diff=orig!=after
                    local=int(diff[y0:y1,x0:x1].sum())
                    total=int(diff.sum())
                    area=(y1-y0)*(x1-x0)
                    rate=local/max(1,area)
                    rest=(total-local)/max(1,4096-area)
                    meaningful=local>=2 and rate>rest+.018
                    self.contingency_obs[col][0 if meaningful else 1]+=1
        return super().observe(f,legal,completed,terminal=terminal)
    def diagnostics(self):
        return {'peer_rank_calls':self.peer_rank_calls,
                'local_rank_calls':self.local_rank_calls,
                'peer_actions_scored':self.peer_actions_scored,
                'click_observations':self.click_observations,
                'native_updates':self.num_updates}

class MyAgent(_N117_AGENT):
    """Drop-in Kaggle interface, no game-ID based decisions."""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.core=E126Core(checkpoint=None,seed=76,learning=True,
            prior_enabled=True,puct=True,uniform=False,c=.1,
            temperature=2.,mode='local')
'''
