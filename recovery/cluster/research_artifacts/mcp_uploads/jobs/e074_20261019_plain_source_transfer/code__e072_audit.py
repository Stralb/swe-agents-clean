"""E072: read-only empirical learning-signal sufficiency audit.

Consumes archived native action histories; does not open/inspect game-engine code,
act in any SDK game, train a model, or touch held-out families.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
import pathlib
import zipfile

TRAIN=("sb26","s5i5","lf52","tn36","g50t")
TEST=("cn04","lp85","m0r0","r11l","sk48")
RESERVE=("ar25","dc22","re86","tu93")
LOCKED=("bp35","ka59","ls20","su15","tr87","cd82","ft09","sc25","sp80","vc33","wa30")
E067='E067_NATIVE_EFFICIENCY_20261018/results/development5/'
E067_ALL='E067_NATIVE_EFFICIENCY_20261018/results/full14/'
PINNED_HF_REV='455b7c58eaa9d5ea05f91cd1b5b603121599e758'
PINNED_HF_REPO='magic-sword/arc_agi_3_public_demo_human_testing'


def sha_file(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for block in iter(lambda:f.read(2**20),b''):
   h.update(block)
 return h.hexdigest()


def load_e067_train(archive,train=TRAIN):
 result=[]
 with zipfile.ZipFile(archive) as z:
  names=set(z.namelist())
  for game in train:
   path=E067+game+'.json'
   if path not in names:
    raise FileNotFoundError(path)
   d=json.loads(z.read(path))
   if d['game']!=game:raise ValueError('Source game mismatch')
   if d['total_calls']>d['budget']:raise ValueError('Uncharged budget overflow')
   if not d['constructor_reset_charged']:raise ValueError('Constructor RESET not charged')
   rows=d['rows'];adv=[]
   for i,r in enumerate(rows):
    if int(r.get('delta_levels',0))>0:
     adv.append({'call':int(r['call']),'action':int(r['action']),
                'delta':int(r['delta_levels']),'index':i,
                'length_h16':min(i+1,16),'length_h32':min(i+1,32),
                'reason':r.get('reason')})
   if sum(r['delta'] for r in adv)!=int(d['levels_completed']):
    raise ValueError(f'Native level ledger disagreement {game}')
   if len(rows)!=d['total_calls']-1:raise ValueError('Charged SDK call accounting mismatch')
   result.append({'game':game,'calls':int(d['total_calls']),'levels':int(d['levels_completed']),
                  'advances':adv,'all_game_actions':len(rows),
                  'first_success_call':adv[0]['call'] if adv else None,
                  'reason_frequencies':dict(collections.Counter(r.get('reason','') for r in rows))})
 return result



def verify_human_manifest(path):
 """Fail closed on missing raw Parquet bytes or session-level evidence.

 Does not inspect ANY excluded-family trajectory, nor parse any Parquet rows.
 This is an integrity/provenance gate, not proof that a dataset is an oracle.
 """
 import numpy as np
 path=pathlib.Path(path)
 h=json.loads(path.read_text())
 prov=h.get('data_provenance',{})
 if h.get('status')!='VERIFIED_READY_FOR_TRAINING' or not h.get('human_data_not_native_self_generated'):
  raise PermissionError('Unverified/fixture human manifest')
 if prov.get('repo')!=PINNED_HF_REPO or prov.get('revision')!=PINNED_HF_REV:
  raise PermissionError('Wrong repository/revision')
 if set(h.get('train_families',()))!=set(TRAIN) or set(h.get('excluded_source_families',()))!=set(TEST+RESERVE):
  raise PermissionError('Wrong family train/test whitelist')
 if set(h.get('protected_and_dev_families',()))!=set(LOCKED):
  raise PermissionError('Wrong protected/dev family exclusions')
 snap=pathlib.Path(prov.get('snapshot_root') or '__missing_snapshot__')
 lock=snap/'E068_HUMAN_DATA_LOCK.json'
 if not lock.is_file():raise FileNotFoundError('Snapshot raw-byte lock missing')
 doc=json.loads(lock.read_text())
 if doc.get('repo')!=PINNED_HF_REPO or doc.get('revision')!=PINNED_HF_REV or doc.get('state')!='VERIFIED':
  raise PermissionError('Snapshot lock invalid')
 shards=doc.get('shards',[])
 if not shards:raise ValueError('No raw Parquet data available')
 original={x['file']:x['sha256'] for x in shards}
 if original!=prov['sha256_by_shard']:
  raise PermissionError('Human raw shard manifest diverged')
 actual={str(x.relative_to(snap)) for x in (snap/'data').glob('*.parquet')}
 if actual!=set(original):raise PermissionError('Snapshot raw Parquet inventory changed')
 for x in shards:
  rel=x['file']
  if not rel.startswith('data/') or not rel.endswith('.parquet') or '..' in pathlib.PurePosixPath(rel).parts:
   raise PermissionError('Unsafe Parquet shard path')
  f=snap/rel
  if not f.is_file() or f.stat().st_size!=x['bytes'] or sha_file(f)!=x['sha256']:
   raise PermissionError('Raw Parquet bytes not hash-verified')
  with f.open('rb') as fh:
   if fh.read(4)!=b'PAR1':raise ValueError('Invalid raw Parquet magic')
 sums=collections.Counter();seen=set();fam=set();events=0;actions=collections.Counter()
 for entry in h.get('shards',[]):
  game=entry['family']
  if game not in TRAIN:raise PermissionError('Evaluation family in human session')
  if entry['session_sha256'] in seen:raise PermissionError('Duplicate session ID')
  seen.add(entry['session_sha256']);fam.add(game)
  name=entry['file']
  if pathlib.Path(name).name!=name or not name.endswith('.npz'):raise PermissionError('Unsafe training shard')
  f=path.parent/name
  if not f.is_file() or sha_file(f)!=entry['file_sha256']:
   raise PermissionError('Human session shard missing or modified')
  with np.load(f,allow_pickle=False) as z:
   req={'frame','next_frame','action','reward','legal','family'}
   if not req.issubset(z.files):raise ValueError('Human session schema incomplete')
   reward=np.asarray(z['reward']);ac=np.asarray(z['action']);fi=np.asarray(z['family'])
   if not(len(reward)==len(ac)==len(fi)):raise ValueError('Human session transitions unaligned')
   if not np.all(fi==TRAIN.index(game)) or np.any(reward<0):
    raise PermissionError('Human family leakage or invalid reward')
   if np.any((ac<1)|(ac>7)):raise ValueError('Human actor action invalid')
   if np.any(~z['legal'][np.arange(len(ac)),ac]):raise ValueError('Illegal action in human session')
   for aa,rr in zip(ac,reward):
    if rr>0:
     actions[str(int(aa))]+=int(rr)
   sums[game]+=int(reward.sum());events+=int(reward.sum())
 if len(seen)!=h['human_sessions'] or events!=h['native_advancements'] or fam!=set(TRAIN):
  raise ValueError('Session count/reward/family proof mismatch')
 if len(seen)<20 or events<30 or len([v for v in sums.values() if v>0])<4:
  raise PermissionError('Insufficient independent human session / reward diversity')
 # Real human supervision must cover both spatial and simple controls if claiming a two-mode curriculum.
 if not(actions.get('6',0)>0 and sum(v for k,v in actions.items() if k!='6')>0):
  raise PermissionError('Human rewards do not cover both click and primitive action families')
 return {'human_sessions':len(seen),'native_advancements':events,
         'reward_families':sorted(k for k,v in sums.items() if v>0),
         'positive_reward_actions':dict(actions),'original_shards':len(shards),
         'snapshot_hashes_verified':True,'fixture_only':False}


def audit(e067,e071_audit=None,human_manifest=None):
 if len(set(TRAIN+TEST+RESERVE+LOCKED))!=len(TRAIN+TEST+RESERVE+LOCKED):
  raise AssertionError('Frozen family split not disjoint')
 if len(TRAIN)!=5 or len(TEST)!=5:
  raise AssertionError('Frozen five versus five split changed')
 d=load_e067_train(e067)
 total_adv=sum(len(x['advances']) for x in d)
 success=[x['game'] for x in d if x['advances']]
 reward_action_types=collections.Counter(str(a['action']) for x in d for a in x['advances'])
 event_h16=sum(a['length_h16'] for x in d for a in x['advances'])
 event_h32=sum(a['length_h32'] for x in d for a in x['advances'])
 external_verified=False
 human=None
 if human_manifest is not None:
  human=verify_human_manifest(human_manifest)
  external_verified=True
 ppo=None
 if e071_audit is not None:
  e=json.loads(pathlib.Path(e071_audit).read_text())
  if not e.get('source_five_only') or e.get('any_holdout_instantiated') or e.get('replayed_trials')!=30:
   raise ValueError('E071 independent replay summary must attest 30 source-five only trials')
  trials=e.get('trials',[])
  if len(trials)!=30 or e.get('native_level_advances')!=sum(x.get('num_positive_native_advances',0) for x in trials):
   raise ValueError('E071 per-case native event ledger discrepancy')
  if not all(x.get('full_frame_exact') and x.get('native_progress_outcome_exact') for x in trials):
   raise ValueError('E071 action-history replay failed')
  per=collections.defaultdict(lambda:{'trials':0,'native_advancements':0})
  for x in trials:
   if x['game'] not in TRAIN:raise PermissionError('E071 heldout trial leakage')
   name=x['policy']; per[name]['trials']+=1;per[name]['native_advancements']+=x['num_positive_native_advances']
  ppo={'audit_file_sha256':sha_file(e071_audit),'actual_native_replay_summary':dict(per),
       'verified_frame_exact_trials':e.get('full_frame_exact_trials')}
 # An arbitrary subwindow around each success does NOT give independent solutions.
 empirical={
  'frozen_train_families':list(TRAIN),'frozen_prospective_source_test_families':list(TEST),
  'frozen_historic_reserve':list(RESERVE),'frozen_quarantined_dev_and_protected':list(LOCKED),
  'all_25_public_historically_studied':True,
  'training_games':len(d),'training_native_levels':sum(x['levels'] for x in d),
  'training_distinct_successful_families':len(success),'successful_families':success,
  'real_native_reward_events':total_adv,'reward_events_by_action_type':dict(reward_action_types),
  'max_h16_success_adjacent_windows_not_independent':event_h16,
  'max_h32_success_adjacent_windows_not_independent':event_h32,
  'native_e067_source_research_archive_sha256':sha_file(e067),
  'external_human_manifest_validated':external_verified,'external_human_evidence':human,
  'e071_native_baseline_reference':ppo,
  'sufficiency_gates':{
   'human_or_equivalent_real_diverse_data_verified':external_verified,
   'at_least_four_distinct_reward_families':len(success)>=4 or bool(human and len(human['reward_families'])>=4),
   'at_least_30_real_advancement_events':total_adv>=30 or bool(human and human['native_advancements']>=30),
   'rewards_in_both_click_and_primitive_mechanics':bool(human and human['positive_reward_actions'].get('6',0)>0 and sum(v for k,v in human['positive_reward_actions'].items() if k!='6')>0),
   'frozen_source_test_five_remain_closed_in_E072':True,
  },
  'decision':'HUMAN_DATA_REQUIRED_BEFORE_FURTHER_NATIVE_REWARD_RL'
    if not external_verified else 'DATA_DIVERSITY_GATE_PASSED__TRAIN_AND_VERIFY_BEFORE_TEST',
  'native_e072_sdk_calls':0,
  'native_e072_new_level_advancements':0,
  'prospective_test_executions_e072':0,
  'official_RHAE':None,
  'per_game':d,
 }
 return empirical



def verify_release_provenance(archive,ppo_audit,provenance):
 """Check consumed source evidence against hashes locked from original E067/E071.

 Only the five development trace entries are opened, never test game code.
 """
 meta=json.loads(pathlib.Path(provenance).read_text())
 hash_archive=sha_file(archive)
 allowed={meta['source5_archive_sha256'],meta['E067_original_release_sha256']}
 if hash_archive not in allowed:
  raise PermissionError('Source evidence is not a verified original or verified source-five-only archive')
 if sha_file(ppo_audit)!=meta['E071_original_audit_sha256']:
  raise PermissionError('PPO independent audit differs from the frozen original')
 with zipfile.ZipFile(archive) as z:
  for entry in meta['member_sha256']:
   if hashlib.sha256(z.read(entry['member'])).hexdigest()!=entry['original_member_sha256']:
    raise PermissionError('Archived native trace content diverged from the original')
 return True


def main():
 p=argparse.ArgumentParser()
 p.add_argument('--e067-archive',type=pathlib.Path,required=True)
 p.add_argument('--e071-audit',type=pathlib.Path,default=None)
 p.add_argument('--human-manifest',type=pathlib.Path,default=None)
 p.add_argument('--provenance',type=pathlib.Path,default=pathlib.Path(__file__).resolve().parents[1]/'reference/SOURCE_PROVENANCE.json')
 p.add_argument('--out',type=pathlib.Path,required=True)
 a=p.parse_args()
 verify_release_provenance(a.e067_archive,a.e071_audit,a.provenance)
 result=audit(a.e067_archive,a.e071_audit,a.human_manifest)
 a.out.parent.mkdir(parents=True,exist_ok=True)
 a.out.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k!='per_game'},indent=2))

if __name__=='__main__':main()
