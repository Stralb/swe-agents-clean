#!/usr/bin/env python3
"""Additional E123 three-seed evidence audit and full 850-trace research archive.
All source files are immutable and no Kaggle operations are performed.
"""
import csv,hashlib,json,zipfile
from pathlib import Path
ROOT=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs')
E=ROOT/'teammate_prior_e123_20261026'
P=ROOT/'e122_e123_joint_audit_20261026/analysis'
PREV=P/'E122_E123_COMPLETE_EVIDENCE.zip'
SRC_SHA='0663845070e47a053076db54243c3445921a06b4bf0908b7b233c263da423bfa'
CHECKPOINT_SHA='c5882f664b082aa131023ac1ffaebeb771ba7fe181fa909730fe1c641e5978b9'
assert PREV.stat().st_size==3864925
assert hashlib.sha256(PREV.read_bytes()).hexdigest()=='45adeb3196b05eeb93a13fc487a72442a643df1b97b2874c6fba4e87d33dc5e5'
selected=('baseline','l1_d14_salience','l1_random_prior','l1_trained_prior')
all_extra_files=[];pairs=[];totals=[];total_episodes=0;total_actions=0
for seed in (77,78):
    group={}
    for arm in selected:
        folder=E/'level1'/('seed'+str(seed))/arm
        files=sorted(x for x in folder.glob('*.json') if x.name!='summary.json')
        assert len(files)==25,(seed,arm,len(files))
        got={}
        for f in files:
            obj=json.loads(f.read_text())
            assert 'fatal' not in obj,(seed,arm,f)
            s=obj['summary'];t=obj['trajectory']
            assert s['source_sha256']==SRC_SHA and s['policy_seed']==seed and s['native_seed']==47
            assert len(t)==s['charged_sdk_actions']
            assert sum(x['reward'] for x in t)==s['levels_completed']
            assert all(0<=x['a']<4102 for x in t)
            assert all(t[i]['post']==t[i+1]['pre'] for i in range(len(t)-1))
            total_episodes+=1;total_actions+=len(t)
            got[s['family']]=obj
            all_extra_files.append(f)
        group[arm]=got
        ss=[ob['summary'] for ob in got.values()]
        summary={'seed':seed,'arm':arm,'L1':sum(s['l1'] for s in ss),'L2':sum(s['l2'] for s in ss),
            'L3plus':sum(s['l3plus'] for s in ss),
            'completed_levels':sum(s['levels_completed'] for s in ss),
            'charged_actions':sum(s['charged_sdk_actions'] for s in ss)}
        totals.append(summary)
        print('EXTRA_ARM',json.dumps(summary,sort_keys=True),flush=True)
    for arm in selected[1:]:
        gained=[];lost=[];changed=[]
        for game in sorted(group['baseline']):
            bb=group['baseline'][game];vv=group[arm][game]
            assert bb['summary']['initial_frame_sha']==vv['summary']['initial_frame_sha']
            bd=bb['summary']['levels_completed']
            vd=vv['summary']['levels_completed']
            if vd>bd:gained.append(game)
            if vd<bd:lost.append(game)
            a=[(x['a'],x['pre'],x['post'],x['reward']) for x in bb['trajectory']]
            b=[(x['a'],x['pre'],x['post'],x['reward']) for x in vv['trajectory']]
            if a!=b:changed.append(game)
        row={'seed':seed,'arm':arm,'gains':','.join(gained),'losses':','.join(lost),
            'n_gains':len(gained),'n_losses':len(lost),'changed_trajectories':len(changed)}
        pairs.append(row)
        print('EXTRA_PAIR',json.dumps(row,sort_keys=True),flush=True)
assert total_episodes==200 and len(all_extra_files)==200
def save(name,records):
    with (P/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]))
        w.writeheader();w.writerows(records)
save('E123_seed77_78_arms.csv',totals)
save('E123_seed77_78_pairs.csv',pairs)
text='''# E123 three-seed validation: key result

The E123 first-level salience and pretrained model prior were retested at policy seeds 77 and 78.
Both use the same native seed 47 and the same 25 historically exposed public games.
No game-specific source or identifiers are supplied to policy selection.

The pretrained prior produces a new s5i5 Level-1 completion at all 3 policy seeds,
but it loses other game completions and reduces the local SDK mean across every seed.

D14 salience gave a small positive local SDK mean on seeds 76 and 78, but on
seed 77 it lost dc22 and produced a worse aggregate score. It is not robust
enough to promote.

A conservative prior correction, intervening only when N117's ranking is
almost tied and the pretrained model expresses a large click preference,
was additionally smoke-tested on four representative games. It made no
changes with pretrained weights and produced no new success. The
same gate with random weights caused a regression in lf52; stop scaling it.

For the official local SDK mean scores and per-game score decomposition,
see local_sdk_score_means.csv, local_sdk_score_per_game.csv,
and local_sdk_score_deltas.csv.
These are 0-100 public native SDK scores, not Kaggle leaderboard results.

The original 0.33 Kaggle-scoring N117 source and its checkpoint were kept intact.
'''
(P/'E123_THREE_SEED_VERDICT.md').write_text(text)
all_added=[P/'E123_seed77_78_arms.csv',P/'E123_seed77_78_pairs.csv',
    P/'E123_THREE_SEED_VERDICT.md',P/'local_sdk_score_means.csv',
    P/'local_sdk_score_per_game.csv',P/'local_sdk_score_deltas.csv',P/'paired_win_times.csv',
    E/'run_e123_conservative.py']
zipfile_path=P/'E122_E123_EXTENDED_850_EPISODES.zip'
with zipfile.ZipFile(zipfile_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as out:
    # The original 650-episode source/trace archive stays intact as an entry.
    out.write(PREV,'E122_E123_ORIGINAL_650.zip')
    for f in all_added:
        assert f.is_file(),f
        out.write(f,str(f.relative_to(ROOT)))
    for f in all_extra_files:
        out.write(f,str(f.relative_to(ROOT)))
print('EXTENDED_850_ARCHIVE',zipfile_path,'BYTES',zipfile_path.stat().st_size,
    'SHA256',hashlib.sha256(zipfile_path.read_bytes()).hexdigest(),flush=True)
print('E123_EXTENSION_VERIFIED_200_EPISODES',total_actions,'ACTION_RECORDS',flush=True)
