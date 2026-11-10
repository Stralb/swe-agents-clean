#!/usr/bin/env python3
"""Audit all E122/E123 native episodes; never access Kaggle or hidden game internals."""
import collections,csv,hashlib,json,zipfile
from pathlib import Path
ROOT=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs')
HERE=ROOT/'e122_e123_joint_audit_20261026'
E122=ROOT/'click_feedback_e122_20261026'
E123=ROOT/'teammate_prior_e123_20261026'
OUT=HERE/'analysis'
OUT.mkdir(parents=True,exist_ok=True)
SOURCE_SHA='0663845070e47a053076db54243c3445921a06b4bf0908b7b233c263da423bfa'
PEER_SHA='c5882f664b082aa131023ac1ffaebeb771ba7fe181fa909730fe1c641e5978b9'
SOURCE=ROOT/'n117_kaggle_20261026_dataset1/private_dataset/my_agent.py'
CKPT=Path('/home-mscluster/astrauss/RL-ARC-AGI-3-Project/assets/dqn_v1/checkpoints/E-onehotcnn__T-stack2__A-vector__U-effect__f0__s11.pt')
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SOURCE_SHA
assert hashlib.sha256(CKPT.read_bytes()).hexdigest()==PEER_SHA
specs=[
('E122',E122/'results',76,['baseline','feedback_rescue_all','feedback_rescue_l2','local_credit_l2','rescue_credit_l2']),
('E122',E122/'results',77,['baseline','feedback_rescue_l2','local_credit_l2','rescue_credit_l2']),
('E122',E122/'results',78,['baseline','feedback_rescue_l2','local_credit_l2','rescue_credit_l2']),
('E123_L2',E123/'results',76,['baseline','peer_salience','peer_random','peer_trained','peer_gated','peer_trained_salience']),
('E123_L1',E123/'level1',76,['baseline','l1_d14_salience','l1_random_prior','l1_trained_prior']),
('E123_adaptive',E123/'adaptive',76,['baseline','adaptive_trained','adaptive_random']),
]
table=[];pairs=[];bygame=[];runs={};json_files=[]
total_actions=0;total_episodes=0
for family,folder,seed,arms in specs:
    group={}
    for arm in arms:
        path=folder/('seed'+str(seed))/arm
        assert path.is_dir(),path
        files=sorted(x for x in path.glob('*.json') if x.name!='summary.json')
        assert len(files)==25,(family,seed,arm,len(files))
        games={}
        for f in files:
            obj=json.loads(f.read_text())
            assert 'fatal' not in obj,(f,obj.get('message'))
            s=obj['summary'];t=obj['trajectory']
            assert s['source_sha256']==SOURCE_SHA and s['policy_seed']==seed and s['native_seed']==47
            assert len(t)==s['charged_sdk_actions']
            assert sum(int(x['reward']) for x in t)==s['levels_completed']
            assert all(0<=int(x['a'])<4102 for x in t)
            assert all(t[i]['post']==t[i+1]['pre'] for i in range(len(t)-1))
            games[s['family']]=obj
            total_actions+=len(t);total_episodes+=1;json_files.append(f)
        assert len(games)==25
        group[arm]=games
        ss=[o['summary'] for o in games.values()]
        totals={'experiment':family,'seed':seed,'arm':arm,'games':25,
                'L1':sum(s['l1'] for s in ss),'L2':sum(s['l2'] for s in ss),
                'L3plus':sum(s['l3plus'] for s in ss),
                'total_levels':sum(s['levels_completed'] for s in ss),
                'SDK_actions':sum(s['charged_sdk_actions'] for s in ss)}
        table.append(totals)
        print('ARM',json.dumps(totals,sort_keys=True),flush=True)
    bb=group['baseline']
    for arm,vv in group.items():
        if arm=='baseline':continue
        assert set(vv)==set(bb)
        gains=[];losses=[];changed=0
        for game in sorted(bb):
            old=bb[game];new=vv[game]
            b=old['summary'];v=new['summary']
            assert b['initial_frame_sha']==v['initial_frame_sha']
            diff=int(v['levels_completed'])-int(b['levels_completed'])
            if diff>0:gains.append(game)
            if diff<0:losses.append(game)
            left=[(x['a'],x['pre'],x['post'],x['reward']) for x in old['trajectory']]
            right=[(x['a'],x['pre'],x['post'],x['reward']) for x in new['trajectory']]
            isdifferent=left!=right
            changed+=int(isdifferent)
            if family=='E122' and arm in ('feedback_rescue_l2','local_credit_l2','rescue_credit_l2'):
                left1=[(x['a'],x['pre'],x['post'],x['reward']) for x in old['trajectory'] if x['level']==1]
                right1=[(x['a'],x['pre'],x['post'],x['reward']) for x in new['trajectory'] if x['level']==1]
                assert left1==right1,(family,seed,arm,game,'First-level mutation')
            bygame.append({'experiment':family,'seed':seed,'arm':arm,'game':game,
                'baseline_levels':b['levels_completed'],'variant_levels':v['levels_completed'],'delta':diff,
                'baseline_actions':b['charged_sdk_actions'],'variant_actions':v['charged_sdk_actions'],
                'changed_trajectory':int(isdifferent)})
        pair={'experiment':family,'seed':seed,'arm':arm,'gained_games':','.join(gains),'lost_games':','.join(losses),
            'n_gained':len(gains),'n_lost':len(losses),'n_trajectory_changed':changed}
        pairs.append(pair)
        print('PAIR',json.dumps(pair,sort_keys=True),flush=True)
    runs[(family,seed)]=group
assert total_episodes==sum(25*len(arms) for _,_,_,arms in specs)
baseE122=runs[('E122',76)]['baseline']
for family in ('E123_L2','E123_L1','E123_adaptive'):
    for game in baseE122:
        a=[(x['a'],x['pre'],x['post'],x['reward']) for x in baseE122[game]['trajectory']]
        b=[(x['a'],x['pre'],x['post'],x['reward']) for x in runs[(family,76)]['baseline'][game]['trajectory']]
        assert a==b,(family,game,'N117 not reproduced')
for family in ('E122','E123_L2','E123_L1','E123_adaptive'):
    r=next(r for r in table if r['experiment']==family and r['seed']==76 and r['arm']=='baseline')
    assert (r['L1'],r['L2'],r['total_levels'],r['SDK_actions'])==(13,2,15,2790)
oracle=max
peer=runs[('E123_L1',76)]['l1_trained_prior']
unionL1=sum(max(peer[g]['summary']['l1'],baseE122[g]['summary']['l1']) for g in baseE122)
unionL2=sum(max(peer[g]['summary']['l2'],baseE122[g]['summary']['l2']) for g in baseE122)
def csvsave(name,rows):
    with (OUT/name).open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)
csvsave('all_arms.csv',table)
csvsave('paired.csv',pairs)
csvsave('per_game.csv',bygame)
report={
    'frozen_N117_sha256':SOURCE_SHA,'teammate_effect_checkpoint_sha256':PEER_SHA,
    'native_seed':47,'public_games':25,'max_actions_per_unfinished_level':200,
    'source_runs_checked':total_episodes,'charged_actions_checked':total_actions,
    'official_kaggle_submissions':0,'official_kaggle_score_this_study':None,
    'arms':table,'comparisons':pairs,'oracle_union_of_separately_run_policies':{'L1':unionL1,'L2':unionL2},
    'limitations':['All 25 public game families were exposed during development.',
       'The oracle is a hindsight selector, not a deployable policy.',
       'A frame change is not native reward or goal progress.',
       'Fewer actions may reflect earlier failure rather than efficiency.',
       'The teammate trained checkpoint has not independently been scored on Kaggle here.',
       'N117 original source and both trained checkpoints remained unchanged.']
}
(OUT/'RESULTS.json').write_text(json.dumps(report,indent=2)+'\n')
lines=['# E122/E123: Reinforced Clicks and Teammate Model Transfer','',
    'Status: both native-SDK study grids completed. No Kaggle submission made.',
    'Frozen N117 SHA-256: '+SOURCE_SHA,
    'Teammate pretrained checkpoint SHA-256: '+PEER_SHA,'',
    '## Protocol','',
    '25 historically exposed public games, native seed 47, 200 scorer-counted actions maximum per unfinished level.',
    'Policy seed 76 for every main arm, and 77-78 for E122 robustness. Outcomes below are native',
    'level completions, not leaderboard scores.','',
    '## All native results','',
    '| Study | Seed | Variant | L1 | L2 | L3+ | Total levels | Actions |',
    '|---|---:|---|---:|---:|---:|---:|---:|']
for a in table:
    lines.append('| {experiment} | {seed} | {arm} | {L1} | {L2} | {L3plus} | {total_levels} | {SDK_actions} |'.format(**a))
lines+=['','## Paired game improvements and regressions','',
        '| Study | Seed | Variant | Gained families | Lost families | Changed trajectories |',
        '|---|---:|---|---|---|---:|']
for a in pairs:
    lines.append('| {} | {} | {} | {} | {} | {} |'.format(a['experiment'],a['seed'],a['arm'],
        a['gained_games'] or 'none',a['lost_games'] or 'none',a['n_trajectory_changed']))
lines+=['','## Interpretation and decisions','',
        '- The freeze-consistent N117 baseline reproduces 13 Level-1, 2 Level-2, 0 Level-3+ wins on 25 games.',
        '- The teammate effect prior can create a new win, but simultaneous losses prevent a valid net deployment gain.',
        '- The hindsight oracle union of N117 and the pretrained first-level prior has L1='+str(unionL1)+
           ' and L2='+str(unionL2)+', but this is not a deployable policy and must never be described as one.',
        '- The gated pretrained prior is evaluated against an identically gated random-weight control.',
        '- These are public development-game results. No unseen-game generalization is established.',
        '- Do not replace N117, which earned the previously reported 0.33 Kaggle score.','',
        '## Reproducibility and validation','',
        '- '+str(total_episodes)+' episode records parsed and '+str(total_actions)+' scorer-counted SDK actions validated.',
        '- Unbroken frame-hash chains, legal action index bounds, and consistency of recorded native level rewards were checked.',
        '- Frozen seed-76 baseline action/frame/reward traces match exactly between E122 and all three E123 protocols.',
        '- E122 Level-2-only variants preserve Level-1 action/frame/reward trajectories across every matched game and policy seed.',
        '- Running the scripts requires the official public SDK, the original frozen N117 agent, and the separate teammate checkpoint.','']
(OUT/'REPORT.md').write_text('\n'.join(lines))
sources=[E122/'run_e122.py',E123/'run_e123_v2.py',E123/'run_e123_l1_v2.py',
         E123/'run_e123_adaptive.py',HERE/'analyze.py',OUT/'REPORT.md',OUT/'RESULTS.json',
         OUT/'all_arms.csv',OUT/'paired.csv',OUT/'per_game.csv']
archive=OUT/'E122_E123_COMPLETE_EVIDENCE.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for f in sources+json_files:
        assert f.is_file(),f
        z.write(f,str(f.relative_to(ROOT)))
print('EVIDENCE_ARCHIVE',archive,'BYTES',archive.stat().st_size,
    'SHA256',hashlib.sha256(archive.read_bytes()).hexdigest(),flush=True)
print('VERIFIED_EPISODES',total_episodes,'VERIFIED_ACTIONS',total_actions,'ORACLE',unionL1,unionL2,flush=True)
print('AUDIT_COMPLETE',flush=True)
