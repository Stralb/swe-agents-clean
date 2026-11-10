#!/usr/bin/env python3
"""E124 – Grounded click-structure interventions on exact frozen N117.
No game identifiers are accessible to policies, no hidden state is read by
agents, and no proxy reward enters Q-learning updates. SDK scores are evaluated
using public native games; no Kaggle actions.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,sys,traceback,math
from pathlib import Path
import numpy as np,torch
from scipy import ndimage as ndi
BASE=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_breakthrough_e124_20261026')
E121=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026')
E123=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/teammate_prior_e123_20261026')
sys.path.insert(0,str(E121))
import run_e121 as R
MODEL=R.original
PARENT=MODEL.AuditedCrossLevelCore
ORIG_CANDS=R.ORIGINAL_CANDIDATES
ARMS=('baseline','prune_bg','prune_broad','edge_contact','contingency','selection_chain')
R.ARMS=tuple(dict.fromkeys(R.ARMS+ARMS))
ACTIVE='baseline'
LAST=None

def same_component_mask(frame,x,y):
    f=np.asarray(frame,np.uint8)
    labels,_=ndi.label(f==f[y,x])
    v=int(labels[y,x])
    return labels==v

def bg_candidate_list(self,f,legal,arm):
    base=list(ORIG_CANDS(self,f,legal))
    if not legal[5] or not any(a>=6 for a in base):return base
    img=np.asarray(f,np.uint8)
    available=img[~self.mask]
    if not len(available):return base
    freq=np.bincount(available,minlength=16)
    b=int(np.argmax(freq))
    dominant=float(freq[b]/len(available))
    min_prop=.62 if arm=='prune_bg' else .43
    if dominant<min_prop:return base
    # Only suppress high-area likely background components, never all pixels
    # of a color (small disconnected objects of the same colour may be valid).
    labels,ns=ndi.label((img==b)&(~self.mask))
    if ns==0:return base
    sizes=np.bincount(labels.ravel())
    threshold=1024 if arm=='prune_bg' else 400
    removed=0
    ans=[]
    for action in base:
        if action>=6:
            x=(action-6)%64;y=(action-6)//64
            label=int(labels[y,x])
            if label and sizes[label]>=threshold:
                removed+=1
                continue
        ans.append(action)
    if not ans:return base
    if len(ans)<2 and len(base)>2:return base
    return ans

def edge_candidate_list(self,frame,legal):
    base=list(ORIG_CANDS(self,frame,legal))
    if not legal[5]:return base
    f=np.asarray(frame,np.uint8)
    result=[]
    for a in base:
        if a<6:result.append(a);continue
        x=int((a-6)%64);y=int((a-6)//64)
        comp=same_component_mask(f,x,y)
        yy,xx=np.where(comp)
        # Change the representative click, not the number of candidates.
        if not 5<=len(xx)<=180:
            result.append(a);continue
        y0,y1=max(0,y-1),min(64,y+2)
        x0,x1=max(0,x-1),min(64,x+2)
        # Boundary pixels with foreign neighbours can be controls,
        # especially for grids or adjacent components. Avoid the 1px border.
        good=(xx>1)&(xx<62)&(yy>1)&(yy<62)
        xx=xx[good];yy=yy[good]
        if len(xx)<2:
            result.append(a);continue
        edge_score=(f[yy-1,xx]!=f[yy,xx]).astype(float)
        edge_score+=(f[yy+1,xx]!=f[yy,xx])
        edge_score+=(f[yy,xx-1]!=f[yy,xx])
        edge_score+=(f[yy,xx+1]!=f[yy,xx])
        if edge_score.max()<=0:
            result.append(a);continue
        # Boundary contact nearest original centroid to avoid arbitrary
        # extreme corners.
        distance=(xx-x)**2+(yy-y)**2
        utility=4*edge_score-.006*distance
        ind=int(np.argmax(utility))
        result.append(6+64*int(yy[ind])+int(xx[ind]))
    return list(dict.fromkeys(result))

def extra_score(self,f,a):
    if a<6:return 0.
    arr=np.asarray(f,np.uint8)
    x=int((a-6)%64);y=int((a-6)//64)
    cur=int(arr[y,x])
    total=np.bincount(arr.ravel(),minlength=16)
    fraction=float(total[cur]/4096)
    # A principled, bounded selection likelihood; uncommon objects offer
    # information without assuming they are goals.
    rareness=1.-math.sqrt(max(0.,fraction))
    # The interaction must remain causally distinguishable from static
    # pixel-level animation (already filtered in N117 HypothesisMemory).
    evidence=self.contingency_obs.get(cur,(0,0))
    yes,no=evidence
    p=(yes+1.)/(yes+no+2.)
    confidence=min(1.,(yes+no)/4.)
    return 0.045*rareness+0.090*(p-.5)*confidence

class E124Core(PARENT):
    def __init__(self,*args,**kwargs):
        global LAST
        super().__init__(*args,**kwargs)
        self.e124_arm=ACTIVE
        self.contingency_obs=collections.defaultdict(lambda:[0,0])
        self.selection_next=False
        self.override_rank_calls=0
        self.filtered_states=0
        self.edge_states=0
        self.selection_events=0
        self.click_observations=0
        LAST=self
    def start_level(self,completed,frame):
        if hasattr(self,'contingency_obs') and getattr(self,'level',-1)!=int(completed):
            self.contingency_obs.clear()
            self.selection_next=False
        return super().start_level(completed,frame)
    def candidates(self,f,legal):
        if self.e124_arm in ('prune_bg','prune_broad'):
            ans=bg_candidate_list(self,f,legal,self.e124_arm)
            if len(ans)<len(ORIG_CANDS(self,f,legal)):self.filtered_states+=1
            return ans
        if self.e124_arm=='edge_contact':
            result=edge_candidate_list(self,f,legal)
            if result!=ORIG_CANDS(self,f,legal):self.edge_states+=1
            return result
        return ORIG_CANDS(self,f,legal)
    def _rank_ties(self,s,best_idx):
        if self.e124_arm not in ('contingency','selection_chain') or self.level>=1:
            return super()._rank_ties(s,best_idx)
        nd=self.nodes[s];acts=np.asarray(nd['actions'],int)
        valid=acts[best_idx]
        if len(valid)==1:return int(valid[0])
        if self.prior_enabled:
            if 'prior' not in nd or len(nd['prior'])!=len(acts):
                with torch.inference_mode():
                    x=MODEL.action_features(nd['f'],self.prev,nd['legal'],acts,self.last)
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
            lookup={int(a):float(v) for a,v in zip(valid,priors)}
        else:
            subset=list(map(int,valid[:min(32,len(valid))]))
            if len(valid)>32:
                subset+=list(map(int,self.rng.choice(valid,size=min(24,len(valid)),replace=False)))
            subset=list(dict.fromkeys(subset))
            mid,spread,lookup=0.,1.,{}
        scores=[]
        for a in subset:
            b=self.beliefs.rank(nd['f'],int(a))
            ps=float(np.clip((lookup.get(a,mid)-mid)/spread,-3.,3.))
            bonus=0.
            if self.e124_arm=='contingency':
                bonus=extra_score(self,nd['f'],a)
            elif self.e124_arm=='selection_chain' and self.selection_next and a<4:
                bonus=.18
            scores.append((.55*ps+.90*b+float(self.rng.uniform(0,.02))+bonus,int(a)))
        self.override_rank_calls+=1
        return max(scores)[1]
    def observe(self,f,legal,completed,terminal=False):
        pend=self.pending
        if pend is not None:
            _,a,oldlevel,before=pend
            if int(completed)==int(oldlevel) and not terminal:
                after=np.asarray(f,np.uint8)
                original=np.asarray(before,np.uint8)
                if int(a)>=6:
                    self.click_observations+=1
                    x=(int(a)-6)%64;y=(int(a)-6)//64
                    col=int(original[y,x])
                    y0=max(0,y-4);y1=min(64,y+5)
                    x0=max(0,x-4);x1=min(64,x+5)
                    delta=original!=after
                    local=int(delta[y0:y1,x0:x1].sum())
                    total=int(delta.sum())
                    local_area=(y1-y0)*(x1-x0)
                    local_rate=local/max(1,local_area)
                    rest_rate=(total-local)/max(1,4096-local_area)
                    meaningful=(local>=2 and local_rate>rest_rate+.018)
                    # Only observed local click contingency is evidence.
                    self.contingency_obs[col][0 if meaningful else 1]+=1
                    self.selection_next=bool(
                        meaningful and self.e124_arm=='selection_chain' and
                        any(bool(legal[j]) for j in (0,1,2,3)))
                    self.selection_events+=int(self.selection_next)
                else:
                    self.selection_next=False
            else:self.selection_next=False
        return super().observe(f,legal,completed,terminal=terminal)
    def report_e124(self):
        return {'arm':self.e124_arm,'rank_calls':self.override_rank_calls,
            'filtered_states':self.filtered_states,'edge_states':self.edge_states,
            'selection_events':self.selection_events,'click_observations':self.click_observations}

MODEL.AuditedCrossLevelCore=E124Core
def apply_arm(arm):
    MODEL.PortableAgentCore.candidates=ORIG_CANDS
R.apply_arm=apply_arm

def execute(game,arm,seed):
    global ACTIVE,LAST
    ACTIVE=arm;LAST=None
    result=R.run(game,arm,seed_policy=seed,seed_native=47)
    result['summary']['E124']=LAST.report_e124() if LAST else {}
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--arm',required=True,choices=ARMS)
    ap.add_argument('--seed',type=int,default=76)
    ap.add_argument('--games',nargs='*',default=list(R.FAMILIES))
    ap.add_argument('--out',default=str(BASE/'results'))
    ap.add_argument('--resume',action='store_true')
    arg=ap.parse_args()
    assert all(g in R.FAMILIES for g in arg.games)
    path=Path(arg.out)/('seed'+str(arg.seed))/arg.arm
    path.mkdir(parents=True,exist_ok=True)
    outcomes=[]
    for game in arg.games:
        f=path/(game+'.json')
        if arg.resume and f.is_file():ob=json.loads(f.read_text())
        else:
            try:ob=execute(game,arg.arm,arg.seed)
            except BaseException as e:
                f.write_text(json.dumps({'fatal':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()},indent=2))
                raise
            f.write_text(json.dumps(ob,indent=2)+'\n')
        s=ob['summary']
        outcomes.append(s)
        print('E124',arg.arm,'SEED',arg.seed,game,'LEVELS',s['levels_completed'],
          'ACTIONS',s['charged_sdk_actions'],'DIAG',s['E124'],flush=True)
    print('ARM_TOTAL',arg.arm,'SEED',arg.seed,'GAMES',len(outcomes),'L1',sum(x['l1'] for x in outcomes),
          'L2',sum(x['l2'] for x in outcomes),'L3PLUS',sum(x['l3plus'] for x in outcomes),
          'ACTIONS',sum(x['charged_sdk_actions'] for x in outcomes),flush=True)
if __name__=='__main__':main()
