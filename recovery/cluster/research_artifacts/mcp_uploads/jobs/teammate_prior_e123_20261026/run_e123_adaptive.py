#!/usr/bin/env python3
"""E123 exploratory online gating of teammate pretrained prior.
The gate is based solely on consecutive observed ineffective CLICK feedback.
Model and native reward remain unchanged; no game-specific names/rules at inference.
"""
from __future__ import annotations
import argparse,collections,json,sys,traceback
from pathlib import Path
import numpy as np
ROOT=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/teammate_prior_e123_20261026')
sys.path.insert(0,str(ROOT))
import run_e123_l1_v2 as L
E=L.E
ARMS=('baseline','adaptive_trained','adaptive_random')
E.R.ARMS=tuple(dict.fromkeys(E.R.ARMS+ARMS))
ORIG_RANK=L.enhanced_rank_ties
ORIG_INIT=E.PeerCore.__init__
ORIG_OBSERVE=E.PeerCore.observe

def init(self,*args,**kwargs):
    ORIG_INIT(self,*args,**kwargs)
    self.adaptive_window=collections.deque(maxlen=8)
    self.adaptive_on=False
    self.adaptive_triggered=0
    self.adaptive_ranks=0
    self.adaptive_ignored_noops=0
E.PeerCore.__init__=init

def observe(self,f,legal,completed,terminal=False):
    if self.level==0 and self.pending is not None:
        _,action,prev_level,before=self.pending
        if int(prev_level)==0 and int(completed)==0 and not terminal:
            if int(action)<6:
                self.adaptive_window.append(-1)
            else:
                x=(int(action)-6)%64;y=(int(action)-6)//64
                y0=max(0,y-4);y1=min(64,y+5)
                x0=max(0,x-4);x1=min(64,x+5)
                delta=np.asarray(before,np.uint8)!=np.asarray(f,np.uint8)
                local=int(delta[y0:y1,x0:x1].sum())
                area=(y1-y0)*(x1-x0)
                total=int(delta.sum())
                other_rate=(total-local)/max(1,4096-area)
                local_rate=local/max(1,area)
                good=(local>=2 and local_rate>other_rate+.018)
                self.adaptive_window.append(0 if good else 1)
            if not self.adaptive_on and len(self.adaptive_window)==8 and sum(v==1 for v in self.adaptive_window)>=8:
                self.adaptive_on=True
                self.adaptive_triggered=int(self.sdk_actions)
        elif int(completed)>0:
            self.adaptive_on=False
    return ORIG_OBSERVE(self,f,legal,completed,terminal=terminal)
E.PeerCore.observe=observe

def adaptive_rank(self,s,best_idx):
    if self.level==0 and self.adaptive_on and self.e123_arm in ('adaptive_trained','adaptive_random'):
        prev=self.e123_arm
        self.e123_arm='l1_trained_prior' if prev=='adaptive_trained' else 'l1_random_prior'
        try:
            result=ORIG_RANK(self,s,best_idx)
            self.adaptive_ranks+=1
            return result
        finally:
            self.e123_arm=prev
    return ORIG_RANK(self,s,best_idx)
E.PeerCore._rank_ties=adaptive_rank

OLD_REPORT=E.PeerCore.report_e123
def report(self):
    result=OLD_REPORT(self)
    result.update({'adaptive_gate_activated_at_action':self.adaptive_triggered,
                   'adaptive_ranking_calls':self.adaptive_ranks})
    return result
E.PeerCore.report_e123=report

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--arm',required=True,choices=ARMS)
    ap.add_argument('--seed',type=int,default=76)
    ap.add_argument('--games',nargs='*',default=list(E.R.FAMILIES))
    ap.add_argument('--out',default=str(ROOT/'adaptive'))
    ap.add_argument('--resume',action='store_true')
    args=ap.parse_args()
    assert all(g in E.R.FAMILIES for g in args.games)
    out=Path(args.out)/('seed'+str(args.seed))/args.arm
    out.mkdir(parents=True,exist_ok=True)
    ss=[]
    for game in args.games:
        p=out/(game+'.json')
        if args.resume and p.is_file():obj=json.loads(p.read_text())
        else:
            try:obj=E.run_one(game,args.arm,args.seed)
            except BaseException as e:
                p.write_text(json.dumps({'fatal':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()},indent=2))
                raise
            p.write_text(json.dumps(obj,indent=2)+'\n')
        s=obj['summary'];ss.append(s)
        print('E123_GATE',args.arm,'SEED',args.seed,game,'LEVELS',s['levels_completed'],
              'ACTIONS',s['charged_sdk_actions'],
              'GATE',s['e123'].get('adaptive_gate_activated_at_action',0),
              'ACTIVATED_RANK',s['e123'].get('adaptive_ranking_calls',0),flush=True)
    print('ARM_TOTAL',args.arm,'SEED',args.seed,'N',len(ss),
        'L1',sum(x['l1'] for x in ss),'L2',sum(x['l2'] for x in ss),
        'L3',sum(x['l3plus'] for x in ss),
        'TOTAL_LEVELS',sum(x['levels_completed'] for x in ss),
        'ACTIONS',sum(x['charged_sdk_actions'] for x in ss),
        'GATE_GAMES',sum(bool(x['e123'].get('adaptive_gate_activated_at_action')) for x in ss),
        flush=True)

if __name__=='__main__':main()
