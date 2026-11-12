#!/usr/bin/env python3
"""E121 supplemental seed audit and full evidence packaging. Non-acting, read-only analyses."""
from __future__ import annotations
import csv,hashlib,json,zipfile
from pathlib import Path
B=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026')
A=B/'analysis'
A.mkdir(exist_ok=True)
SOURCE_SHA='0663845070e47a053076db54243c3445921a06b4bf0908b7b233c263da423bfa'
SEEDS=(76,77,78)
arms=('baseline','l2_diverse2')
summaries=[]
per_game=[]
for seed in SEEDS:
    arm_data={}
    for arm in arms:
        directory=(B/'results'/arm) if seed==76 else (B/'seed_checks'/('seed'+str(seed))/arm)
        files=sorted(x for x in directory.glob('*.json') if x.name!='summary.json')
        assert len(files)==25,(seed,arm,len(files))
        parsed={}
        for f in files:
            ob=json.loads(f.read_text())
            assert 'fatal' not in ob
            s=ob['summary'];t=ob['trajectory']
            assert s['policy_seed']==seed and s['native_seed']==47,(seed,arm,f.name,s['policy_seed'])
            assert s['source_sha256']==SOURCE_SHA
            assert len(t)==s['charged_sdk_actions']
            assert sum(x['reward'] for x in t)==s['levels_completed']
            assert all(0<=x['a']<4102 for x in t)
            assert all(t[i-1]['post']==t[i]['pre'] for i in range(1,len(t)))
            parsed[s['family']]=ob
        assert len(parsed)==25
        arm_data[arm]=parsed
        totals={'seed':seed,'arm':arm,'games':25,'L1':sum(x['summary']['l1'] for x in parsed.values()),
          'L2':sum(x['summary']['l2'] for x in parsed.values()),
          'L3plus':sum(x['summary']['l3plus'] for x in parsed.values()),
          'completed_levels':sum(x['summary']['levels_completed'] for x in parsed.values()),
          'sdk_actions':sum(x['summary']['charged_sdk_actions'] for x in parsed.values())}
        summaries.append(totals)
        print('SEED_ARM',json.dumps(totals),flush=True)
    assert set(arm_data[arms[0]])==set(arm_data[arms[1]])
    gains=[];losses=[];changed_paths=[]
    for game in sorted(arm_data[arms[0]]):
        x=arm_data['baseline'][game]
        y=arm_data['l2_diverse2'][game]
        assert x['summary']['initial_frame_sha']==y['summary']['initial_frame_sha']
        tx=[(a['a'],a['pre'],a['post'],a['reward']) for a in x['trajectory'] if a['level']==1]
        ty=[(a['a'],a['pre'],a['post'],a['reward']) for a in y['trajectory'] if a['level']==1]
        assert tx==ty,(seed,game,'Level1 not frozen')
        dx=y['summary']['levels_completed']-x['summary']['levels_completed']
        if dx>0:gains.append(game)
        if dx<0:losses.append(game)
        same=[(a['a'],a['pre'],a['post'],a['reward']) for a in x['trajectory']]==[(a['a'],a['pre'],a['post'],a['reward']) for a in y['trajectory']]
        if not same:changed_paths.append(game)
        per_game.append({'seed':seed,'game':game,'baseline_levels':x['summary']['levels_completed'],
          'l2_diverse2_levels':y['summary']['levels_completed'],'level_difference':dx,
          'baseline_actions':x['summary']['charged_sdk_actions'],
          'l2_diverse2_actions':y['summary']['charged_sdk_actions'],
          'L1_exact_sequence':True,'whole_trajectory_same':same})
    print('SEED_DIFFERENCES',seed,'GAIN',gains,'LOSS',losses,
          'CHANGED_PHYSICAL_TRAJECTORIES',changed_paths,flush=True)
    assert not gains and not losses,(seed,gains,losses)
with (A/'seed_robustness.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(summaries[0]));w.writeheader();w.writerows(summaries)
with (A/'seed_per_game.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(per_game[0]));w.writeheader();w.writerows(per_game)
(A/'seed_robustness.json').write_text(json.dumps({'seeds':list(SEEDS),'arms':list(arms),'summaries':summaries,
   'per_game':per_game,'policy_source_sha256':SOURCE_SHA,'gains_across_75_paired_seed_games':0,
   'note':'These are three policy-seed replicates on the same 25 historically exposed public families, NOT 75 independent environments.'},indent=2)+'\n')
main=(A/'REPORT.md').read_text()
main+='\n## Additional policy-seed robustness (three policy seeds, same 25 public games)\n\n'
main+='| Seed | Original L1 | Original L2 | Level-2-only diverse L1 | Level-2-only diverse L2 | New rewarding games |\n'
main+='|---:|---:|---:|---:|---:|---:|\n'
for seed in SEEDS:
    bb=next(x for x in summaries if x['seed']==seed and x['arm']=='baseline')
    cc=next(x for x in summaries if x['seed']==seed and x['arm']=='l2_diverse2')
    main+=f"| {seed} | {bb['L1']} | {bb['L2']} | {cc['L1']} | {cc['L2']} | 0 |\n"
main+='\nLevel-1 actions, frame hashes and native rewards are exactly unchanged in every matched family/seed pair (75/75).'
main+=' These repeated policy seeds do not create independent game configurations. The best candidate does not improve any level-completion outcome.\n'
main+='\n## Final decision\n\n**Do not promote any E121 candidate to Kaggle.** Retain the N117 0.33 official submission unmodified.\n'
(A/'REPORT_COMPLETE.md').write_text(main)
original_results=[x for x in (B/'results').glob('*/*.json') if x.is_file()]
seed_results=[x for x in (B/'seed_checks').glob('seed*/*/*.json') if x.is_file()]
assert len([x for x in original_results if x.name!='summary.json'])==175
assert len([x for x in seed_results if x.name!='summary.json'])==100
files=[B/'run_e121.py',B/'run_e121_staged.py',B/'runtime_bootstrap.py',B/'analyze_e121_v2.py',
       B/'analyze_seeds.py',A/'REPORT_COMPLETE.md',A/'seed_robustness.json',A/'seed_robustness.csv',
       A/'seed_per_game.csv',A/'summary.json',A/'totals.csv',A/'per_game_comparisons.csv']
files+=original_results+seed_results
out=A/'E121_COMPLETE_EVIDENCE_WITH_SEEDS.zip'
with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=7) as z:
  for path in files:
    assert path.is_file(),path
    z.write(path,arcname=str(path.relative_to(B)))
print('EVIDENCE_ARCHIVE',out,'BYTES',out.stat().st_size,'FILES',len(files),
  'EPISODES',275,'ZIP_SHA256',hashlib.sha256(out.read_bytes()).hexdigest(),flush=True)
print('E121_SEED_AUDIT_COMPLETE',flush=True)
