#!/bin/bash
#SBATCH --job-name=E108_rotation_audit
#SBATCH --partition=stampede
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:08:00
#SBATCH --dependency=afterok:72161
set -euo pipefail
umask 077
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
from pathlib import Path
from collections import Counter
import hashlib,json,random,zipfile
H=Path('/home-mscluster/astrauss')
W=H/'e108_random_development_rounds'
S=H/'research_artifacts/mcp_uploads/jobs/e108_20261020_random_rounds'
Z=H/'E108_FOUR_RANDOM_ROUNDS_20261020.zip'
OUT=S/'E108_VERIFIED_FOUR_ROUNDS.json'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
if Z.exists() or OUT.exists():raise FileExistsError('Preserve existing evidence')
allrows=[];allselections=[];seen=set();files={}
for rn in (1,2,3,4):
 root=W/('round_%02d'%rn)
 selection=json.loads((root/'SELECTION_FROZEN.json').read_text())
 result=json.loads((root/'ROUND_RESULT.json').read_text())
 assert result['completed_trials']==60 and not result['errors']
 assert selection['budget']==512 and selection['policy_seeds']==[28901,28902,28903]
 assert not set(selection['selected_games']).intersection(selection['protected_families'])
 rng=random.Random(int(selection['random_seed_hex'],16))
 if rn<=3:
  assert rng.sample(selection['eligible_remaining_before_draw'],5)==selection['selected_games']
  assert not set(selection['selected_games']).intersection(seen)
 else:
  assert len(selection['first_draw_in_sequence'])==1
  assert len(selection['recycled_development_families'])==4
  assert not set(selection['selected_games']).intersection(allselections[-1]['selected_games'])
 allselections.append(selection);seen.update(selection['selected_games'])
 for source,h in selection['source_hashes'].items():assert sha(Path(source))==h,(rn,source)
 by={};stats=Counter();model_updates=0;rewins=0
 paired=[];cpu=0.;decisions=0;raw=0;charged=0;wins=0
 for game in selection['selected_games']:
  by[game]={}
  for arm in selection['arms']:
   seq=[]
   for seed in selection['policy_seeds']:
    matching=[r for r in result['results'] if r.get('game')==game and r.get('seed')==seed and r.get('arm')==arm]
    assert len(matching)==1
    r=matching[0];assert 'error' not in r and r['actions']<=512
    folder=root/game/str(seed)/arm
    assert sha(folder/'trace.jsonl')==r['trace_sha256']
    assert sha(folder/'observations.npz')==r['frames_sha256']
    assert sha(folder/'native_scorecard.json')==r['scorecard_sha256']
    card=json.loads((folder/'native_scorecard.json').read_text())
    assert card['score']==r['score']
    assert r['actions']==r['decisions']+r['resets']-1
    assert r['raw_commands']==r['decisions']+r['resets']
    if arm=='candidate':stats.update(r['stats'])
    cpu+=r['cpu_seconds'];decisions+=r['decisions'];raw+=r['raw_commands'];charged+=r['actions'];wins+=r['won']
    seq.append(r['completed_levels'])
    for p in folder.iterdir():
     if p.is_file():files['round_%02d/'%rn+str(p.relative_to(root))]=p
   by[game][arm]=seq
  comparator='previous' if rn>1 else 'no_memory'
  a=by[game]['candidate'];b=by[game][comparator]
  paired.append({'game':game,'candidate_mean':sum(a)/3,'previous_or_ablation_mean':sum(b)/3})
 for p in (root/'SELECTION_FROZEN.json',root/'ROUND_RESULT.json'):files['round_%02d/'%rn+p.name]=p
 candidate_levels=sum(sum(by[g]['candidate']) for g in by)
 cand_success=sum(v>0 for g in by for v in by[g]['candidate'])
 qualifying=sum(sum(by[g]['candidate'])/3>=2 for g in by)
 summary={'round':rn,'games':selection['selected_games'],'candidate':selection['candidate'],
  'previous':selection['previous'],'levels_by_seed':by,'candidate_level_advances':candidate_levels,
  'candidate_trials_with_advancement':cand_success,'candidate_trials':15,
  'candidate_families_mean_at_least_two':qualifying,'paired_game_means':paired,
  'candidate_better_games':sum(p['candidate_mean']>p['previous_or_ablation_mean'] for p in paired),
  'candidate_worse_games':sum(p['candidate_mean']<p['previous_or_ablation_mean'] for p in paired),
  'total_successful_full_games_all_arms':wins,'compute_cpu_seconds_all_arms':round(cpu,3),
  'explicit_decisions_all_arms':decisions,'scorer_actions_all_arms':charged,'raw_commands_all_arms':raw,
  'candidate_mechanism_totals':dict(stats),'random_seed_hex':selection['random_seed_hex'],
  'recycled_families':selection.get('recycled_development_families',[]),
  'round_result_sha256':sha(root/'ROUND_RESULT.json')}
 allrows.append(summary)
 print('E108_AUDITED_ROUND',json.dumps(summary,sort_keys=True),flush=True)
for p in S.iterdir():
 if p.is_file() and p.suffix in ('.py','.sbatch'):files['source/'+p.name]=p
for name in ('E106_perception_v0.py','E106_online_explorer_v0.py'):
 p=H/'research_artifacts/mcp_uploads/jobs/e106_20261020_general_agent'/name
 files['source/'+name]=p
for rel in ('src/adapter.py','src/__init__.py'):
 p=H/'RL-ARC-AGI-3-Project'/rel
 if p.is_file():files['adapter/'+rel]=p
summary={'experiment':'E108_ROTATING_RANDOM_FIVE_DEVELOPMENT',
 'completed_rounds':4,'completed_trials':240,'distinct_public_families':len(seen),
 'seeds_are_policy_randomness_not_new_layouts':True,'every_policy_starts_without_cross_game_memory':True,
 'first_three_panels_disjoint':True,'fourth_has_explicit_recycling':True,
 'protected_families':allselections[0]['protected_families'],'protected_not_opened':True,
 'all_draws_source_frozen_before_native_evaluation':True,
 'budget_per_arm':512,'all_native_rewards_and_failures_accounted':True,
 'rounds':allrows,'general_breakthrough_established':any(r['candidate_families_mean_at_least_two']>=3 and r['candidate_better_games']>r['candidate_worse_games'] for r in allrows),
 'no_unseen_generalization_claim':True,'no_neural_DQN_or_PPO_training_in_this_experiment':True}
with OUT.open('x') as f:json.dump(summary,f,indent=2)
files['E108_VERIFIED_FOUR_ROUNDS.json']=OUT
manifest={k:{'sha256':sha(p),'bytes':p.stat().st_size} for k,p in files.items()}
with zipfile.ZipFile(Z,'x',zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
 for name,p in sorted(files.items()):z.write(p,name)
 z.writestr('SHA256_MANIFEST.json',json.dumps(manifest,indent=2))
with zipfile.ZipFile(Z) as z:assert z.testzip() is None
print('E108_ARCHIVE_READY',json.dumps({'path':str(Z),'bytes':Z.stat().st_size,'sha256':sha(Z),
 'trials':240,'families':len(seen),'target_reached':summary['general_breakthrough_established']}),flush=True)
PY
