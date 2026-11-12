#!/usr/bin/env python3
"""E121 observation-only native-SDK experiment.
The original N117 policy and weights remain unchanged. Only the observable
click candidate set is modified; no hidden game data is read by the agent.
"""
from __future__ import annotations
import argparse,collections,hashlib,importlib.util,json,logging,os,sys,time,traceback,types
from pathlib import Path
from typing import Any

BASE=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026')
SOURCE=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_dataset1/private_dataset/my_agent.py')
SHA='0663845070e47a053076db54243c3445921a06b4bf0908b7b233c263da423bfa'
ENV=BASE/'runtime/environment_files'
SITE=BASE/'runtime/python_site'
sys.path.insert(0,str(SITE))
os.environ['OPERATION_MODE']='offline'
os.environ['ENVIRONMENTS_DIR']=str(ENV)
os.environ['ARC_ENV_ROOT']=str(ENV)
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
os.environ['MKL_NUM_THREADS']='1'
os.environ['CUDA_VISIBLE_DEVICES']=''
import numpy as np
import torch
from scipy import ndimage as ndi
from arc_agi import Arcade,OperationMode
from arcengine import GameAction,GameState

torch.set_num_threads(1)
logging.getLogger('arc_agi').setLevel(logging.ERROR)
fake=types.ModuleType('agents')
fake.__path__=[]
agentstub=types.ModuleType('agents.agent')
class Agent:pass
agentstub.Agent=Agent
sys.modules['agents']=fake
sys.modules['agents.agent']=agentstub

if hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=SHA:
    raise RuntimeError('Frozen N117 source has changed')
spec=importlib.util.spec_from_file_location('e121_original_frozen_source',SOURCE)
original=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=original
spec.loader.exec_module(original)
ORIGINAL_CANDIDATES=original.PortableAgentCore.candidates

ARMS=('baseline','near2','diverse2','diverse3')
FAMILIES=tuple(sorted(p.name for p in ENV.iterdir() if p.is_dir()))
assert len(FAMILIES)==25,(len(FAMILIES),FAMILIES)
SEED_POLICY=76
SEED_NATIVE=47
LEVEL_CAP=200

def rank_extra_points(xx:np.ndarray,yy:np.ndarray,original_i:int,count:int,arm:str)->list[int]:
    cx=float(xx.mean());cy=float(yy.mean())
    xy=np.stack((xx.astype(float),yy.astype(float)),axis=1)
    distances=(xy[:,0]-cx)**2+(xy[:,1]-cy)**2
    eligible=np.flatnonzero(np.arange(len(xx))!=original_i)
    if not len(eligible):return []
    if arm=='near2':
        ordered=eligible[np.argsort(distances[eligible],kind='stable')]
        return [int(x) for x in ordered[:count]]
    picks=[]
    anchors=[int(original_i)]
    for _ in range(min(count,len(eligible))):
        # Deterministic farthest-point sampling across the component.
        dmin=np.full(len(xx),float('inf'))
        for j in anchors:
            d=np.sum((xy-xy[j])**2,axis=1)
            dmin=np.minimum(dmin,d)
        dmin[anchors]=-1.0
        j=int(np.argmax(dmin))
        if j in anchors:break
        picks.append(j);anchors.append(j)
    return picks

def spatial_candidates(self,frame,legal,arm):
    base=list(ORIGINAL_CANDIDATES(self,frame,legal))
    if not bool(legal[5]):return base
    extras=[]
    batch=[]
    vals,counts=np.unique(frame,return_counts=True)
    sizes={int(c):int(n) for c,n in zip(vals,counts)}
    for c in vals:
        labels,_=ndi.label((frame==c)&(~self.mask))
        for idx,sl in enumerate(ndi.find_objects(labels),1):
            if sl is None:continue
            yy,xx=np.nonzero(labels[sl]==idx)
            yy=yy+sl[0].start;xx=xx+sl[1].start
            size=len(xx)
            if size<3 or size>1024:continue
            cx=float(xx.mean());cy=float(yy.mean())
            orig_idx=int(np.argmin((xx-cx)**2+(yy-cy)**2))
            group=0 if 2<=size<=160 and 2<=max(xx)-min(xx)+1<=32 else 1
            base_action=6+int(yy[orig_idx])*64+int(xx[orig_idx])
            if base_action not in base:raise AssertionError('component centroid not in original legal menu')
            batch.append((group,sizes[int(c)],size,int(orig_idx),xx,yy))
    batch.sort(key=lambda r:r[:3])
    num_extra=3 if arm=='diverse3' else 2
    seen=set(base)
    for group,color_freq,size,i,xx,yy in batch:
        for j in rank_extra_points(xx,yy,i,num_extra,arm):
            action=6+int(yy[j])*64+int(xx[j])
            if action in seen:continue
            seen.add(action)
            extras.append(action)
            if len(extras)>=48:break
        if len(extras)>=48:break
    assert all(6<=a<4102 for a in extras)
    return base+extras

def apply_arm(arm):
    assert arm in ARMS
    if arm=='baseline':
        original.PortableAgentCore.candidates=ORIGINAL_CANDIDATES
        return
    def modified(self,frame,legal):
        return spatial_candidates(self,frame,legal,arm)
    original.PortableAgentCore.candidates=modified

def legal_vector(observation):
    out=np.zeros(7,dtype=bool)
    for a in getattr(observation,'available_actions',[]) or []:
        k=int(getattr(a,'value',a))
        if k<1 or k>7:raise ValueError(('unexpected action',k))
        out[k-1]=True
    return out

def frame(observation):
    out=np.asarray(observation.frame[-1],dtype=np.uint8).copy()
    if out.shape!=(64,64):raise ValueError(out.shape)
    return out

def frame_hash(x):
    return hashlib.sha256(x.tobytes()).hexdigest()

def native_action(index):
    if 0<=index<6:
        n=(1,2,3,4,5,7)[index]
        return GameAction['ACTION'+str(n)],None
    if 6<=index<4102:
        return GameAction.ACTION6,{'x':int((index-6)%64),'y':int((index-6)//64)}
    raise ValueError(('bad action index',index))

def run(game,arm,seed_policy=SEED_POLICY,seed_native=SEED_NATIVE):
    assert game in FAMILIES
    assert arm in ARMS
    apply_arm(arm)
    start=time.monotonic()
    arc=Arcade(operation_mode=OperationMode.OFFLINE,environments_dir=str(ENV),recordings_dir=str(BASE/'runtime/recordings'),logger=logging.getLogger('E121'))
    env=arc.make(game,seed=seed_native,save_recording=False)
    if env is None:raise RuntimeError('Unable to instantiate legal public SDK')
    obs=env.observation_space
    if obs.state is GameState.NOT_PLAYED:
        obs=env.step(GameAction.RESET)
    first=frame(obs)
    core=original.AuditedCrossLevelCore(checkpoint=None,seed=seed_policy,learning=True,prior_enabled=True,puct=True,uniform=False,c=.1,temperature=2.,mode='local')
    core.start_level(int(obs.levels_completed),first)
    actions=[]
    bylevel=collections.Counter()
    wins=[]
    stop='unknown'
    extras_selected=0
    clicks_selected=0
    candidate_lengths=[]
    baseline_lengths=[]
    reward_positions=[]
    while True:
        obs=env.observation_space
        before_level=int(obs.levels_completed)
        stage=before_level+1
        if obs.state in (GameState.GAME_OVER,GameState.WIN):
            stop='native_terminal';break
        if bylevel[stage]>=LEVEL_CAP:
            stop='per_level_200_cap';break
        current_legal=legal_vector(obs)
        if not current_legal.any():
            stop='no_legal_actions';break
        before=frame(obs)
        base_candidates=ORIGINAL_CANDIDATES(core,before,current_legal)
        count_after=len(core.candidates(before,current_legal))
        baseline_lengths.append(len(base_candidates))
        candidate_lengths.append(count_after)
        chosen=int(core.choose(before,current_legal))
        native,data=native_action(chosen)
        if not current_legal[native.value-1]:
            raise AssertionError(('illegal native action',chosen,native))
        if chosen>=6:clicks_selected+=1
        chosen_extra=chosen not in base_candidates
        extras_selected+=int(chosen_extra)
        new=env.step(native,data=data)
        if new is None:raise RuntimeError('SDK returned no frame')
        new_level=int(new.levels_completed)
        if not before_level<=new_level<=before_level+1:
            raise RuntimeError(('invalid progress',before_level,new_level))
        after=frame(new)
        terminal=new.state in (GameState.GAME_OVER,GameState.WIN)
        core.observe(after,legal_vector(new),new_level,terminal=terminal)
        bylevel[stage]+=1
        row={'step':len(actions)+1,'level':stage,'a':chosen,'reward':int(new_level>before_level),
             'pixels_changed':int(np.count_nonzero(before!=after)),'chosen_extra':int(chosen_extra),
             'candidates_original':len(base_candidates),'candidates_total':count_after,
             'pre':frame_hash(before),'post':frame_hash(after),'state':str(new.state)}
        actions.append(row)
        if new_level>before_level:
            wins.append({'level':new_level,'step':len(actions),'action':chosen})
            reward_positions.append(len(actions))
        if terminal:
            stop='native_terminal';break
        if len(actions)>=3000:
            raise RuntimeError('emergency action cap exceeded')
    total=int(env.observation_space.levels_completed)
    summary={'family':game,'arm':arm,'levels_completed':total,
             'l1':int(total>=1),'l2':int(total>=2),'l3plus':int(total>=3),
             'charged_sdk_actions':len(actions),'by_level_actions':dict(bylevel),
             'initial_frame_sha':frame_hash(first),'stop':stop,'wins':wins,
             'extra_actions_selected':extras_selected,'clicks_selected':clicks_selected,
             'candidate_original_mean':float(np.mean(baseline_lengths)) if baseline_lengths else 0.,
             'candidate_total_mean':float(np.mean(candidate_lengths)) if candidate_lengths else 0.,
             'policy_seed':seed_policy,'native_seed':seed_native,'learned_updates':int(core.num_updates),
             'puct_choices':int(core.puct_choices),'elapsed_seconds':round(time.monotonic()-start,3),
             'source_sha256':SHA}
    return {'summary':summary,'trajectory':actions}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--arm',required=True,choices=ARMS)
    p.add_argument('--games',nargs='*',default=list(FAMILIES))
    p.add_argument('--out',default=str(BASE/'results'))
    p.add_argument('--policy-seed',type=int,default=SEED_POLICY)
    p.add_argument('--native-seed',type=int,default=SEED_NATIVE)
    p.add_argument('--resume',action='store_true')
    args=p.parse_args()
    out=Path(args.out)/args.arm
    out.mkdir(parents=True,exist_ok=True)
    assert all(g in FAMILIES for g in args.games)
    summaries=[]
    for game in args.games:
        path=out/(game+'.json')
        if args.resume and path.exists():
            obj=json.loads(path.read_text())
        else:
            try:obj=run(game,args.arm,args.policy_seed,args.native_seed)
            except Exception as e:
                obj={'fatal':type(e).__name__,'error':str(e),'traceback':traceback.format_exc(),'family':game,'arm':args.arm}
                path.write_text(json.dumps(obj,indent=2)+'\n')
                print('FATAL',game,args.arm,type(e).__name__,str(e),flush=True)
                raise
            path.write_text(json.dumps(obj,indent=2)+'\n')
        s=obj['summary'];summaries.append(s)
        print('E121',args.arm,game,'L',s['levels_completed'],'A',s['charged_sdk_actions'],
              'EXTRA_SELECTED',s['extra_actions_selected'],'CAND',round(s['candidate_total_mean'],1),
              'TIME_S',s['elapsed_seconds'],flush=True)
    totals={'arm':args.arm,'games':len(summaries),
            'l1':sum(s['l1'] for s in summaries),'l2':sum(s['l2'] for s in summaries),
            'l3plus':sum(s['l3plus'] for s in summaries),
            'charged_sdk_actions':sum(s['charged_sdk_actions'] for s in summaries),
            'extra_actions_selected':sum(s['extra_actions_selected'] for s in summaries),
            'clicks_selected':sum(s['clicks_selected'] for s in summaries)}
    (out/'summary.json').write_text(json.dumps({'totals':totals,'per_game':summaries},indent=2)+'\n')
    print('ARM_TOTAL',json.dumps(totals,sort_keys=True),flush=True)

if __name__=='__main__':main()
