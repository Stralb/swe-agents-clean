#!/usr/bin/env python3
"""E125: Observation-only sparse click-regime activation for teammate visual prior.
Treatments use legal ACTION6 menus plus image frequency statistics, never game id,
and never inspect hidden state/source at inference. Three-seed exploratory study.
"""
import argparse,collections,json,sys,traceback
from pathlib import Path
import numpy as np
HERE=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/sparse_click_transfer_e125_20261026')
E123=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/teammate_prior_e123_20261026')
sys.path.insert(0,str(E123))
import run_e123_l1_v2 as L
E=L.E
R=E.R
ACTIVE=('baseline','sparse80_trained','sparse70_trained','sparse80_random','sparse80_salience')
R.ARMS=tuple(dict.fromkeys(R.ARMS+ACTIVE))
orig_rank=E.PARENT._rank_ties

class SparseCore(E.PeerCore):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.e125_eligible_states=0
        self.e125_rank_calls=0
        self.e125_eligible_actions=0
    def _rank_ties(self,s,best_idx):
        if self.e123_arm not in ACTIVE[1:] or self.level>=1:
            return orig_rank(self,s,best_idx)
        n=self.nodes[s]
        legal=np.asarray(n['legal'],bool)
        # With ACTION6 (click), optionally ACTION7 (undo), and no movement
        # controls, we test the learned visual prior's specialization.
        if not legal[5] or np.any(legal[:5]):
            return orig_rank(self,s,best_idx)
        frame=np.asarray(n['f'],dtype=np.uint8)
        fraction=float(np.bincount(frame.ravel(),minlength=16).max())/4096.
        threshold=.70 if self.e123_arm=='sparse70_trained' else .80
        if fraction<threshold:
            return orig_rank(self,s,best_idx)
        self.e125_eligible_states+=1
        arm=self.e123_arm
        if arm=='sparse80_random':self.e123_arm='l1_random_prior'
        elif arm=='sparse80_salience':self.e123_arm='l1_d14_salience'
        else:self.e123_arm='l1_trained_prior'
        try:
            result=L.enhanced_rank_ties(self,s,best_idx)
            self.e125_rank_calls+=1
            return result
        finally:
            self.e123_arm=arm
    def report_e123(self):
        result=super().report_e123()
        result.update({'sparse_candidate_states':self.e125_eligible_states,
                       'sparse_prior_rank_calls':self.e125_rank_calls})
        return result

R.original.AuditedCrossLevelCore=SparseCore

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--arm',choices=ACTIVE,required=True)
    p.add_argument('--seed',type=int,default=76)
    p.add_argument('--games',nargs='*',default=list(R.FAMILIES))
    p.add_argument('--out',default=str(HERE/'results'))
    p.add_argument('--resume',action='store_true')
    a=p.parse_args()
    assert all(g in R.FAMILIES for g in a.games)
    out=Path(a.out)/('seed'+str(a.seed))/a.arm
    out.mkdir(parents=True,exist_ok=True)
    ss=[]
    for game in a.games:
        path=out/(game+'.json')
        if a.resume and path.is_file():obj=json.loads(path.read_text())
        else:
            try:obj=E.run_one(game,a.arm,a.seed)
            except BaseException as ex:
                path.write_text(json.dumps({'fatal':type(ex).__name__,'message':str(ex),'traceback':traceback.format_exc()}))
                raise
            path.write_text(json.dumps(obj,indent=2)+'\n')
        s=obj['summary'];ss.append(s)
        print('E125',a.arm,'SEED',a.seed,game,'LEVELS',s['levels_completed'],
              'ACTIONS',s['charged_sdk_actions'],'SELECTOR',s['e123'].get('sparse_prior_rank_calls',0),
              flush=True)
    print('ARM_TOTAL',a.arm,'SEED',a.seed,'N',len(ss),'L1',sum(x['l1'] for x in ss),
        'L2',sum(x['l2'] for x in ss),'L3',sum(x['l3plus'] for x in ss),
        'ACTIONS',sum(x['charged_sdk_actions'] for x in ss),
        'SELECTOR_CALLS',sum(x['e123'].get('sparse_prior_rank_calls',0) for x in ss),flush=True)
if __name__=='__main__':main()
