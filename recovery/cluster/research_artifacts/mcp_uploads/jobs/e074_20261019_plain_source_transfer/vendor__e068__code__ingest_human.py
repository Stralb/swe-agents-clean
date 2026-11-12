"""Strict five-family public human data ingestion. No simulation or invented rewards.

Important: Arrow `env` predicate is evaluated BEFORE the trajectory column is
materialized as Python objects. Evaluation-family trajectory JSON is never
passed to the decoder. Requires pinned, hash-verified local Parquet.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from acquire_human import verify
from e068_split import TRAIN_FAMILIES,TEST_FAMILIES,FORBIDDEN,sha
BASE=Path(__file__).resolve().parents[1]

def canonical_env(s):
 return str(s).split('-')[0].lower()

def parse_action(inp):
 if isinstance(inp,dict):
  act=inp.get('id',inp.get('action'))
  payload=inp.get('data') or inp.get('action_data') or {}
 elif isinstance(inp,(int,str)):
  act=inp;payload={}
 else:return None,{}
 if isinstance(act,str):
  z=act.split('.')[-1].upper()
  if z=='RESET':act=0
  elif z.startswith('ACTION') and z[6:].isdigit():act=int(z[6:])
  elif z.isdigit():act=int(z)
  else:return None,{}
 if not isinstance(act,int) or act not in range(8):return None,{}
 if not isinstance(payload,dict):payload={}
 return act,payload

def parse_frame(value):
 if value is None:return None
 try:
  z=np.asarray(value)
  if z.shape==(64,64):z=z.astype(np.uint8)
  elif z.shape==(4096,):z=z.reshape(64,64).astype(np.uint8)
  elif len(z.shape)==3 and z.shape[-2:]==(64,64):z=z[-1].astype(np.uint8)
  else:return None
  if int(z.min())<0 or int(z.max())>15:raise ValueError('Frame palette outside 0..15')
  return z.copy()
 except (TypeError,OverflowError,ValueError):return None

def legal_actions(value):
 if value is None:return None
 if not isinstance(value,(tuple,list)):return None
 x=[]
 for elem in value:
  a,_=parse_action(elem)
  if a is None:return None
  x.append(a)
 if any(a>7 for a in x):return None
 return sorted(set(x))

def convert_session(row):
 family=canonical_env(row.get('env') or '')
 if family not in TRAIN_FAMILIES:raise PermissionError(f'Nontraining family {family} passed to human trajectory decoder')
 raw=row.get('trajectory')
 events=json.loads(raw) if isinstance(raw,str) else raw
 if not isinstance(events,list):raise ValueError('Expected list of human action frame events')
 entries=[];errors={'missing_frame':0,'missing_action':0,'missing_level':0,'illegal_action':0,'missing_coords':0,'invalid_legal':0,'level_regression':0}
 previous=None;resets=0;native_advances=0
 for index,event in enumerate(events):
  d=event.get('data',event) if isinstance(event,dict) else None
  if not isinstance(d,dict):previous=None;errors['missing_frame']+=1;continue
  f=parse_frame(d.get('frame'))
  if f is None:previous=None;errors['missing_frame']+=1;continue
  rawlevel=d.get('levels_completed')
  if rawlevel is None:previous=None;errors['missing_level']+=1;continue
  level=int(rawlevel)
  legal=legal_actions(d.get('available_actions'))
  if legal is None:errors['invalid_legal']+=1
  action,payload=parse_action(d.get('action_input'))
  if action==0 or bool(d.get('full_reset',False)):
   resets+=1;previous={'frame':f,'level':level,'legal':legal};continue
  if previous is None:
   previous={'frame':f,'level':level,'legal':legal};continue
  if action is None:
   errors['missing_action']+=1;previous=None;continue
  if previous['legal'] is None or action not in previous['legal']:
   errors['illegal_action']+=1;previous=None;continue
  if level<previous['level']:
   errors['level_regression']+=1;previous={'frame':f,'level':level,'legal':legal};continue
  xy=[int(payload.get('x',-1)),int(payload.get('y',-1))]
  if action==6 and not (0<=xy[0]<64 and 0<=xy[1]<64):
   errors['missing_coords']+=1;previous=None;continue
  delta=max(0,level-previous['level']);native_advances+=delta
  mask=np.zeros(8,dtype=bool);mask[previous['legal']]=True
  nextmask=np.zeros(8,dtype=bool)
  if legal is not None:nextmask[legal]=True
  entries.append({'frame':previous['frame'],'next_frame':f,'action':action,'xy':xy,
   'reward':delta,'terminal':bool(delta>0 or str(d.get('state','')).split('.')[-1].upper() in ('GAME_OVER','WIN')),
   'legal':mask,'next_legal':nextmask,'family':TRAIN_FAMILIES.index(family),'session_step':index})
  previous={'frame':f,'level':level,'legal':legal}
 sid=str(row.get('guid','missing_guid'))
 return {'family':family,'session_sha256':hashlib.sha256(sid.encode()).hexdigest(),
         'records':entries,'native_advancements':native_advances,'session_resets':resets,'errors':errors,'input_events':len(events)}

def scan_parquet(snapshot):
 import pyarrow.dataset as ds
 root=Path(snapshot);verify(root)
 paths=sorted((root/'data').glob('*.parquet'))
 data=ds.dataset([str(x) for x in paths],format='parquet')
 required={'env','trajectory','guid'}
 if not required.issubset(data.schema.names):raise ValueError(f'Human Parquet missing {required-set(data.schema.names)}')
 # No evaluation-family trajectory cell is brought into Python memory.
 scanner=data.scanner(columns=['env','guid','trajectory'],filter=ds.field('env').isin(list(TRAIN_FAMILIES)),batch_size=2)
 for b in scanner.to_batches():
  for row in b.to_pylist():
   if row['env'] not in TRAIN_FAMILIES:raise AssertionError('Arrow family predicate bypass')
   yield row

def save(rows,out,min_sessions=5,min_advances=5,min_success_families=2,verified_snapshot=None,fixture_only=False):
 if not fixture_only and not verified_snapshot:
  raise PermissionError('Real public human dataset lock must be verified before creating a trainable manifest')
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 seen=set();manifest=[];total=0;rewards=0
 for row in rows:
  parsed=convert_session(row)
  sid=parsed['session_sha256']
  if sid in seen:raise ValueError('Duplicate human recording')
  seen.add(sid)
  content=parsed.pop('records')
  if not content:continue
  arr={name:np.stack([e[name] for e in content]) for name in content[0]}
  assert set(np.unique(arr['family'])) <=set(range(5))
  target=out/f'{parsed["family"]}_{sid[:16]}.npz'
  np.savez_compressed(target,**arr)
  parsed.update({'file':target.name,'file_sha256':sha(target),'observed_transitions':len(content)})
  rewards+=int(arr['reward'].sum());total+=len(content);manifest.append(parsed)
 successful=sorted(set(r['family'] for r in manifest if r['native_advancements']>0))
 gates={'sessions':len(manifest)>=min_sessions,'native_rewards':rewards>=min_advances,'reward_families':len(successful)>=min_success_families,
   'five_train_families_have_sessions':{x['family'] for x in manifest}==set(TRAIN_FAMILIES)}
 result={'status':('FIXTURE_ONLY_NOT_HUMAN_DATA' if fixture_only else 'VERIFIED_READY_FOR_TRAINING' if all(gates.values()) else 'INSUFFICIENT_HUMAN_NATIVE_REWARDS'),
  'data_provenance':{'repo':verified_snapshot.get('repo'),'revision':verified_snapshot.get('revision'),'sha256_by_shard':{x['file']:x['sha256'] for x in verified_snapshot.get('shards',[])},'snapshot_root':verified_snapshot.get('snapshot_root')} if verified_snapshot else {'fixture_only':True},
  'train_families':list(TRAIN_FAMILIES),'excluded_source_families':list(TEST_FAMILIES),'protected_and_dev_families':list(FORBIDDEN),
  'human_data_not_native_self_generated':not fixture_only,'human_sessions':len(manifest),'native_advancements':rewards,
  'native_reward_families':successful,'total_transitions':total,'gates':gates,'shards':manifest}
 (out/'E068_HUMAN_TRAINING_MANIFEST.json').write_text(json.dumps(result,indent=2)+'\n')
 return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--snapshot',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
 a=p.parse_args();snapshot=verify(a.snapshot);snapshot['snapshot_root']=str(a.snapshot.resolve());result=save(scan_parquet(a.snapshot),a.out,verified_snapshot=snapshot)
 print(json.dumps({k:v for k,v in result.items() if k!='shards'},indent=2),flush=True)
 if result['status']!='VERIFIED_READY_FOR_TRAINING':raise SystemExit(3)
