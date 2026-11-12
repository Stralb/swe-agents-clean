#!/usr/bin/env python3
"""Predeclared extra robustness check, no tuning. 4 fresh policy/native seed pairs,
same 25 previously exposed public families. Not hidden Kaggle evaluation.
"""
from pathlib import Path
import csv,hashlib,importlib.util,json,sys
from collections import defaultdict
ROOT=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs')
HERE=ROOT/'e128_release_20261027'
E121=ROOT/'click_diversity_e121_20261026'
REFERENCE=ROOT/'click_hybrid_e126_20261026'
sys.path.insert(0,str(E121))
import run_e121 as R

def load_agent():
    src=HERE/'release/my_agent.py'
    spec=importlib.util.spec_from_file_location('e128_robust_agent',src)
    m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m
    spec.loader.exec_module(m)
    assert hashlib.sha256(src.read_bytes()).hexdigest()=='84f27a2589575558ddb85dff2539f68d1937c6dc1a048cb3b133f6ae7005178c'
    return m
agent=load_agent()
orig=R.original.AuditedCrossLevelCore
R.ARMS=tuple(dict.fromkeys(R.ARMS+('baseline','hybrid_trained')))
R.apply_arm=lambda arm:None
META={p.name:json.loads(next(p.glob('*/metadata.json')).read_text()) for p in R.ENV.iterdir() if p.is_dir()}
assert len(META)==25

def sdk_score(obj,g):
    hs=META[g]['baseline_actions'];d=len(hs)*(len(hs)+1)/2.;v=0.;last=0
    for w in obj['summary']['wins']:
        lv=int(w['level']);n=int(w['step'])-last;last=int(w['step'])
        assert n>0
        v+=lv*min(115.,100.*(hs[lv-1]/n)**2)
    completed=obj['summary']['levels_completed']
    return min(v/d,sum(range(1,completed+1))/d*100.)

def save_csv(path,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader();w.writerows(rows)

out=HERE/'robustness'
out.mkdir(parents=True,exist_ok=True)
seed_pairs=((79,48),(80,49),(81,50),(82,51))
summary=[];games=[]
for policy_seed,native_seed in seed_pairs:
    base_results={};variant_results={}
    for g in sorted(META):
        for mode,cls,collection in (
            ('baseline',orig,base_results),
            ('hybrid_trained',agent.E126Core,variant_results)):
            R.original.AuditedCrossLevelCore=cls
            result=R.run(g,mode,seed_policy=policy_seed,seed_native=native_seed)
            collection[g]=result
            print('HOLDOUT',policy_seed,native_seed,g,mode,
                'LEVELS',result['summary']['levels_completed'],
                'ACTIONS',result['summary']['charged_sdk_actions'],flush=True)
    gained=[];lost=[];changed_initial=0
    for g in sorted(META):
        b=base_results[g];v=variant_results[g]
        assert b['summary']['initial_frame_sha']==v['summary']['initial_frame_sha']
        old=json.loads((REFERENCE/'results/seed76/baseline'/(g+'.json')).read_text())['summary']
        changed_initial+=int(b['summary']['initial_frame_sha']!=old['initial_frame_sha'])
        bl=b['summary']['levels_completed'];vl=v['summary']['levels_completed']
        if vl>bl:gained.append(g)
        if vl<bl:lost.append(g)
        games.append({'policy_seed':policy_seed,'native_seed':native_seed,'game':g,
            'baseline_levels':bl,'hybrid_levels':vl,'delta_levels':vl-bl,
            'baseline_score':round(sdk_score(b,g),10),
            'hybrid_score':round(sdk_score(v,g),10),
            'baseline_actions':b['summary']['charged_sdk_actions'],
            'hybrid_actions':v['summary']['charged_sdk_actions']})
    btot=sum(x['summary']['levels_completed'] for x in base_results.values())
    vtot=sum(x['summary']['levels_completed'] for x in variant_results.values())
    scoreb=sum(sdk_score(x,g) for g,x in base_results.items())/25
    scorev=sum(sdk_score(x,g) for g,x in variant_results.items())/25
    row={'policy_seed':policy_seed,'native_seed':native_seed,
         'baseline_levels':btot,'E126_levels':vtot,'delta_levels':vtot-btot,
         'baseline_sdk_mean':round(scoreb,10),'E126_sdk_mean':round(scorev,10),
         'delta_sdk_mean':round(scorev-scoreb,10),
         'gained_families':','.join(gained),'lost_families':','.join(lost),
         'different_initial_frames_vs_seed47':changed_initial}
    summary.append(row)
    print('HOLDOUT_SUMMARY',json.dumps(row,sort_keys=True),flush=True)
save_csv(out/'holdout_per_game.csv',games)
save_csv(out/'holdout_summary.csv',summary)
(out/'holdout_summary.json').write_text(json.dumps({
    'protocol':'PREDECLARED_POLICY_NATIVE_PAIRS_79_48_TO_82_51',
    'source_sha256':'84f27a2589575558ddb85dff2539f68d1937c6dc1a048cb3b133f6ae7005178c',
    'all_games_previously_exposed':True,
    'no_tuning_after_result':True,
    'results':summary,
    'Kaggle_submission_count':0},indent=2)+'\n')
print('E128_ROBUSTNESS_COMPLETE',len(games),'GAME_PAIRS',flush=True)
