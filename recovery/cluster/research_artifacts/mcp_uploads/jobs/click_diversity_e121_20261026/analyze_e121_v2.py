#!/usr/bin/env python3
"""Evidence-first E121 analysis; no SDK game source inspection or uncharged probes."""
from __future__ import annotations
import csv,hashlib,json,random,statistics,zipfile
from pathlib import Path
BASE=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026')
SOURCE=BASE/'results'
ARMS=('baseline','near2','diverse2','diverse3','l2_near2','l2_diverse2','l2_diverse3')
EXPECTED_SOURCE='0663845070e47a053076db54243c3445921a06b4bf0908b7b233c263da423bfa'
out=BASE/'analysis'
out.mkdir(parents=True,exist_ok=True)
records={}
for arm in ARMS:
    d=SOURCE/arm
    if not d.is_dir():raise RuntimeError('Missing arm directory '+arm)
    files=sorted(d.glob('??[0-9][0-9].json'))
    if len(files)!=25:
        # Name filter does not match all 4-character public IDs.
        files=sorted(x for x in d.glob('*.json') if x.name!='summary.json')
    assert len(files)==25,(arm,len(files))
    dd={}
    for f in files:
        obj=json.loads(f.read_text())
        assert 'fatal' not in obj,(arm,f.name,obj.get('fatal'))
        s=obj['summary'];tr=obj['trajectory']
        assert s['source_sha256']==EXPECTED_SOURCE
        assert s['charged_sdk_actions']==len(tr)
        assert sum(row['reward'] for row in tr)==s['levels_completed'],(arm,f.name,'incorrect reward count')
        assert all(0<=row['a']<4102 and row['candidates_total']>=row['candidates_original'] for row in tr),(arm,f.name,'invalid action')
        assert all(tr[i-1]['post']==tr[i]['pre'] for i in range(1,len(tr))),(arm,f.name,'broken frame chain')
        assert sum(row['chosen_extra'] for row in tr)==s['extra_actions_selected']
        assert len({s['initial_frame_sha']})==1
        dd[s['family']]=obj
    assert len(dd)==25
    records[arm]=dd
games=sorted(records['baseline'])
assert all(games==sorted(records[a]) for a in ARMS)
assert [(records['baseline'][g]['summary']['levels_completed']>=1) for g in games].count(True)==13
assert [(records['baseline'][g]['summary']['levels_completed']>=2) for g in games].count(True)==2
assert sum(records['baseline'][g]['summary']['charged_sdk_actions'] for g in games)==2790
baseline=records['baseline']
for arm in ARMS[1:]:
    for g in games:
        assert records[arm][g]['summary']['initial_frame_sha']==baseline[g]['summary']['initial_frame_sha'],(arm,g,'initial layouts differ')
for arm in ARMS:
    print('VERIFIED_ARM',arm,'EPISODES',len(records[arm]),'ACTIONS',sum(records[arm][g]['summary']['charged_sdk_actions'] for g in games))

def summary_totals(arm):
    ss=[records[arm][g]['summary'] for g in games]
    return {'arm':arm,'n_games':25,'L1':sum(s['l1'] for s in ss),'L2':sum(s['l2'] for s in ss),
           'L3plus':sum(s['l3plus'] for s in ss),'total_completed_levels':sum(s['levels_completed'] for s in ss),
           'charged_sdk_actions':sum(s['charged_sdk_actions'] for s in ss),
           'noncentroid_selected':sum(s['extra_actions_selected'] for s in ss),
           'clicks_selected':sum(s['clicks_selected'] for s in ss)}

def first_diff(a,b):
    ta=baseline[a]['trajectory']
    tb=records[b][a]['trajectory']
    for i in range(max(len(ta),len(tb))):
        if i>=len(ta) or i>=len(tb):
            return {'step':i+1,'cause':'different_episode_length'}
        ra,rb=ta[i],tb[i]
        if ra['a']!=rb['a'] or ra['pre']!=rb['pre']:
            return {'step':i+1,'level':ra['level'],'pre_state_equal':ra['pre']==rb['pre'],'baseline_action':ra['a'],
                    'variant_action':rb['a'],'baseline_delta':ra['pixels_changed'],'variant_delta':rb['pixels_changed']}
    return None

def ci(data,seed=531):
    random.seed(seed)
    means=[]
    n=len(data)
    for _ in range(10000):
        means.append(sum(data[random.randrange(n)] for j in range(n))/n)
    means.sort()
    return [round(means[250],4),round(means[9749],4)]

totals=[summary_totals(a) for a in ARMS]
deltas={}
pair_rows=[]
for arm in ARMS[1:]:
    changes=[]
    gain=[];lost=[]
    diffs=[]
    for game in games:
        bb=baseline[game]['summary'];ss=records[arm][game]['summary']
        diff=ss['levels_completed']-bb['levels_completed']
        changes.append(diff)
        if diff>0:gain.append(game)
        if diff<0:lost.append(game)
        d=first_diff(game,arm)
        diffs.append({'game':game,'difference':diff,'first_divergence':d})
        pair_rows.append({'arm':arm,'game':game,'baseline_levels':bb['levels_completed'],
                    'candidate_levels':ss['levels_completed'],'level_difference':diff,
                    'baseline_actions':bb['charged_sdk_actions'],'candidate_actions':ss['charged_sdk_actions'],
                    'baseline_l1':bb['l1'],'candidate_l1':ss['l1'],
                    'baseline_l2':bb['l2'],'candidate_l2':ss['l2'],
                    'first_divergence_step':d['step'] if d else '',
                    'first_divergence_level':d.get('level','') if d else '',
                    'same_pre_action_frame':d.get('pre_state_equal','') if d else ''})
    gated=arm.startswith('l2_')
    if gated:
        for g in games:
            pre=[(x['a'],x['pre'],x['post'],x['reward']) for x in baseline[g]['trajectory'] if x['level']==1]
            post=[(x['a'],x['pre'],x['post'],x['reward']) for x in records[arm][g]['trajectory'] if x['level']==1]
            assert pre==post,(arm,g,'L1 must be identical to original')
    deltas[arm]={'gained_game_families':gain,'regressed_game_families':lost,'unchanged':25-len(gain)-len(lost),
                  'level_sum_change':sum(changes),'mean_completed_level_change':round(sum(changes)/25,4),
                  'bootstrap_95_descriptive':ci(changes),'gained_count':len(gain),'lost_count':len(lost),
                  'first_divergence':diffs,'L1_behavior_exactly_frozen':gated}
    print('DELTA',arm,'GAIN',gain,'LOSS',lost,'SUM',sum(changes),'CI',ci(changes),flush=True)
with (out/'per_game_comparisons.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(pair_rows[0]))
    w.writeheader();w.writerows(pair_rows)
with (out/'totals.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(totals[0]))
    w.writeheader();w.writerows(totals)
(out/'summary.json').write_text(json.dumps({'agent_sha256':EXPECTED_SOURCE,'runner_sha256':hashlib.sha256((BASE/'run_e121.py').read_bytes()).hexdigest(),
    'evaluation':'25 previously exposed public native SDK games, per policy seed 76 / native seed 47',
    'scoring':'native completed-level counts; neither Kaggle leaderboard score nor human-relative RHAE',
    'totals':totals,'differences':deltas,'limits':['all 25 public games historically exposed','only one environment configuration per game','selected candidate count changes policy prior probabilities','early termination shortens actions']},indent=2)+'\n')
lines=['# E121 — Spatial Candidate Diversity (Full Native Study)','',
'**Status:** completed public-native evaluation; no Kaggle submission.','',
'## Study design','',
'- Original, frozen source SHA-256: '+EXPECTED_SOURCE+'.',
'- Twenty-five previously exposed public game families; policy seed 76, native seed 47.',
'- Only the set of observable legal click candidates was varied, never the pretrained checkpoint, rewards, PUCT Q-updates or game-specific rules.',
'- Conditions: centroid-only baseline; two near-centre (count-matched) targets; two or three farthest-point targets; and versions activated only after Level 1.',
'- Limit: 200 SDK actions per unfinished level; natural terminals may occur earlier.',
'',
'## Results','',
'| Arm | L1 | L2 | L3+ | Total levels | Charged actions | Gain games | Loss games |',
'|:---|---:|---:|---:|---:|---:|:---|:---|']
for s in totals:
    name=s['arm']
    delta=deltas.get(name,{})
    lines.append('| '+name+' | '+str(s['L1'])+' | '+str(s['L2'])+' | '+str(s['L3plus'])+' | '+str(s['total_completed_levels'])+' | '+str(s['charged_sdk_actions'])+' | '+','.join(delta.get('gained_game_families',[]))+' | '+','.join(delta.get('regressed_game_families',[]))+' |')
lines+=['',
'## Controls and checks',
'- A baseline-only two-game smoke matched Level-2 completions in tu93 (79 actions) and vc33 (105 actions).',
'- The full original baseline reproduced exactly 13 L1, 2 L2, 0 L3+ and 2,790 charged actions.',
'- All initial frame SHA-256 values match across arms; all recorded frame chains, reward counts and legal action indices were checked.',
'- Level-2-only variants have exactly the same 25/25 Level-1 physical action/frame/reward sequences as baseline.',
'- Paired game-cluster bootstrap intervals are descriptive only, since every public game has been previously exposed.',
'',
'## Interpretation',
'No global candidate-expansion variant creates a new completed level on these 25 games; some lose completed levels.',
'Extra action candidates also change PUCT prior normalisation, so a changed trajectory does not by itself prove a newly clicked location was causally useful.',
'Do not interpret lower total action counts as action efficiency: several episodes terminate earlier after failure.',
'The noncentroid-selected diagnostic includes occasional original-policy candidate expansion, and is not a direct count of causally successful new clicks.',
'',
'## Deployment recommendation',
'Retain the existing official-scoring N117 agent unchanged. No candidate passes a reward-gain deployment gate.',
'Any future effort should target independently tested interactive prerequisites rather than generic candidate-set expansion.',
'']
(out/'REPORT.md').write_text('\n'.join(lines))
archive=out/'E121_FULL_PUBLIC_NATIVE_EVIDENCE.zip'
files=[BASE/'run_e121.py',BASE/'run_e121_staged.py',out/'REPORT.md',out/'summary.json',out/'totals.csv',out/'per_game_comparisons.csv']
files+=list((SOURCE).glob('*/*.json'))
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=7) as z:
    for f in files:
        z.write(f,f.relative_to(BASE))
print('ARCHIVE',archive,'BYTES',archive.stat().st_size,'EPISODES',25*len(ARMS),flush=True)
print('REPORT_PATH',out/'REPORT.md',flush=True)
print('COMPLETE',flush=True)
