#!/usr/bin/env python3
"""Conservative teammate-prior transfer: intervention only on weak N117 ties.
All decisions use legal actions and observed pixels; no game identity routing.
"""
import argparse,json,sys,traceback
from pathlib import Path
import numpy as np
B=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/teammate_prior_e123_20261026')
sys.path.insert(0,str(B))
import run_e123_l1_v2 as L
E=L.E
R=E.R
ARMS=('baseline','confidence_trained','confidence_random')
R.ARMS=tuple(dict.fromkeys(R.ARMS+ARMS))

class ConfidenceCore(E.PeerCore):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.conf_checked=0
        self.conf_switched=0
        self.conf_rejected=0
    def _rank_ties(self,s,best_idx):
        # Original action first. Unchanged RNG state/decision if switch rejected.
        base=int(E.PARENT._rank_ties(self,s,best_idx))
        if self.level>=1 or self.e123_arm not in ARMS[1:]:
            return base
        node=self.nodes[s]
        acts=np.asarray(node['actions'],dtype=np.int64)
        valid=acts[best_idx]
        clicks=valid[valid>=6]
        if base<6 or len(clicks)<2 or not self.prior_enabled:
            return base
        if 'prior' not in node or len(node['prior'])!=len(acts):
            raise RuntimeError('Original frozen model prior missing')
        original_logits=node['prior'][best_idx]
        med=float(np.median(original_logits))
        std=max(.02,float(np.std(original_logits)))
        original_lookup=dict(zip(map(int,valid),map(float,original_logits)))
        def frozen_score(a):
            z=float(np.clip((original_lookup[int(a)]-med)/std,-3,3))
            return .55*z+.90*float(self.beliefs.rank(node['f'],int(a)))
        pretrained=E.model_for('trained' if self.e123_arm=='confidence_trained' else 'random')
        prev=self.prev if self.prev is not None else node['f']
        peer=E.peer_scores(pretrained,node['f'],prev,acts)
        pick=int(max(map(int,clicks),key=lambda a:(peer.get(a,0),-a)))
        self.conf_checked+=1
        if pick==base:return base
        if (peer.get(pick,0.)>=1.25 and peer.get(pick,0.)-peer.get(base,0.)>=1.25
           and frozen_score(base)-frozen_score(pick)<=.15):
            self.conf_switched+=1
            return pick
        self.conf_rejected+=1
        return base
    def report_e123(self):
        x=super().report_e123()
        x.update({'confidence_checked':self.conf_checked,'confidence_switched':self.conf_switched,
            'confidence_rejected':self.conf_rejected})
        return x

R.original.AuditedCrossLevelCore=ConfidenceCore
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--arm',choices=ARMS,required=True)
    ap.add_argument('--seed',type=int,default=76)
    ap.add_argument('--games',nargs='*',default=list(R.FAMILIES))
    ap.add_argument('--out',default=str(B/'conservative'))
    ap.add_argument('--resume',action='store_true')
    opts=ap.parse_args()
    out=Path(opts.out)/('seed'+str(opts.seed))/opts.arm
    out.mkdir(parents=True,exist_ok=True)
    ss=[]
    for game in opts.games:
        assert game in R.FAMILIES
        f=out/(game+'.json')
        if f.is_file() and opts.resume:ob=json.loads(f.read_text())
        else:
            try:ob=E.run_one(game,opts.arm,opts.seed)
            except BaseException as ex:
                f.write_text(json.dumps({'fatal':type(ex).__name__,'message':str(ex),'traceback':traceback.format_exc()},indent=2))
                raise
            f.write_text(json.dumps(ob,indent=2)+'\n')
        s=ob['summary'];ss.append(s)
        print('E123C',opts.arm,opts.seed,game,'L',s['levels_completed'],
          'A',s['charged_sdk_actions'],'SWITCHES',s['e123'].get('confidence_switched',0),flush=True)
    print('ARM_TOTAL',opts.arm,'SEED',opts.seed,'GAMES',len(ss),
      'L1',sum(s['l1'] for s in ss),'L2',sum(s['l2'] for s in ss),
      'L3PLUS',sum(s['l3plus'] for s in ss),'ACTIONS',sum(s['charged_sdk_actions'] for s in ss),
      'SWITCHES',sum(s['e123'].get('confidence_switched',0) for s in ss),flush=True)
if __name__=='__main__':main()
