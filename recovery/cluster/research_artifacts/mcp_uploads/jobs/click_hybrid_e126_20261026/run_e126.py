#!/usr/bin/env python3
"""E126 public-SDK hybrid: E124 observed click-contingency ranking plus
E125 selectively transferred teammate frozen effect prior in click-only sparse scenes.
No hidden state, no LLM, no game-ID dispatch; no Kaggle submissions.
"""
from __future__ import annotations
import argparse,json,sys,traceback
from pathlib import Path
import numpy as np
HERE=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_hybrid_e126_20261026')
E124_BASE=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_breakthrough_e124_20261026')
E123_BASE=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/teammate_prior_e123_20261026')
sys.path.insert(0,str(E124_BASE))
sys.path.insert(0,str(E123_BASE))
import run_e124 as E124
import run_e123_l1_v2 as L
R=E124.R
ARMS=('baseline','contingency_only','hybrid_trained','hybrid_random','hybrid_salience')
R.ARMS=tuple(dict.fromkeys(R.ARMS+ARMS))
ACTIVE='baseline'
LAST=None

class Hybrid(E124.E124Core):
    def __init__(self,*args,**kwargs):
        global LAST
        super().__init__(*args,**kwargs)
        self.e126_arm=ACTIVE
        self.e123_arm={'hybrid_random':'l1_random_prior',
                       'hybrid_salience':'l1_d14_salience'}.get(ACTIVE,'l1_trained_prior')
        self.e123_active_count=0
        self.e126_gate_calls=0
        self.e126_gate_frames=0
        self.e126_fallback_calls=0
        LAST=self

    def _rank_ties(self,s,best_idx):
        if self.level>=1 or self.e126_arm not in ('hybrid_trained','hybrid_random','hybrid_salience'):
            self.e126_fallback_calls+=1
            return super()._rank_ties(s,best_idx)
        nd=self.nodes[s]
        legal=np.asarray(nd['legal'],bool)
        if not bool(legal[5]) or bool(np.any(legal[:5])):
            self.e126_fallback_calls+=1
            return super()._rank_ties(s,best_idx)
        frame=np.asarray(nd['f'],dtype=np.uint8)
        dominant=float(np.bincount(frame.ravel(),minlength=16).max())/4096.
        if dominant<.80:
            self.e126_fallback_calls+=1
            return super()._rank_ties(s,best_idx)
        self.e126_gate_calls+=1
        self.e126_gate_frames+=1
        return L.enhanced_rank_ties(self,s,best_idx)

    def report_e126(self):
        return {'arm':self.e126_arm,
                'sparse_gate_calls':self.e126_gate_calls,
                'fallback_calls':self.e126_fallback_calls,
                'transferred_ranks':self.e123_active_count,
                'contingency':self.report_e124()}

R.original.AuditedCrossLevelCore=Hybrid
R.apply_arm=E124.apply_arm

def do_one(game,arm,seed):
    global ACTIVE,LAST
    ACTIVE=arm
    E124.ACTIVE='baseline' if arm=='baseline' else 'contingency'
    LAST=None
    ob=R.run(game,arm,seed_policy=seed,seed_native=47)
    ob['summary']['E126']=LAST.report_e126() if LAST is not None else {}
    return ob

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--arm',required=True,choices=ARMS)
    ap.add_argument('--seed',type=int,default=76)
    ap.add_argument('--games',nargs='*',default=list(R.FAMILIES))
    ap.add_argument('--out',default=str(HERE/'results'))
    ap.add_argument('--resume',action='store_true')
    args=ap.parse_args()
    out=Path(args.out)/('seed'+str(args.seed))/args.arm
    out.mkdir(parents=True,exist_ok=True)
    summaries=[]
    for game in args.games:
        assert game in R.FAMILIES
        path=out/(game+'.json')
        if args.resume and path.is_file():ob=json.loads(path.read_text())
        else:
            try:ob=do_one(game,args.arm,args.seed)
            except BaseException as err:
                path.write_text(json.dumps({'fatal':type(err).__name__,'message':str(err),
                     'traceback':traceback.format_exc()},indent=2))
                raise
            path.write_text(json.dumps(ob,indent=2)+'\n')
        s=ob['summary'];summaries.append(s)
        print('E126',args.arm,'seed',args.seed,game,'levels',s['levels_completed'],
          'actions',s['charged_sdk_actions'],'gate',s['E126']['sparse_gate_calls'],flush=True)
    print('ARM_TOTAL',args.arm,'seed',args.seed,'N',len(summaries),
      'L1',sum(x['l1'] for x in summaries),'L2',sum(x['l2'] for x in summaries),
      'L3',sum(x['l3plus'] for x in summaries),
      'ACTIONS',sum(x['charged_sdk_actions'] for x in summaries),
      'GATED',sum(x['E126']['sparse_gate_calls'] for x in summaries),flush=True)

if __name__=='__main__':main()
