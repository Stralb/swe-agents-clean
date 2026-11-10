"""Source-5-only human offline BC versus reward-weighted AWR.

Requires REAL hash-verified public human Parquet ingestion. Never fabricates
human recordings, game rewards, held-out results or trained checkpoints.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
from e068_split import TRAIN_FAMILIES,TEST_FAMILIES,FORBIDDEN,sha
from acquire_human import verify
from train_pixel_rl import train
FIELDS=['frame','next_frame','action','xy','reward','terminal','legal','next_legal','family','session_step']

def validate_and_merge(src,out):
 src=Path(src);out=Path(out);out.mkdir(parents=True,exist_ok=True)
 manifest_file=src/'E068_HUMAN_TRAINING_MANIFEST.json'
 doc=json.loads(manifest_file.read_text())
 if doc.get('status')!='VERIFIED_READY_FOR_TRAINING' or not doc.get('human_data_not_native_self_generated') or doc.get('data_provenance',{}).get('repo')!='magic-sword/arc_agi_3_public_demo_human_testing':
  raise RuntimeError('Human provenance/reward gate failed. Refuse training.')
 provenance=doc['data_provenance']
 snapshot_root=provenance.get('snapshot_root')
 if not snapshot_root:raise RuntimeError('Human data snapshot source path absent')
 locked=verify(snapshot_root,revision=provenance['revision'])
 if locked['repo']!=provenance['repo'] or {x['file']:x['sha256'] for x in locked['shards']}!=provenance['sha256_by_shard']:
  raise RuntimeError('Human snapshot provenance and shard hash inventory changed')
 if tuple(doc['train_families'])!=TRAIN_FAMILIES:raise PermissionError('Human data train-family split differs')
 if set(doc['excluded_source_families'])!=set(TEST_FAMILIES):raise PermissionError('Excluded source families changed')
 if set(doc['protected_and_dev_families'])!=set(FORBIDDEN):raise PermissionError('Protected split changed')
 actual_families={row['family'] for row in doc['shards']}
 if actual_families!=set(TRAIN_FAMILIES):raise RuntimeError('Human curriculum requires verified recordings from each of five training families')
 arrays={k:[] for k in FIELDS}
 for i,row in enumerate(doc['shards']):
  family=row['family'];p=src/row['file']
  if family not in TRAIN_FAMILIES:raise PermissionError('Forbidden human shard')
  if p.name != row['file'] or sha(p)!=row['file_sha256']:raise RuntimeError('Human session hash mismatch')
  z=np.load(p,allow_pickle=False)
  if set(z.files)!=set(FIELDS):raise ValueError('Human session schema mismatch')
  family_idx=TRAIN_FAMILIES.index(family)
  if not np.all(z['family']==family_idx):raise PermissionError('Human array game-family leakage')
  if z['frame'].ndim!=3 or z['frame'].shape[1:]!=(64,64):raise ValueError('Human frame is not 64x64')
  if np.any(z['reward']<0) or not np.all(z['legal'][np.arange(len(z['action'])),z['action']]):
   raise ValueError('Invalid native reward or action legality')
  for k in FIELDS:
   arr=np.asarray(z[k]);
   # Strict episode separation for discounting even between same-family files.
   if k=='session_step':arr=arr.astype(np.int64)+(i+1)*1_000_000
   arrays[k].append(arr)
 data={k:np.concatenate(v) for k,v in arrays.items()}
 merged=out/'human_train_source5.npz';np.savez_compressed(merged,**data)
 summary={'source_type':'public_human_playing_not_self_generated','manifest_sha256':sha(manifest_file),
  'sha256':sha(merged),'sessions':len(doc['shards']),'native_advancements':int(data['reward'].sum()),
  'number_examples':int(len(data['reward'])),'families':list(TRAIN_FAMILIES),
  'excluded':list(TEST_FAMILIES),'forbidden':list(FORBIDDEN),'path':str(merged)}
 if summary['native_advancements'] != doc['native_advancements']:raise AssertionError('Reward mismatch in merged sessions')
 (out/'HUMAN_PRETRAIN_VERIFIED.json').write_text(json.dumps(summary,indent=2)+'\n')
 return merged,summary

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
 p.add_argument('--updates',type=int,default=2500);args=p.parse_args()
 path,summary=validate_and_merge(args.source,args.out)
 print('SOURCE5_HUMAN_VERIFIED',json.dumps(summary),flush=True)
 for mode in ('bc','awr','shuffled'):
  audit=train(mode=mode,seed=2068,steps=args.updates,dataset_path=path,output_dir=args.out,source_type='public human sessions, source5 only')
  audit['human_manifest_sha256']=summary['manifest_sha256']
  (args.out/f'pixel_{mode}_training.json').write_text(json.dumps(audit,indent=2)+'\n')
 print('BC_AND_AWR_TRAINING_FINISHED',flush=True)
