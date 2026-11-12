#!/usr/bin/env python3
"""E124 factorial ablation of visual rarity and observed local click contingency.
The original N117 value network and native rewards are never modified.
"""
from __future__ import annotations
import argparse,json,math,sys,traceback
from pathlib import Path
import numpy as np
ROOT=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_breakthrough_e124_20261026')
sys.path.insert(0,str(ROOT))
import run_e124 as E
ARMS=('contingency','rarity_only','effect_only','random_bonus')
E.R.ARMS=tuple(dict.fromkeys(E.R.ARMS+ARMS))
ORIGINAL=E.extra_score
BASE_INIT=E.E124Core.__init__

def init(self,*args,**kwargs):
    BASE_INIT(self,*args,**kwargs)
    self.e124_ablated=self.e124_arm
    if self.e124_arm in ARMS:self.e124_arm='contingency'
E.E124Core.__init__=init

def extra(self,f,a):
    if getattr(self,'e124_ablated','contingency')=='contingency':
        return ORIGINAL(self,f,a)
    if a<6:return 0.
    mode=self.e124_ablated
    if mode=='random_bonus':
        return .045*float(self.rng.random())
    frame=np.asarray(f,np.uint8)
    x=(a-6)%64;y=(a-6)//64
    c=int(frame[y,x])
    n=float(np.count_nonzero(frame==c))/4096.
    rarity=.045*(1.-math.sqrt(n))
    yes,no=self.contingency_obs.get(c,(0,0))
    confidence=min(1.,(yes+no)/4.)
    posterior=(yes+1.)/(yes+no+2.)
    causal=.090*(posterior-.5)*confidence
    return rarity if mode=='rarity_only' else causal
E.extra_score=extra

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--arm',choices=ARMS,required=True)
    p.add_argument('--seed',type=int,default=76)
    p.add_argument('--games',nargs='*',default=list(E.R.FAMILIES))
    p.add_argument('--out',default=str(ROOT/'ablation'))
    p.add_argument('--resume',action='store_true')
    a=p.parse_args()
    path=Path(a.out)/('seed'+str(a.seed))/a.arm
    path.mkdir(parents=True,exist_ok=True)
    totals=[]
    for game in a.games:
        assert game in E.R.FAMILIES
        file=path/(game+'.json')
        if a.resume and file.is_file():result=json.loads(file.read_text())
        else:
            try:result=E.execute(game,a.arm,a.seed)
            except BaseException as err:
                file.write_text(json.dumps({'fatal':type(err).__name__,'message':str(err),'traceback':traceback.format_exc()}))
                raise
            result['summary']['ablation_arm']=a.arm
            file.write_text(json.dumps(result,indent=2)+'\n')
        ss=result['summary'];totals.append(ss)
        print('E124_ABL',a.arm,'SEED',a.seed,game,'LEVELS',ss['levels_completed'],
              'ACTIONS',ss['charged_sdk_actions'],flush=True)
    print('ABL_TOTAL',a.arm,'SEED',a.seed,'N',len(totals),'L1',sum(x['l1'] for x in totals),
          'L2',sum(x['l2'] for x in totals),'L3+',sum(x['l3plus'] for x in totals),
          'ACTIONS',sum(x['charged_sdk_actions'] for x in totals),flush=True)

if __name__=='__main__':main()
