"""E074: one-command strict source-five public-human data acquisition and frozen training.

* No game SDK is imported or opened.
* The five E070 prospective test families are NEVER decoded/evaluated here.
* Never uses a generated/fixture corpus in place of raw verified human Parquet.
* This is an offline evaluation-safe data/optimizer job, not proof of generalization.
"""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,os,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
E068=ROOT/'vendor/e068/code'
E069=ROOT/'vendor/e069/code'
sys.path[:0]=[str(ROOT/'code'),str(E068),str(E069)]
from e072_audit import audit,verify_release_provenance,verify_human_manifest

REFERENCE=ROOT/'reference'
SOURCE=REFERENCE/'E067_SOURCE5_ONLY_NATIVE_RECORDS.zip'
PPO=REFERENCE/'E071_INDEPENDENT_AUDIT.json'
PROV=REFERENCE/'SOURCE_PROVENANCE.json'


def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as fp:
  for b in iter(lambda:fp.read(1<<20),b''):h.update(b)
 return h.hexdigest()


def parent_reference():
 verify_release_provenance(SOURCE,PPO,PROV)
 d=audit(SOURCE,PPO)
 assert d['training_games']==5 and d['real_native_reward_events']==3
 assert not d['external_human_manifest_validated']
 assert d['frozen_prospective_source_test_families']==['cn04','lp85','m0r0','r11l','sk48']
 return d


def check_dependencies():
 required=('numpy','torch','huggingface_hub','pyarrow')
 missing=[name for name in required if importlib.util.find_spec(name) is None]
 if missing:raise ImportError('Missing packages: '+', '.join(missing))
 return {'dependencies_found':list(required)}


def train(work,updates=2500,snapshot=None,fetch=True,only_ingest=False):
 parent=parent_reference()
 work=Path(work).resolve()
 if work==ROOT or ROOT in work.parents:
  raise PermissionError('Output directory must be outside extracted source tree')
 check_dependencies()
 work.mkdir(parents=True,exist_ok=True)
 snapshot=Path(snapshot).resolve() if snapshot else work/'human_snapshot'
 ingested=work/'human_five_training'
 trained=work/'trained_human'
 from acquire_human import download,verify
 from ingest_human import scan_parquet,save
 if fetch:
  lock=download(snapshot)
 else:
  lock=verify(snapshot)
 lock=dict(lock,snapshot_root=str(snapshot))
 manifest=ingested/'E068_HUMAN_TRAINING_MANIFEST.json'
 if not manifest.is_file():
  # Pre-trajectory scan strictly filters env to allowed source families.
  save(scan_parquet(snapshot),ingested,verified_snapshot=lock)
 # The source audit validates hashes and signed family partition before any updates.
 verified=verify_human_manifest(manifest)
 gate=audit(SOURCE,PPO,manifest)
 if not all(gate['sufficiency_gates'].values()):
  raise PermissionError('Mandatory data-diversity science gates failed')
 (work/'E074_VALIDATED_HUMAN_GATE.json').write_text(json.dumps({
   'input_manifest_sha256':sha(manifest), 'human_snapshot_lock_sha256':sha(snapshot/'E068_HUMAN_DATA_LOCK.json'),
   'gates':gate['sufficiency_gates'], 'verified_human_evidence':verified,
   'five_training_only':True, 'source_only_native_reference_sha256':parent['native_e067_source_research_archive_sha256'],
   'no_test_games_instantiated':True},indent=2)+'\n')
 if only_ingest:return {'state':'VERIFIED_HUMAN_DATA_ONLY','human':verified,'training_started':False}
 from e069_human_train import run
 freeze=run(snapshot,ingested,trained,updates=updates)
 # Check the actual checkpoint bytes and freeze ledger before returning.
 for m in freeze['models']:
  # Keep both model and artifact hashes in a separate lock, no checkpoint selection on heldout.
  found=list(trained.glob('*'+m['mode']+'*.pt'))
  if not found:raise FileNotFoundError(f'Expected {m["mode"]} .pt checkpoint missing')
  if not any(sha(p)==m['sha256'] for p in found):
   raise ValueError(f'Checkpoint hash mismatch: {m["mode"]}')
 freeze.update({'source_family_frozen_test_never_instantiated':True,
  'native_score_claimed':False,'human_dataset_verified':True,'official_rhae':None})
 (work/'E074_TRAINING_COMPLETE_FREEZE.json').write_text(json.dumps(freeze,indent=2)+'\n')
 return {'state':'CHECKPOINTS_TRAINED_AND_HASH_FROZEN','models':freeze['models'],
         'evaluations_performed':0, 'official_score':None}


def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--mode',choices=('audit','train','ingest'),default='audit')
 p.add_argument('--work',type=Path)
 p.add_argument('--snapshot',type=Path,default=None)
 p.add_argument('--verify-existing',action='store_true')
 p.add_argument('--updates',type=int,default=2500)
 args=p.parse_args()
 if args.mode=='audit':
  out=parent_reference()
  print(json.dumps({'stage':'SOURCE_DATA_ONLY__HUMAN_NOT_YET_AVAILABLE',
    'real_native_reward_events':out['real_native_reward_events'],
    'train_reward_families':out['successful_families'],
    'prospective_test_games_still_closed':out['frozen_prospective_source_test_families'],
    'human_data_gate_passed':False,'training_performed':False},indent=2))
 else:
  if args.work is None:raise SystemExit('--work is required for training / ingestion')
  if not 10<=args.updates<=10000:raise SystemExit('Updates must be 10..10000')
  out=train(args.work,updates=args.updates,snapshot=args.snapshot,
    fetch=not args.verify_existing,only_ingest=args.mode=='ingest')
  print(json.dumps(out,indent=2))

if __name__=='__main__':main()
