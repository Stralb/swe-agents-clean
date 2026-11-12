#!/bin/bash
#SBATCH --job-name=e074_human_schema
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:15:00
set -euo pipefail
export OMP_NUM_THREADS=2
PY=/home-mscluster/astrauss/arc26/.venv/bin/python
SNAP=/home-mscluster/astrauss/e074_human_training/human_snapshot
"$PY" - "$SNAP" <<'PY'
import sys,json,collections
from pathlib import Path
import pyarrow.dataset as ds
root=Path(sys.argv[1])
lock=json.loads((root/'E068_HUMAN_DATA_LOCK.json').read_text())
if lock['state']!='VERIFIED' or lock['revision']!='455b7c58eaa9d5ea05f91cd1b5b603121599e758':
 raise RuntimeError('Dataset revision/hash state not locked')
z=ds.dataset([str(x) for x in sorted((root/'data').glob('*.parquet'))],format='parquet')
print('TOTAL_ROWS',z.count_rows(),flush=True)
print('SCHEMA',z.schema,flush=True)
print('ENV_COUNTS',collections.Counter(x['env'] for b in z.scanner(columns=['env'],batch_size=200).to_batches() for x in b.to_pylist()),flush=True)
train=('sb26','s5i5','lf52','tn36','g50t')
sc=z.scanner(columns=['env','guid','trajectory'],filter=ds.field('env').isin(train),batch_size=1)
counts=collections.Counter()
for b in sc.to_batches():
 for row in b.to_pylist():
  fam=row['env']; counts[fam]+=1
  if counts[fam]>1:continue
  raw=row['trajectory']
  events=json.loads(raw) if isinstance(raw,str) else raw
  print('SAMPLE',fam,'session_events',len(events),flush=True)
  for i,event in enumerate(events[:6]):
   d=event.get('data',event) if isinstance(event,dict) else None
   if not isinstance(d,dict):print('EVENT',i,'type',type(event).__name__);continue
   print('EVENT',i,'keys',sorted(d.keys()),'action_type',type(d.get('action_input')).__name__,
     'action',str(d.get('action_input'))[:180],'level',d.get('levels_completed'),'state',d.get('state'),
     'legal',str(d.get('available_actions'))[:160],
     'frame_type',type(d.get('frame')).__name__,flush=True)
print('TRAIN_COUNTS',dict(counts),flush=True)
print('FROZEN_SPLIT',train,flush=True)
PY