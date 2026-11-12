#!/bin/bash
#SBATCH --job-name=e127-native-trace-audit
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:09:00
set -euo pipefail
umask 077
python3 - <<'PY'
from pathlib import Path
from zipfile import ZipFile
from collections import defaultdict
import csv,hashlib,io,json
ROOT=Path('/home-mscluster/astrauss/research_artifacts')
SRC=ROOT/'mcp_uploads/jobs/click_integrated_audit_e127_20261026/analysis/E124_E125_E126_FULL_NATIVE_EVIDENCE.zip'
OUT=ROOT/'mcp_uploads/jobs/rl_e127_mechanism_audit_20261027/analysis'
OUT.mkdir(parents=True,exist_ok=True)
arms=('baseline','contingency_only','hybrid_trained','hybrid_random','hybrid_salience')
seeds=(76,77,78)
with ZipFile(SRC) as z:
    lookup={}
    for n in z.namelist():
        if n.startswith('click_hybrid_e126_20261026/results/') and n.endswith('.json'):
            parts=n.split('/')
            if len(parts)==5 and parts[3] in arms and parts[2].startswith('seed'):
                lookup[(int(parts[2][4:]),parts[3],parts[4][:-5])]=n
    raw=z.read('click_integrated_audit_e127_20261026/analysis/per_game.csv').decode('utf-8')
    scored={(int(r['seed']),r['arm'],r['game']):r for r in csv.DictReader(io.StringIO(raw)) if r['family']=='E126'}
    print('SOURCE_ZIP_BYTES',SRC.stat().st_size,'E126_TRACES',len(lookup),'SOURCE_HASH',hashlib.sha256(SRC.read_bytes()).hexdigest(),flush=True)
    episodes={}; rows=[]
    for key,n in sorted(lookup.items()):
        seed,arm,game=key
        d=json.loads(z.read(n));tr=d['trajectory'];summary=d['summary']
        q=scored.get(key)
        assert q is not None and len(tr)==int(q['actions']) and int(summary['levels_completed'])==int(q['completed_levels'])
        zero=sum(int(x['pixels_changed'])==0 for x in tr)
        micro=sum(1<=int(x['pixels_changed'])<=3 for x in tr)
        large=sum(int(x['pixels_changed'])>=4 for x in tr)
        rewards=sum(float(x['reward'])>0 for x in tr)
        positive_effect_no_reward=sum(int(x['pixels_changed'])>0 and float(x['reward'])<=0 for x in tr)
        repeat=sum(tr[i]['a']==tr[i-1]['a'] for i in range(1,len(tr)))
        first=next((x['step'] for x in tr if float(x['reward'])>0),None)
        rows.append(dict(seed=seed,arm=arm,game=game,actions=len(tr),levels=int(summary['levels_completed']),
             score=float(q['sdk_score_0_100']),zero_pixels=zero,micro_pixels=micro,at_least_4_pixels=large,
             visible_no_immediate_reward=positive_effect_no_reward,reward_events=rewards,
             repeats=repeat,unique_actions=len({x['a'] for x in tr}),
             clicked_actions=int(summary.get('clicks_selected') or 0),
             new_candidate_actions=sum(bool(x.get('chosen_extra')) for x in tr),
             first_native_reward_action=first if first is not None else ''))
        episodes[key]=tr
    assert len(rows)==375 and len(scored)>=375
    def write_csv(path,rs):
        with path.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rs[0]))
            w.writeheader();w.writerows(rs)
    write_csv(OUT/'per_episode_effects.csv',rows)
    bykey={(x['seed'],x['arm'],x['game']):x for x in rows}
    pairs=[]
    for seed in seeds:
      for game in sorted({k[2] for k in episodes}):
        b=episodes[(seed,'baseline',game)]
        for arm in arms[1:]:
            a=episodes[(seed,arm,game)]
            head_same=bool(a and b and a[0]['pre']==b[0]['pre'])
            divergence='identical'
            firstdiv=None
            prefix=0
            for idx in range(min(len(a),len(b))):
                x,y=a[idx],b[idx]
                if x['pre']!=y['pre']:
                    divergence='different_pre_observation';firstdiv=idx+1;break
                if x['a']!=y['a']:
                    divergence='same_observation_different_action';firstdiv=idx+1;break
                if x['post']!=y['post'] or x['reward']!=y['reward']:
                    divergence='same_action_different_observed_outcome';firstdiv=idx+1;break
                prefix+=1
            if firstdiv is None and len(a)!=len(b):
                divergence='one_trajectory_ended';firstdiv=prefix+1
            ba=bykey[(seed,'baseline',game)];va=bykey[(seed,arm,game)]
            pairs.append(dict(seed=seed,arm=arm,game=game,start_same=int(head_same),
                 divergence_kind=divergence,common_prefix_actions=prefix,first_divergence_action=firstdiv or '',
                 score_delta=round(va['score']-ba['score'],9),
                 level_delta=va['levels']-ba['levels'],
                 effect_event_delta=(va['micro_pixels']+va['at_least_4_pixels'])-(ba['micro_pixels']+ba['at_least_4_pixels']),
                 reward_event_delta=va['reward_events']-ba['reward_events']))
    assert len(pairs)==300
    write_csv(OUT/'paired_trace_branches.csv',pairs)
    grouped=[]
    for seed in seeds:
      for arm in arms:
        r=[x for x in rows if x['seed']==seed and x['arm']==arm]
        z=[x for x in pairs if x['seed']==seed and x['arm']==arm]
        grouped.append(dict(seed=seed,arm=arm,game_families=len(r),episodes_changed=sum(x['divergence_kind']!='identical' for x in z) if z else 0,
             shared_state_action_divergences=sum(x['divergence_kind']=='same_observation_different_action' for x in z) if z else 0,
             improved_score_families=sum(x['score_delta']>1e-10 for x in z) if z else 0,
             regressed_score_families=sum(x['score_delta']< -1e-10 for x in z) if z else 0,
             observed_actions=sum(x['actions'] for x in r),zero_pixel_actions=sum(x['zero_pixels'] for x in r),
             micro_1_to_3_actions=sum(x['micro_pixels'] for x in r),
             at_least_4_pixel_actions=sum(x['at_least_4_pixels'] for x in r),
             visible_no_immediate_reward=sum(x['visible_no_immediate_reward'] for x in r),
             reward_events=sum(x['reward_events'] for x in r),
             completed_levels=sum(x['levels'] for x in r),
             mean_sdk=round(sum(x['score'] for x in r)/25,9)))
    write_csv(OUT/'grouped_trace_summary.csv',grouped)
    selected=[]
    for seed in seeds:
      for game in ('s5i5','lf52'):
        for arm in ('baseline','contingency_only','hybrid_trained'):
          tr=episodes[(seed,arm,game)]
          for x in tr:
            selected.append(dict(seed=seed,game=game,arm=arm,step=x['step'],level=x['level'],
                 action_id=x['a'],pixels_changed=x['pixels_changed'],native_reward=x['reward'],
                 first8_pre_hash=x['pre'][:8],first8_post_hash=x['post'][:8]))
    write_csv(OUT/'selected_effect_traces.csv',selected)
    print('GROUP_SUMMARY_START')
    with (OUT/'grouped_trace_summary.csv').open() as f: print(f.read(),flush=True)
    print('PAIRED_CHANGED_DIVERGENCE_TYPES')
    from collections import Counter
    for arm in arms[1:]:
      zz=[x for x in pairs if x['arm']==arm]
      print(arm,dict(Counter(x['divergence_kind'] for x in zz)),flush=True)
    print('SELECTED_PAIRS')
    for x in pairs:
      if x['game'] in ('s5i5','lf52') and x['arm'] in ('hybrid_trained','hybrid_random'):
        print(x,flush=True)
print('READONLY_NATIVE_TRACE_ANALYSIS_COMPLETE')
PY