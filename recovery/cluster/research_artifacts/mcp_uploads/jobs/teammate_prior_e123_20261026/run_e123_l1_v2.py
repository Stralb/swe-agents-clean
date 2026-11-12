#!/usr/bin/env python3
"""E123 additional treatment: teammate salience or learned prior in original N117 L1 tie ranking.
Preserves the exact N117 tie-break calculation except one predeclared bonus.
"""
from __future__ import annotations
import argparse,hashlib,json,sys,traceback
from pathlib import Path
import numpy as np,torch
ROOT=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/teammate_prior_e123_20261026')
sys.path.insert(0,str(ROOT))
import run_e123_v2 as E
ARMS=('baseline','l1_d14_salience','l1_random_prior','l1_trained_prior')
E.R.ARMS=tuple(dict.fromkeys(E.R.ARMS+ARMS))
ORIG=E.PARENT._rank_ties

def enhanced_rank_ties(self,s,best_idx):
    if self.e123_arm not in ARMS[1:] or self.level>=1:
        return ORIG(self,s,best_idx)
    nd=self.nodes[s]
    acts=np.asarray(nd['actions'],dtype=np.int64)
    valid=acts[best_idx]
    if len(valid)==1:return int(valid[0])
    if self.prior_enabled:
        if 'prior' not in nd or len(nd['prior'])!=len(acts):
            with torch.inference_mode():
                x=E.R.original.action_features(nd['f'],self.prev,nd['legal'],acts,self.last)
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
    if self.e123_arm=='l1_d14_salience':
        extra=E.salience_scores(nd['f'],acts)
    else:
        kind='random' if self.e123_arm=='l1_random_prior' else 'trained'
        prev=self.prev if self.prev is not None else nd['f']
        extra=E.peer_scores(E.model_for(kind),nd['f'],prev,acts)
    scores=[]
    for a in subset:
        b=self.beliefs.rank(nd['f'],int(a))
        ps=float(np.clip((lookup.get(a,mid)-mid)/spread,-3.,3.))
        # Original N117 scoring untouched except the last extra term.
        score=.55*ps+.90*b+float(self.rng.uniform(0,.02))+.13*extra.get(int(a),0.)
        scores.append((score,int(a)))
    self.e123_active_count+=len(subset)
    return max(scores)[1]

E.PeerCore._rank_ties=enhanced_rank_ties

def main():
    pa=argparse.ArgumentParser()
    pa.add_argument('--arm',required=True,choices=ARMS)
    pa.add_argument('--seed',type=int,default=76)
    pa.add_argument('--games',nargs='*',default=list(E.R.FAMILIES))
    pa.add_argument('--out',default=str(ROOT/'level1'))
    pa.add_argument('--resume',action='store_true')
    args=pa.parse_args()
    assert all(g in E.R.FAMILIES for g in args.games)
    out=Path(args.out)/('seed'+str(args.seed))/args.arm
    out.mkdir(parents=True,exist_ok=True)
    summaries=[]
    for game in args.games:
        path=out/(game+'.json')
        if path.exists() and args.resume:obj=json.loads(path.read_text())
        else:
            try:obj=E.run_one(game,args.arm,args.seed)
            except BaseException as e:
                path.write_text(json.dumps({'fatal':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()}))
                raise
            path.write_text(json.dumps(obj,indent=2)+'\n')
        s=obj['summary'];summaries.append(s)
        print('E123_L1',args.arm,'SEED',args.seed,game,'LEVELS',s['levels_completed'],
              'ACTIONS',s['charged_sdk_actions'],'BONUS_SCORES',s['e123'].get('prior_adjusted_candidates',0),flush=True)
    print('ARM_TOTAL',args.arm,'SEED',args.seed,'GAMES',len(summaries),'L1',sum(s['l1'] for s in summaries),
          'L2',sum(s['l2'] for s in summaries),'L3',sum(s['l3plus'] for s in summaries),
          'ACTIONS',sum(s['charged_sdk_actions'] for s in summaries),flush=True)

if __name__=='__main__':main()
