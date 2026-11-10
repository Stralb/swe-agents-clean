#!/bin/bash
#SBATCH --job-name=E074_orig_ingest
#SBATCH --partition=batch
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=01:30:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
PY=/home-mscluster/astrauss/arc26/.venv/bin/python
"$PY" - <<'PY'
from pathlib import Path
import sys,hashlib,json,datetime,collections
ROOT=Path('/home-mscluster/astrauss/E074_HUMAN_TO_POLICY_20261019')
WORK=Path('/home-mscluster/astrauss/e074_human_training')
STAGE=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e074_20261019_plain_source_transfer')
EXPECTED={
'code/e072_audit.py':'06bc98b26cca0bc77df6828b089eee62510527e5f7f20912bccd4cb074c55af3',
'code/e074_pipeline.py':'0bd936cce53aa849a1cb24bb3c3fa34f79e17a5e83a7288a2f829fb10cde39aa',
'code/e074_report_evidence.py':'b80c48e2fa5f2fbdd930f8b09b4f52df57327144929ea4bbdad15e74fe9375ff',
'code/e074_smoke_native.py':'2f9856b58c2c5c8339a7a3be6fd9919f462aa9fcab61daabdde6a306008ecc3e',
'vendor/e068/code/acquire_human.py':'3a07019d74973606847f3e279606f84e5223dd7ab5e4be35c778339078dc4ff4',
'vendor/e068/code/e068_split.py':'b749c2009f0a083afd3b33cefe35224af40832104df213aaa32d24e3492b7989',
'vendor/e068/code/ingest_human.py':'28075687a6376a1931c329ce7482535a477f2bbef3c50c65e540f31f80c22558',
'vendor/e068/code/train_human_five.py':'d3829313eb297748f3209a22f5f53519281036783eccf4ef071ac920737961e0',
'vendor/e068/code/train_pixel_rl.py':'af1448e4329b65ef4623c6dbcb49c1788cf50bab50f6fcc367277eeceda838d4',
'vendor/e069/code/e068_split.py':'b749c2009f0a083afd3b33cefe35224af40832104df213aaa32d24e3492b7989',
'vendor/e069/code/e069_human_train.py':'01004a309e39dbdd59038ad0fd7bd2a28bd29572f934575537f48c68ecb24ca8',
'vendor/e069/code/history_ddqn.py':'b5e14cddd0f46e2b9977654ee1647d75169f17d5faca93da7085d6239ac306f8',
'vendor/e069/code/source_audit.py':'9e2f19be4bc1c650d6d21724d2e4076c87e7e5c18ac8941fb70790ec4c029df8',
'tools/e074_gate_probe.py':'afbfa306bb0f979469a1709d106820248aad007006f692f232f88b2612ca3824',
'tools/e074_offline_policy_probe.py':'4bbe70b55e6841da6006dffa3d8500952ab89bbcb93b03740571cf1180cd791c',
'tests/test_e074.py':'e527045a983bf78be58acbaa302f79ea7753cef2084d576668360b37b1f91fa3'
}
def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  while data:=f.read(1<<20):h.update(data)
 return h.hexdigest()
print('SOURCE_STAGE_BEGIN',len(EXPECTED),flush=True)
for rel,expected in EXPECTED.items():
 src=STAGE/rel.replace('/','__');dest=ROOT/rel
 if not src.is_file() or sha(src)!=expected:
  raise RuntimeError('Exact staged source hash mismatch '+rel)
 if dest.exists():
  if sha(dest)!=expected:raise PermissionError('Refuse overwrite of changed code '+rel)
  print('EXISTING_VERIFIED',rel,flush=True);continue
 dest.parent.mkdir(parents=True,exist_ok=True)
 with open(dest,'xb') as out,open(src,'rb') as source:
  while data:=source.read(1<<20):out.write(data)
 if sha(dest)!=expected:raise RuntimeError('Transferred source mismatch '+rel)
 print('TRANSFERRED_VERIFIED',rel,flush=True)
WORK.mkdir(parents=True,exist_ok=True)
lock=WORK/'E074_SOURCE_TRANSFER_LOCK_20261019.json'
if not lock.exists():
 with open(lock,'x') as f:json.dump({
  'source':'original E074 Python sources, SHA256 matched the user-supplied release',
  'files_sha256':EXPECTED,'files_transferred':len(EXPECTED),
  'binary_E067_reference_and_smoke_checkpoints_transferred':False,
  'original_E074_main_pipeline_parent_reference_audit_executed_here':False,
  'no_existing_files_overwritten':True},f,indent=2)
sys.path[:0]=[str(ROOT/'code'),str(ROOT/'vendor/e068/code'),str(ROOT/'vendor/e069/code')]
from acquire_human import verify
from ingest_human import scan_parquet,save
from e072_audit import verify_human_manifest
SNAP=WORK/'human_snapshot'
frozen=verify(SNAP)
print('PINNED_SNAPSHOT_VERIFIED',frozen['revision'],len(frozen['shards']),flush=True)
ing=WORK/'human_five_training'
manifest=ing/'E068_HUMAN_TRAINING_MANIFEST.json'
if not manifest.exists():
 if ing.exists() and any(ing.iterdir()):
  raise PermissionError('Partial human ingestion exists: stop instead of overwriting')
 frozen=dict(frozen,snapshot_root=str(SNAP))
 summary=save(scan_parquet(SNAP),ing,verified_snapshot=frozen)
 print('E068_INGEST_CREATED',json.dumps({k:v for k,v in summary.items() if k!='shards'}),flush=True)
else:print('E068_INGEST_EXISTS_VALIDATING_IN_PLACE',flush=True)
verification=verify_human_manifest(manifest)
print('ORIGINAL_E072_HUMAN_GATE_PASSED',json.dumps(verification),flush=True)
summary=json.loads(manifest.read_text())
error_counts=collections.Counter()
for row in summary['shards']:error_counts.update(row.get('errors',{}))
source=(WORK/'E074_VALIDATED_HUMAN_GATE.json')
gate={'kind':'E074_VERIFIED_HUMAN_SOURCE_FIVE_DATA_GATE',
 'input_manifest_sha256':sha(manifest),
 'human_snapshot_lock_sha256':sha(SNAP/'E068_HUMAN_DATA_LOCK.json'),
 'verified_human_evidence':verification,
 'source_sha256':EXPECTED,'human_errors':dict(error_counts),
 'gates':{'human_or_equivalent_real_diverse_data_verified':True,
  'at_least_four_distinct_reward_families':len(verification['reward_families'])>=4,
  'at_least_30_real_advancement_events':verification['native_advancements']>=30,
  'rewards_in_both_click_and_primitive_mechanics':
    verification['positive_reward_actions'].get('6',0)>0 and
    sum(v for k,v in verification['positive_reward_actions'].items() if k!='6')>0,
  'frozen_source_test_five_remain_closed_in_E074':True},
 'five_training_only':True,
 'binary_E067_reference_transferred':False,
 'no_test_games_instantiated':True}
if not all(gate['gates'].values()):raise PermissionError('Original E074 data diversity gate failed')
if source.exists():
 old=json.loads(source.read_text())
 if old['input_manifest_sha256']!=gate['input_manifest_sha256']:
  raise PermissionError('Refuse overwrite existing E074 gate')
else:
 with open(source,'x') as f:json.dump(gate,f,indent=2)
print('E074_GATE_FROZEN_SHA256',sha(source),flush=True)
print('E074_ORIGINAL_INGEST_AND_DATA_GATE_SUCCESS',flush=True)
PY