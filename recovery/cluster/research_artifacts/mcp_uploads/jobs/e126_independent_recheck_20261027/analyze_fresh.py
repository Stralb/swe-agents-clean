#!/usr/bin/env python3
"""Independent post-run evaluation of 79-81 matched N117/E126 native SDK records."""
from pathlib import Path
import csv, json, statistics
ROOT=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs')
BASE=ROOT/'e126_independent_recheck_20261027'
FRESH=BASE/'fresh'
ENV=ROOT/'click_diversity_e121_20261026/runtime/environment_files'
games=sorted(p.name for p in ENV.iterdir() if p.is_dir())
assert len(games)==25, len(games)
meta={g:json.loads(next((ENV/g).glob('*/metadata.json')).read_text()) for g in games}
rows=[]
details=[]
def score(o,g):
    baseline=list(map(int,meta[g]['baseline_actions']))
    denominator=len(baseline)*(len(baseline)+1)/2
    numerator=0.
    prev=0
    for i,w in enumerate(o['summary']['wins'],1):
        assert int(w['level'])==i
        elapsed=int(w['step'])-prev
        assert elapsed>0
        prev=int(w['step'])
        numerator+=i*min(115.,100.*(baseline[i-1]/elapsed)**2)
    done=int(o['summary']['levels_completed'])
    return min(numerator/denominator, sum(range(1,done+1))/denominator*100.)
for seed in (79,80,81):
    cases={}
    for arm in ('baseline','hybrid_trained'):
        p=FRESH/('seed'+str(seed))/arm
        expected={g+'.json' for g in games}
        actual={x.name for x in p.glob('*.json')}
        assert actual==expected, (seed,arm, sorted(expected-actual), sorted(actual-expected))
        entries={}
        for g in games:
            o=json.loads((p/(g+'.json')).read_text())
            assert 'fatal' not in o,(seed,arm,g,o.get('message'))
            s=o['summary']
            trajectory=o['trajectory']
            assert s['policy_seed']==seed
            assert s['native_seed']==47
            assert s['charged_sdk_actions']==len(trajectory)
            assert sum(int(t['reward']) for t in trajectory)==s['levels_completed']
            assert all(0<=int(t['a'])<4102 for t in trajectory)
            assert all(trajectory[j]['post']==trajectory[j+1]['pre'] for j in range(len(trajectory)-1))
            assert s['source_sha256']=='0663845070e47a053076db54243c3445921a06b4bf0908b7b233c263da423bfa'
            entries[g]=o
        cases[arm]=entries
        summaries=[entries[g]['summary'] for g in games]
        scores=[score(entries[g],g) for g in games]
        rows.append({'seed':seed,'arm':arm,'games':25,'L1':sum(x['l1'] for x in summaries),
            'L2':sum(x['l2'] for x in summaries),'L3plus':sum(x['l3plus'] for x in summaries),
            'levels':sum(x['levels_completed'] for x in summaries),
            'SDK_calls':sum(x['charged_sdk_actions'] for x in summaries),
            'mean_score_0_100':round(statistics.mean(scores),9),
            'native_wins':sum(x['stop']=='native_terminal' and x['levels_completed']==len(meta[g]['baseline_actions']) for g,x in zip(games,summaries))})
    for g in games:
        b=cases['baseline'][g]
        c=cases['hybrid_trained'][g]
        assert b['summary']['initial_frame_sha']==c['summary']['initial_frame_sha'],(seed,g,'mismatched starting frame')
        bl=int(b['summary']['levels_completed'])
        cl=int(c['summary']['levels_completed'])
        bs=score(b,g);cs=score(c,g)
        details.append({'seed':seed,'game':g,'baseline_levels':bl,'E126_levels':cl,
            'delta_levels':cl-bl,'baseline_score':round(bs,9),'E126_score':round(cs,9),
            'delta_score':round(cs-bs,9),
            'baseline_calls':b['summary']['charged_sdk_actions'],
            'E126_calls':c['summary']['charged_sdk_actions']})
out=BASE/'fresh_audit'
out.mkdir(exist_ok=True)
for name,data in [('summary.csv',rows),('paired_games.csv',details)]:
    with (out/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]))
        w.writeheader();w.writerows(data)
all_gains=[r for r in details if r['delta_levels']>0]
all_losses=[r for r in details if r['delta_levels']<0]
md=['# Fresh E126 matched study (policy seeds 79-81)','',
    'Native seed 47; 25 previously exposed public games per arm per seed; 200-action per-level cap. ',
    'These are fresh native evaluation episodes, not unseen layouts or Kaggle hidden scores.','',
    '| Seed | Agent | L1 | L2 | L3+ | Total | Mean native SDK score | SDK calls |',
    '|---:|---|---:|---:|---:|---:|---:|---:|']
for x in rows:
    md.append('| {seed} | {arm} | {L1} | {L2} | {L3plus} | {levels} | {mean_score_0_100:.6f} | {SDK_calls} |'.format(**x))
md.extend(['',f'Paired level gain trials: {len(all_gains)}; regression trials: {len(all_losses)}.',
    'Gains: '+str([(x['seed'],x['game'],x['delta_levels']) for x in all_gains]),
    'Losses: '+str([(x['seed'],x['game'],x['delta_levels']) for x in all_losses]),
    '','Score differences should not be interpreted as independent unseen-game generalization.',
    'Policy seed replication may repeat identical physical trajectories.',
    ''])
(out/'REPORT.md').write_text('\n'.join(md))
print('\n'.join(md),flush=True)
print('FRESH_RECHECK_AUDIT_COMPLETE',flush=True)
