#!/bin/bash
#SBATCH --job-name=E074_train_four
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=08:30:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=2
PY=/home-mscluster/astrauss/arc26/.venv/bin/python
ROOT=/home-mscluster/astrauss/E074_HUMAN_TO_POLICY_20261019
WORK=/home-mscluster/astrauss/e074_human_training
export PYTHONPATH="$ROOT/vendor/e069/code:$ROOT/vendor/e068/code:$ROOT/code"
"$PY" - <<'PY'
from pathlib import Path
import hashlib,json
import torch
ROOT=Path('/home-mscluster/astrauss/E074_HUMAN_TO_POLICY_20261019')
WORK=Path('/home-mscluster/astrauss/e074_human_training')
SRC=WORK/'human_five_training/E068_HUMAN_TRAINING_MANIFEST.json'
GATE=WORK/'E074_VALIDATED_HUMAN_GATE.json'
TRAIN=WORK/'trained_human'
FREEZE=WORK/'E074_TRAINING_COMPLETE_FREEZE.json'
SOURCE_LOCK=WORK/'E074_SOURCE_TRANSFER_LOCK_20261019.json'
SEED=2069; UPDATES=2500
def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  while b:=f.read(1<<20): h.update(b)
 return h.hexdigest()
if not SOURCE_LOCK.is_file():raise PermissionError('Verified E074 source transfer missing')
d=json.loads(SOURCE_LOCK.read_text())
if len(d['files_sha256'])!=16:raise PermissionError('Original E074 code transfer incomplete')
for rel,expected in d['files_sha256'].items():
 p=ROOT/rel
 if not p.is_file() or sha(p)!=expected:raise PermissionError('Original source SHA mismatch '+rel)
if not GATE.is_file():raise FileNotFoundError('Strict E074 human-data gate not established')
gate=json.loads(GATE.read_text())
if any(not x for x in gate['gates'].values()):raise PermissionError('Human gates not passed')
if sha(SRC)!=gate['input_manifest_sha256']:raise PermissionError('Ingested manifest modified after freeze')
from acquire_human import verify
from e072_audit import verify_human_manifest
snap=verify(WORK/'human_snapshot')
if sha(WORK/'human_snapshot/E068_HUMAN_DATA_LOCK.json')!=gate['human_snapshot_lock_sha256']:
 raise PermissionError('Pinned raw dataset lock was modified')
verified=verify_human_manifest(SRC)
if verified!=gate['verified_human_evidence']:
 raise PermissionError('Original human verifier now disagrees with frozen gate')
print('HUMAN_DATA_REVERIFIED',json.dumps(verified),flush=True)
if FREEZE.exists():
 raise PermissionError('Existing E074 complete freeze: no duplicate training allowed')
if TRAIN.exists() and any(TRAIN.iterdir()):
 raise PermissionError('Existing E074 training artifacts: do not overwrite partial checkpoints')
from e069_human_train import run
print('E074_FOUR_ARM_TRAIN_BEGIN','updates',UPDATES,'seed',SEED,flush=True)
freeze=run(WORK/'human_snapshot',WORK/'human_five_training',TRAIN,updates=UPDATES)
assert freeze['kind']=='E069_PRE_HOLDOUT_MODEL_FREEZE'
assert freeze['human_sessions']==60 and freeze['native_reward_events']==291
assert freeze['source_revision']=='455b7c58eaa9d5ea05f91cd1b5b603121599e758'
assert len(freeze['models'])==4 and {m['mode'] for m in freeze['models']}=={'bc','ddqn','shuffled','no_history'}
assert freeze['policy_training_script_sha256']==sha(ROOT/'vendor/e069/code/history_ddqn.py')
for rec in freeze['models']:
 mode=rec['mode'];file=TRAIN/f'history_{mode}.pt'
 if not file.is_file() or sha(file)!=rec['sha256']:raise RuntimeError('Checkpoint hash mismatch: '+mode)
 obj=torch.load(file,map_location='cpu',weights_only=True)
 audit=json.loads((TRAIN/f'history_{mode}_training.json').read_text())
 if obj['updates']!=UPDATES or obj['seed']!=SEED or obj['mode']!=mode:raise RuntimeError('Training settings mismatch: '+mode)
 if obj['dataset_hash']!=freeze['human_data_sha256']:raise RuntimeError('Checkpoint trained on different data')
 if audit['genuine_td_updates']!=(0 if mode=='bc' else UPDATES):raise RuntimeError('TD updates mismatch')
 if audit['sha256']!=sha(file) or audit['true_native_level_events']!=291:
  raise RuntimeError('Training audit does not match checkpoint')
 print('CHECKPOINT_VALIDATED',mode,rec['sha256'],'td_updates',audit['genuine_td_updates'],flush=True)
freeze.update({'source_family_frozen_test_never_instantiated':True,
  'native_score_claimed':False,'human_dataset_verified':True,'official_rhae':None,
  'human_e072_verifier':verified,'verified_gate_sha256':sha(GATE),
  'reused_original_e074_sources':True,'training_regime':'offline-only; no online RL or native game acts',
  'not_heldout_evaluation':True})
with FREEZE.open('x') as f:json.dump(freeze,f,indent=2)
print('E074_FOUR_ARM_TRAIN_SUCCESS',str(FREEZE),'sha256',sha(FREEZE),flush=True)
PY
if [ -e "$WORK/E074_OFFLINE_POLICY_PROBE.json" ];then
  echo "E074_OFFLINE_PROBE_EXISTS_NO_REWRITE"
else
  "$PY" "$ROOT/tools/e074_offline_policy_probe.py" --root "$ROOT" --work "$WORK"
fi
echo "E074_OFFLINE_FROZEN_AND_SOURCE_FIVE_ONLY_DIAGNOSTIC_DONE"
