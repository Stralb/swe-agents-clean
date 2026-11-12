#!/usr/bin/env python3
"""E122: observed-feedback click rescue and local causal click credit.
All acting data: latest public frame, legal actions, native level progression.
No game identity or game source accesses inside the agent.
"""
from __future__ import annotations
import argparse, collections, hashlib, json, os, sys, time, traceback
from pathlib import Path
import numpy as np
from scipy import ndimage as ndi
E121=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026')
BASE=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_feedback_e122_20261026')
sys.path.insert(0,str(E121))
import run_e121 as R
ACTOR=R.original
PARENT=ACTOR.AuditedCrossLevelCore
ORIGINAL_CANDIDATES=R.ORIGINAL_CANDIDATES
ACTIVE='baseline'
LAST=None
ARMS=('baseline','feedback_rescue_all','feedback_rescue_l2','local_credit_l2','rescue_credit_l2')
R.ARMS=tuple(dict.fromkeys(R.ARMS+ARMS))
def apply_arm(arm):
    ACTOR.PortableAgentCore.candidates=ORIGINAL_CANDIDATES
R.apply_arm=apply_arm

def clipped_rect(x,y,r=4):
    return max(0,y-r),min(64,y+r+1),max(0,x-r),min(64,x+r+1)

def click_class(frame,a):
    if a<6:return None
    x=(a-6)%64;y=(a-6)//64
    c=int(frame[y,x])
    y0,y1,x0,x1=clipped_rect(x,y,1)
    patch=frame[y0:y1,x0:x1]
    ne=int(np.count_nonzero(patch!=c))
    return (c,min(3,ne//2))

def meaningful_local_click(before,after,a):
    x=(a-6)%64;y=(a-6)//64
    y0,y1,x0,x1=clipped_rect(x,y,4)
    delta=(before!=after)
    total=int(delta.sum())
    local=int(delta[y0:y1,x0:x1].sum())
    local_cells=(y1-y0)*(x1-x0)
    outside=max(1,4096-local_cells)
    outside_rate=(total-local)/outside
    local_rate=local/max(1,local_cells)
    # Conservative evidence: local pixel change exceeding background motion.
    positive=(local>=2 and local_rate>outside_rate+0.018)
    # Exact no-op, or a local no-op with very little global movement.
    negative=(total==0 or (local==0 and total<=4))
    return positive,negative,local,total

class FeedbackCore(PARENT):
    def __init__(self,*args,**kwargs):
        global LAST
        super().__init__(*args,**kwargs)
        self.e122_arm=ACTIVE
        self.e122_bad=collections.defaultdict(set)
        self.e122_attempts=collections.Counter()
        self.e122_feedback=collections.defaultdict(lambda:[0,0])
        self.e122_added=0
        self.e122_rescued_actions=0
        self.e122_evidence=collections.Counter()
        self.e122_cache=collections.OrderedDict()
        LAST=self

    def start_level(self,completed,frame):
        # Keep evidence only within level; no cross-level leakage or memorized coordinates.
        if getattr(self,'level',-1)!=int(completed):
            self.e122_bad.clear()
            self.e122_attempts.clear()
            self.e122_feedback.clear()
            self.e122_cache.clear()
        return super().start_level(completed,frame)

    def _rescue_enabled(self):
        return (self.e122_arm in ('feedback_rescue_all','feedback_rescue_l2','rescue_credit_l2')
                and (self.e122_arm=='feedback_rescue_all' or self.level>=1))

    def _credit_enabled(self):
        return self.level>=1 and self.e122_arm in ('local_credit_l2','rescue_credit_l2')

    def node(self,f,legal):
        s=super().node(f,legal)
        if not self._rescue_enabled() or not bool(legal[5]) or s not in self.e122_bad:return s
        nd=self.nodes[s]
        if len(nd['actions'])>768:return s
        # A click may target one object whose centre is noninteractive. Only
        # after an observed no-effect outcome in this same visible state do
        # we propose two alternative same-colour connected-component points.
        for fail_action in sorted(self.e122_bad[s]):
            x=(fail_action-6)%64;y=(fail_action-6)//64
            mask=(f==f[y,x]) & (~self.mask)
            labels,_=ndi.label(mask)
            lab=int(labels[y,x])
            if lab==0:continue
            yy,xx=np.where(labels==lab)
            if not 3<=len(xx)<=1024:continue
            d2=(xx-x)**2+(yy-y)**2
            # Farthest point and half-distance point test whether within-object
            # placement (not colour alone) is the missing cause.
            order=np.argsort(-d2,kind='stable')
            far=int(order[0]);center=min(len(order)-1,max(1,len(order)//3))
            picks=(far,int(order[center]))
            for idx in picks:
                a=6+64*int(yy[idx])+int(xx[idx])
                if a in nd['q'] or a in self.e122_bad[s]:continue
                nd['actions'].append(a)
                nd['q'][a]=1.
                self.e122_added+=1
                if self.e122_added>=3000:raise RuntimeError('rescue candidates unbounded')
        return s

    def observe(self,f,legal,completed,terminal=False):
        # Record only the observed before/after pair and native reward. Passive
        # animation is not a reward; visual evidence never changes Q targets.
        if self.pending is not None:
            state,a,before_level,old=self.pending
            if a>=6 and int(completed)==int(before_level):
                yes,no,local,total=meaningful_local_click(old,np.asarray(f,np.uint8),int(a))
                self.e122_evidence['click_observed']+=1
                self.e122_evidence['local_positive']+=int(yes)
                self.e122_evidence['local_negative']+=int(no)
                key=click_class(old,int(a))
                if key is not None and (yes or no):
                    self.e122_feedback[key][0 if yes else 1]+=1
                if no:
                    self.e122_bad[state].add(int(a))
                if int(a) in self.e122_bad[state] and yes:
                    self.e122_bad[state].discard(int(a))
        return super().observe(f,legal,completed,terminal=terminal)

    def _memory_bonus(self,frame,a,mode):
        b1,b2,desc,past_n,current_n=super()._memory_bonus(frame,a,mode)
        if a<6:return b1,b2,desc,past_n,current_n
        if self._credit_enabled():
            yes,no=self.e122_feedback[click_class(frame,a)]
            n=yes+no
            if n:
                p=(yes+1)/(n+2)
                # Bayesian evidence shrunk toward neutrality; no native reward
                # is assigned for action effects.
                b2+=0.055*(p-.5)*min(1.,n/3.)
                self.e122_evidence['credit_scored']+=1
        if self._rescue_enabled():
            s=self.key(frame,self.nodes[self.key(frame,np.asarray(self.nodes[next(iter(self.nodes))]['legal'],bool))]['legal']) if False else None
            # Per-position no-effect is already represented by PUCT visits,
            # so we don't impose an additional penalty here.
        return b1,b2,desc,past_n,current_n

    def report_e122(self):
        return {'arm':self.e122_arm,'rescue_candidates_generated':int(self.e122_added),
                'evidence_counts':dict(self.e122_evidence),
                'observed_feedback_classes':len(self.e122_feedback),
                'bad_click_state_keys':len(self.e122_bad)}

ACTOR.AuditedCrossLevelCore=FeedbackCore

def execute(family,arm,seed=76):
    global ACTIVE,LAST
    ACTIVE=arm; LAST=None
    obj=R.run(family,arm,seed_native=47,seed_policy=seed)
    obj['summary']['e122']=LAST.report_e122() if LAST is not None else {}
    return obj

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--arm',required=True,choices=ARMS)
    ap.add_argument('--games',nargs='*',default=list(R.FAMILIES))
    ap.add_argument('--seed',type=int,default=76)
    ap.add_argument('--out',default=str(BASE/'results'))
    ap.add_argument('--resume',action='store_true')
    args=ap.parse_args()
    out=Path(args.out)/('seed'+str(args.seed))/args.arm
    out.mkdir(parents=True,exist_ok=True)
    assert all(g in R.FAMILIES for g in args.games)
    summaries=[]
    for game in args.games:
        f=out/(game+'.json')
        if f.exists() and args.resume:ob=json.loads(f.read_text())
        else:
            try:ob=execute(game,args.arm,args.seed)
            except BaseException as e:
                f.write_text(json.dumps({'fatal':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()},indent=2))
                raise
            f.write_text(json.dumps(ob,indent=2)+'\n')
        s=ob['summary'];summaries.append(s)
        print('E122',args.arm,'SEED',args.seed,game,'LEVELS',s['levels_completed'],
              'ACTIONS',s['charged_sdk_actions'],'RESCUES',s['e122'].get('rescue_candidates_generated',0),
              'EVIDENCE',s['e122'].get('evidence_counts',{}),flush=True)
    print('ARM_TOTAL',args.arm,'SEED',args.seed,'GAMES',len(summaries),'L1',sum(s['l1'] for s in summaries),
          'L2',sum(s['l2'] for s in summaries),'L3',sum(s['l3plus'] for s in summaries),
          'ACTIONS',sum(s['charged_sdk_actions'] for s in summaries),flush=True)

if __name__=='__main__':main()
