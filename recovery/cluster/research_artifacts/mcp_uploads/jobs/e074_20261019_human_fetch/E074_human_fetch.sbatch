#!/bin/bash
#SBATCH --job-name=E074_human_fetch
#SBATCH --partition=batch
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/E074_human_fetch_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/E074_human_fetch_%j.err
set -euo pipefail
umask 077
export E074_WORK="/home-mscluster/astrauss/e074_human_training"
export E074_PYTHON="/home-mscluster/astrauss/arc26/.venv/bin/python"
if [ ! -x "$E074_PYTHON" ]; then echo "E074 Python missing"; exit 53; fi
export HF_HOME="$E074_WORK/hf_cache"
export HF_HUB_DISABLE_TELEMETRY=1
export PYTHONUNBUFFERED=1
"$E074_PYTHON" - --dir "$E074_WORK/human_snapshot" <<'E074_EXACT_ACQUIRE_PY'
"""Immutable, hash-audited ARC public human Parquet acquisition for Slurm nodes.
This NEVER runs during import or local model training. Unavailable network is an
explicit failure, not a silently substituted synthetic or teacher dataset.
"""
from __future__ import annotations
import argparse,hashlib,json,os,re
from pathlib import Path
REPO='magic-sword/arc_agi_3_public_demo_human_testing'
REV='455b7c58eaa9d5ea05f91cd1b5b603121599e758'
LOCK='E068_HUMAN_DATA_LOCK.json'

def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  while b:=f.read(2<<20):h.update(b)
 return h.hexdigest()

def preflight(directory,revision=REV):
 d=Path(directory);d.mkdir(parents=True,exist_ok=True)
 if not re.fullmatch('[0-9a-f]{40}',revision):raise ValueError('full revision SHA required')
 lock=d/LOCK
 if lock.exists():
  old=json.loads(lock.read_text())
  if old['repo']!=REPO or old['revision']!=revision:
   raise PermissionError('Existing acquisition directory locked to another revision')
 else:
  if list(d.rglob('*.parquet')):raise PermissionError('Preexisting unmanifested Parquet files')
  tmp=lock.with_suffix('.tmp')
  tmp.write_text(json.dumps({'repo':REPO,'revision':revision,'state':'FETCH_PENDING','shards':[]},indent=2)+'\n')
  os.replace(tmp,lock)
 return lock

def verify(directory,revision=REV):
 d=Path(directory);l=d/LOCK
 if not l.exists():raise FileNotFoundError('Locked download manifest missing')
 info=json.loads(l.read_text())
 if info['repo']!=REPO or info['revision']!=revision or info['state']!='VERIFIED':
  raise RuntimeError('Human snapshot is not completely verified')
 files=sorted((d/'data').glob('*.parquet'))
 if not files or set(x.name for x in files)!=set(x['file'].split('/')[-1] for x in info['shards']):
  raise RuntimeError('Human Parquet shard inventory mismatch')
 for row in info['shards']:
  p=d/row['file']
  if p.stat().st_size!=row['bytes'] or sha(p)!=row['sha256']:
   raise RuntimeError('Human Parquet shard digest mismatch')
  with open(p,'rb') as f:
   if f.read(4)!=b'PAR1':raise ValueError('Invalid Parquet magic header')
 return info

def download(directory,revision=REV):
 lock=preflight(directory,revision);d=Path(directory)
 if json.loads(lock.read_text())['state']=='VERIFIED':return verify(d,revision)
 from huggingface_hub import snapshot_download
 snapshot_download(repo_id=REPO,repo_type='dataset',revision=revision,local_dir=str(d),
   allow_patterns=['data/*.parquet','README.md'])
 files=sorted((d/'data').glob('*.parquet'))
 if not files:raise RuntimeError('Hugging Face snapshot returned no Parquet shards')
 shards=[]
 for p in files:
  with open(p,'rb') as f:
   if f.read(4)!=b'PAR1':raise ValueError(f'Bad Parquet header: {p.name}')
  shards.append({'file':str(p.relative_to(d)),'bytes':p.stat().st_size,'sha256':sha(p)})
 info={'repo':REPO,'revision':revision,'state':'VERIFIED','shards':shards,
       'total_bytes':sum(x['bytes'] for x in shards),'source_type':'public human sessions, no private benchmark or oracle API'}
 tmp=lock.with_suffix('.tmp');tmp.write_text(json.dumps(info,indent=2)+'\n');os.replace(tmp,lock)
 return verify(d,revision)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--dir',type=Path,required=True)
 p.add_argument('--revision',default=REV);p.add_argument('--verify-only',action='store_true');a=p.parse_args()
 print(json.dumps(verify(a.dir,a.revision) if a.verify_only else download(a.dir,a.revision),indent=2),flush=True)
E074_EXACT_ACQUIRE_PY
echo E074_SNAPSHOT_ACQUISITION_AND_SHA256_VERIFICATION_COMPLETED
