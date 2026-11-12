#!/usr/bin/env python3
"""E124-E126 audit of native-SDK public episodes and distribution-safe provenance.
No Kaggle submissions. Zero game engine internals passed to agents.
"""
import csv,hashlib,json,random,zipfile
from pathlib import Path

ROOT=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs')
ME=ROOT/'click_integrated_audit_e127_20261026'
OUT=ME/'analysis'
OUT.mkdir(parents=True,exist_ok=True)
E121=ROOT/'click_diversity_e121_20261026'
E124=ROOT/'click_breakthrough_e124_20261026'
E125=ROOT/'sparse_click_transfer_e125_20261026'
E126=ROOT/'click_hybrid_e126_20261026'
SOURCE=ROOT/'n117_kaggle_20261026_dataset1/private_dataset/my_agent.py'
SRC_SHA='0663845070e47a053076db54243c3445921a06b4bf0908b7b233c263da423bfa'
PEER=Path('/home-mscluster/astrauss/RL-ARC-AGI-3-Project/assets/dqn_v1/checkpoints/E-onehotcnn__T-stack2__A-vector__U-effect__f0__s11.pt')
PEER_SHA='c5882f664b082aa131023ac1ffaebeb771ba7fe181fa909730fe1c641e5978b9'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SRC_SHA
assert hashlib.sha256(PEER.read_bytes()).hexdigest()==PEER_SHA
GAME_META=E121/'runtime/environment_files'
meta={x.name:json.loads(next(x.glob('*/metadata.json')).read_text()) for x in GAME_META.iterdir() if x.is_dir()}
games=sorted(meta)
assert len(games)==25
runs=[
('E124',E124/'results',76,['baseline','prune_bg','prune_broad','contingency','selection_chain']),
('E124',E124/'results',77,['baseline','contingency']),
('E124',E124/'results',78,['baseline','contingency']),
('E124_ablation',E124/'ablation',76,['contingency','rarity_only','effect_only','random_bonus']),
('E124_ablation',E124/'ablation',77,['rarity_only','effect_only']),
('E124_ablation',E124/'ablation',78,['rarity_only','effect_only']),
('E125',E125/'results',76,['baseline','sparse80_trained','sparse80_random','sparse80_salience','sparse70_trained']),
('E125',E125/'results',77,['baseline','sparse80_trained','sparse80_random','sparse80_salience']),
('E125',E125/'results',78,['baseline','sparse80_trained','sparse80_random','sparse80_salience']),
('E126',E126/'results',76,['baseline','contingency_only','hybrid_trained','hybrid_random','hybrid_salience']),
('E126',E126/'results',77,['baseline','contingency_only','hybrid_trained','hybrid_random','hybrid_salience']),
('E126',E126/'results',78,['baseline','contingency_only','hybrid_trained','hybrid_random','hybrid_salience'])
]

def calculate_score(obj,game):
    human=list(map(int,meta[game]['baseline_actions']))
    total=len(human)
    denom=total*(total+1)/2.
    numer=0.
    prev=0
    for i,win in enumerate(obj['summary']['wins'],1):
        j=int(win['level'])
        assert j==i and j<=total
        elapsed=int(win['step'])-prev
        prev=int(win['step'])
        assert elapsed>0
        numer+=j*min(115.,100.*(human[j-1]/elapsed)**2)
    done=int(obj['summary']['levels_completed'])
    cap=sum(range(1,done+1))/denom*100.
    return min(numer/denom,cap)

def write_csv(filename,rows):
    assert rows,filename
    with (OUT/filename).open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

by_arm={}
arm_rows=[]
game_rows=[]
source_files=[]
total_actions=0
total_episodes=0
for family,path,seed,conditions in runs:
    for arm in conditions:
        root=path/('seed'+str(seed))/arm
        files=sorted(x for x in root.glob('*.json') if x.name!='summary.json')
        assert len(files)==25,(family,seed,arm,len(files))
        loaded={}
        for file in files:
            obj=json.loads(file.read_text())
            assert 'fatal' not in obj,(file,obj.get('message'))
            s=obj['summary']
            tr=obj['trajectory']
            assert s['source_sha256']==SRC_SHA
            assert s['policy_seed']==seed and s['native_seed']==47
            assert s['charged_sdk_actions']==len(tr)
            assert sum(int(x['reward']) for x in tr)==s['levels_completed']
            assert all(0<=int(x['a'])<4102 for x in tr)
            assert all(tr[i]['post']==tr[i+1]['pre'] for i in range(len(tr)-1)),file
            assert s['family'] in meta
            assert len(s['initial_frame_sha'])==64
            loaded[s['family']]=obj
            score=calculate_score(obj,s['family'])
            game_rows.append({'family':family,'seed':seed,'arm':arm,'game':s['family'],
                'completed_levels':s['levels_completed'],'actions':len(tr),
                'sdk_score_0_100':round(score,10),'first_win_step':s['wins'][0]['step'] if s['wins'] else ''})
            source_files.append(file)
            total_episodes+=1
            total_actions+=len(tr)
        assert sorted(loaded)==games
        by_arm[(family,seed,arm)]=loaded
        scores=[calculate_score(loaded[g],g) for g in games]
        outcomes=[loaded[g]['summary'] for g in games]
        row={'family':family,'seed':seed,'arm':arm,'games':25,
            'L1':sum(s['l1'] for s in outcomes),'L2':sum(s['l2'] for s in outcomes),
            'L3plus':sum(s['l3plus'] for s in outcomes),
            'completed_levels':sum(s['levels_completed'] for s in outcomes),
            'sdk_actions':sum(s['charged_sdk_actions'] for s in outcomes),
            'mean_sdk_score_0_100':round(sum(scores)/25.,10)}
        arm_rows.append(row)
        print('E127_ARM',json.dumps(row,sort_keys=True),flush=True)

# Cross-protocol frozen N117 baseline: byte-for-byte identical physical trajectories.
for seed in (76,77,78):
    original=by_arm[('E124',seed,'baseline')]
    for study in ('E125','E126'):
        compare=by_arm[(study,seed,'baseline')]
        for g in games:
            a=[(x['a'],x['pre'],x['post'],x['reward']) for x in original[g]['trajectory']]
            b=[(x['a'],x['pre'],x['post'],x['reward']) for x in compare[g]['trajectory']]
            assert a==b,(seed,study,g,'baseline not identical')
    assert sum(original[g]['summary']['levels_completed'] for g in games)==({76:15,77:14,78:15}[seed])

deltas=[]
for study,path,seed,arms in runs:
    baseline=by_arm[('E124',seed,'baseline')] if study=='E124_ablation' else by_arm[(study,seed,'baseline')]
    for arm in arms:
        if arm=='baseline':continue
        current=by_arm[(study,seed,arm)]
        positive=[];negative=[];score_changes=[];changed_traces=0
        for g in games:
            b=baseline[g]
            v=current[g]
            assert b['summary']['initial_frame_sha']==v['summary']['initial_frame_sha']
            leveldiff=v['summary']['levels_completed']-b['summary']['levels_completed']
            if leveldiff>0:positive.append(g)
            if leveldiff<0:negative.append(g)
            dscore=calculate_score(v,g)-calculate_score(b,g)
            if abs(dscore)>1e-8:score_changes.append((g,round(dscore,7)))
            left=[(x['a'],x['pre'],x['post'],x['reward']) for x in b['trajectory']]
            right=[(x['a'],x['pre'],x['post'],x['reward']) for x in v['trajectory']]
            changed_traces+=int(left!=right)
        avg=sum(calculate_score(current[g],g)-calculate_score(baseline[g],g) for g in games)/25.
        row={'family':study,'seed':seed,'arm':arm,
            'gained_games':','.join(positive),'regressed_games':','.join(negative),
            'score_changes':str(score_changes),'changed_trajectories':changed_traces,
            'mean_native_score_change':round(avg,10)}
        deltas.append(row)
        print('E127_DELTA',json.dumps(row,sort_keys=True),flush=True)

# Three-seed checks for trained E125/E126 vs architecture+gate random control.
for seed in (76,77,78):
    e125=by_arm[('E125',seed,'sparse80_trained')]
    e126=by_arm[('E126',seed,'hybrid_trained')]
    original=by_arm[('E126',seed,'baseline')]
    gains=[g for g in games if e126[g]['summary']['levels_completed']>original[g]['summary']['levels_completed']]
    losses=[g for g in games if e126[g]['summary']['levels_completed']<original[g]['summary']['levels_completed']]
    assert 's5i5' in gains and not losses,(seed,gains,losses)
    assert e126['s5i5']['summary']['levels_completed']==1
    assert e125['s5i5']['summary']['levels_completed']==1
    print('E127_HYBRID_GAIN',seed,gains,'LOSSES',losses,
        'S5I5_L1_STEP',e126['s5i5']['summary']['wins'][0]['step'],flush=True)

# Game-cluster bootstrap across unique 25 families, averaging three policy seeds per family.
def bootstrap(study,arm):
    values=[]
    for g in games:
        mean=sum(calculate_score(by_arm[(study,s,arm)][g],g)-
                 calculate_score(by_arm[(study,s,'baseline')][g],g) for s in (76,77,78))/3.
        values.append(mean)
    rng=random.Random(12047)
    reps=sorted(sum(rng.choice(values) for _ in range(25))/25 for _ in range(4000))
    return {'mean':round(sum(values)/25,8),'low':round(reps[99],8),'high':round(reps[3899],8)}
boot_e125=bootstrap('E125','sparse80_trained')
boot_e126=bootstrap('E126','hybrid_trained')
print('E127_GAME_CLUSTER_BOOTSTRAP_E125',boot_e125,flush=True)
print('E127_GAME_CLUSTER_BOOTSTRAP_E126',boot_e126,flush=True)
write_csv('all_arms.csv',arm_rows)
write_csv('per_game.csv',game_rows)
write_csv('paired_changes.csv',deltas)
report={
'agent_source_sha256':SRC_SHA,
'peer_model_sha256':PEER_SHA,
'policy_seeds':[76,77,78],
'public_game_families':25,
'native_env_seed':47,
'episodes_checked':total_episodes,
'sdk_actions_checked':total_actions,
'official_Kaggle_submissions':0,
'mean_score_is_not_Kaggle_score':True,
'e125_descriptive_game_cluster_bootstrap':boot_e125,
'e126_descriptive_game_cluster_bootstrap':boot_e126,
'arms':arm_rows,
'comparisons':deltas,
'limitations':[
 'The 25 public games and their action traces have been repeatedly exposed during research.',
 'The sparse threshold of >=80% modal color was chosen after examining known public game successes.',
 'Three policy seeds on the same environment seed do not constitute 75 independent games.',
 'A single newly completed game can dominate SDK score and the bootstrap interval.',
 'The local native SDK score is not the official hidden Kaggle score.',
 'A frame change or action-effect prediction is not evidence of accomplishing the game goal.',
 'No hidden game state/source, LLM, shadow oracle or privileged planner was used during action selection.'
]}
(OUT/'RESULTS.json').write_text(json.dumps(report,indent=2)+'\n')
md=[
'# E124-E126: Observation-Conditioned Click Exploration',
'',
'**Status:** native-SDK evaluation completed; no Kaggle submission.',
'',
'The native checkpoint and original N117 agent were not modified. SHA256 '+SRC_SHA+'.',
'',
'## Main design',
'',
'**E124:** prune large likely background candidates, replace centroid with an edge point (pilot only), estimate color rarity and empirically local click effects, or follow a click with a primitive action.',
'',
'**E125:** transfer the teammate pretrained CNN effect prior only when ACTION6 is legal, directional keys 1-5 are not legal, and >=80% of the observed 64x64 image has one color. Compare random weights and deterministic visual salience through the identical gate.',
'',
'**E126:** fuse E124 click-contingency outside the gated states with E125 pretrained effect prior in those gated states; compare random-weight and salience-only hybrids.',
'',
'All interventions use only the official observation and legal action interface. N117 Bellman targets and frozen model unchanged.',
'',
'## Three-seed local SDK outcomes',
'',
'| Study | Seed | Arm | L1 | L2 | Total levels | Mean native SDK score (0-100) |',
'|---|---:|---|---:|---:|---:|---:|']
for r in arm_rows:
    md.append('| {family} | {seed} | {arm} | {L1} | {L2} | {completed_levels} | {mean_sdk_score_0_100:.6f} |'.format(**r))
md+=['',
'## Mechanism ablation and validity',
'',
'The E124 rarity-only and effect-only arms both reproduce the single-seed lf52 action-efficiency result. Therefore the result is not uniquely attributable to causal learning; a matched random bonus is an additional control.',
'',
'The E125 pretrained sparse-click transfer produces the missing s5i5 win on 3/3 policy seeds without breaking existing public-game completions. The identically gated random and salience controls do not.',
'',
'The E126 combined policy produces the s5i5 result and can improve other exposed games through E124 ranking. This is a post hoc development result only.',
'',
'Three-seed game-cluster mean score differences are descriptive:',
'',
'- E125 '+str(boot_e125),
'- E126 '+str(boot_e126),
'',
'## Methodological limitations',
'',
'The public games have repeatedly informed model development. The 80% sparse-scene threshold is susceptible to visually identifying the s5i5 family, even without explicit game names. Evidence does not establish generalization to hidden competition games.',
'',
'No Kaggle notebook, agent checkpoint, or official 0.33 submission was modified.',
'',
'See per_game.csv, paired_changes.csv, and RESULTS.json for all scores, regressions, frame-change validation, and provenance.',
'']
(OUT/'REPORT.md').write_text('\n'.join(md))

# Complete remote data archive: exact scripts and all episode traces, not public game source.
sources=[E121/'run_e121.py',
 E124/'run_e124.py',E124/'run_e124_ablation.py',
 E125/'run_e125.py',E126/'run_e126.py',
 ME/'analyze.py',OUT/'REPORT.md',OUT/'RESULTS.json',
 OUT/'all_arms.csv',OUT/'per_game.csv',OUT/'paired_changes.csv']
archive=OUT/'E124_E125_E126_FULL_NATIVE_EVIDENCE.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for f in sources+[SOURCE,PEER]+source_files:
        assert f.is_file(),f
        z.write(f,str(f.relative_to(ROOT)) if f.is_relative_to(ROOT) else 'teammate_checkpoint/'+f.name)
print('E127_ARCHIVE_PATH',archive,flush=True)
print('E127_ARCHIVE_BYTES',archive.stat().st_size,flush=True)
print('E127_ARCHIVE_SHA256',hashlib.sha256(archive.read_bytes()).hexdigest(),flush=True)
print('E127_VERIFIED_EPISODES',total_episodes,'ACTIONS',total_actions,flush=True)
print('E127_AUDIT_COMPLETE',flush=True)
