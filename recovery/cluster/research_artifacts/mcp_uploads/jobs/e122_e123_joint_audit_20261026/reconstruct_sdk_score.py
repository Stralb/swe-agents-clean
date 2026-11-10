#!/usr/bin/env python3
"""Reconstruct official local SDK 0-100 per-game score from public metadata and
audited native reward-step traces, validated against SDK scorecard smoke tests.
No Kaggle or hidden game source is accessed.
"""
import csv,json,math,zipfile,hashlib
from pathlib import Path
ROOT=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs')
E121=ROOT/'click_diversity_e121_20261026'
E123=ROOT/'teammate_prior_e123_20261026'
E122=ROOT/'click_feedback_e122_20261026'
OUT=ROOT/'e122_e123_joint_audit_20261026/analysis'
META=E121/'runtime/environment_files'
db={}
for top in sorted(META.iterdir()):
    if top.is_dir():
        files=list(top.glob('*/metadata.json'))
        assert len(files)==1,(top,files)
        item=json.loads(files[0].read_text())
        assert item['game_id'].startswith(top.name+'-')
        assert item['baseline_actions']
        db[top.name]=item
assert len(db)==25

def level_scores(episode,game):
    human=list(map(int,db[game]['baseline_actions']))
    total_n=len(human)
    assert total_n>=3
    wins=episode['summary']['wins']
    assert len(wins)==episode['summary']['levels_completed']
    prev=0
    numer=0.
    weight_completed=0.
    per_level=[]
    for idx,w in enumerate(wins):
        assert int(w['level'])==idx+1
        charged=int(w['step'])-prev
        assert charged>0
        prev=int(w['step'])
        native= min(115.,(human[idx]/charged)**2*100.)
        per_level.append((idx+1,charged,human[idx],native))
        numer+=(idx+1)*native
        weight_completed+=idx+1
    denom=total_n*(total_n+1)/2.
    return min(numer/denom,weight_completed/denom*100.),per_level

sets=[
    ('E122',E122/'results',[76,77,78],
     ['baseline','feedback_rescue_all','feedback_rescue_l2','local_credit_l2','rescue_credit_l2']),
    ('E123_L2',E123/'results',[76],
     ['baseline','peer_salience','peer_random','peer_trained','peer_gated','peer_trained_salience']),
    ('E123_L1',E123/'level1',[76,77,78],
     ['baseline','l1_d14_salience','l1_random_prior','l1_trained_prior']),
    ('E123_adaptive',E123/'adaptive',[76],
     ['baseline','adaptive_trained','adaptive_random']),
]
rows=[];game_rows=[];effect_rows=[];scores={}
for family,path,seeds,arms in sets:
  for seed in seeds:
    for arm in arms:
      folder=path/('seed'+str(seed))/arm
      if not folder.is_dir():
         if family=='E122' and seed!=76 and arm=='feedback_rescue_all':continue
         raise RuntimeError('MISSING '+str(folder))
      records=sorted(f for f in folder.glob('*.json') if f.name!='summary.json')
      if len(records)<25:
         if family=='E122' and seed!=76 and arm=='feedback_rescue_all':continue
         raise RuntimeError('INCOMPLETE '+str(folder)+' files '+str(len(records)))
      assert len(records)==25
      sums=[]
      for f in records:
        episode=json.loads(f.read_text())
        assert 'fatal' not in episode,f
        game=episode['summary']['family']
        pts,per=level_scores(episode,game)
        sums.append(pts)
        scores[(family,seed,arm,game)]=pts
        game_rows.append({'study':family,'seed':seed,'condition':arm,'game':game,
            'native_score_0_100':round(pts,10),'levels':episode['summary']['levels_completed'],
            'sdk_actions':episode['summary']['charged_sdk_actions']})
      rows.append({'study':family,'seed':seed,'condition':arm,
          'mean_sdk_score_0_100':round(sum(sums)/25.,10),
          'nonzero_game_scores':sum(x>0 for x in sums),
          'games':25})
      print('SCORE',family,'SEED',seed,arm,'MEAN',round(sum(sums)/25.,9),
          'GAMES_WITH_SCORE',sum(x>0 for x in sums),flush=True)
# Explicit exact SDK smoke matches for tested game/arm pairs.
smoke={('dc22','baseline'):4.761904762,('lf52','baseline'):0.961682945,
       ('tn36','baseline'):3.571428571,('dc22','l1_d14_salience'):4.761904762,
       ('lf52','l1_d14_salience'):1.818181818,('tn36','l1_d14_salience'):3.571428571}
for (game,arm),expected in smoke.items():
    got=scores[('E123_L1',76,arm,game)]
    assert abs(got-expected)<1e-7,(game,arm,got,expected)
# Pairwise observed score deltas; score levels 0 to 100, NOT Kaggle leaderboard.
for row in rows:
    if row['condition']=='baseline':continue
    family=row['study'];seed=row['seed'];arm=row['condition']
    baseline=next(x for x in rows if x['study']==family and x['seed']==seed and x['condition']=='baseline')
    pergame=[(g,scores[(family,seed,arm,g)]-scores[(family,seed,'baseline',g)]) for g in sorted(db)]
    gain=[(g,round(d,7)) for g,d in pergame if d>1e-9]
    loss=[(g,round(d,7)) for g,d in pergame if d<-1e-9]
    result={'study':family,'seed':seed,'condition':arm,'baseline':baseline['mean_sdk_score_0_100'],
            'candidate':row['mean_sdk_score_0_100'],
            'delta_sdk_score':round(row['mean_sdk_score_0_100']-baseline['mean_sdk_score_0_100'],10),
            'score_gain_games':str(gain),'score_loss_games':str(loss)}
    effect_rows.append(result)
    print('PAIRED_SCORE',json.dumps(result,sort_keys=True),flush=True)

def output_csv(filename,records):
    with (OUT/filename).open('w',newline='') as ff:
        writer=csv.DictWriter(ff,fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
output_csv('local_sdk_score_means.csv',rows)
output_csv('local_sdk_score_per_game.csv',game_rows)
output_csv('local_sdk_score_deltas.csv',effect_rows)
print('SCORE_VERIFICATION_COMPLETE',len(rows),'ARMS',len(game_rows),'EPISODES')
