#!/bin/bash
#SBATCH --job-name=e074_reward_audit
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --time=00:30:00
set -euo pipefail
export OMP_NUM_THREADS=2
PY=/home-mscluster/astrauss/arc26/.venv/bin/python
"$PY" - <<'PY'
import json,collections
from pathlib import Path
import pyarrow.dataset as ds
p=Path('/home-mscluster/astrauss/e074_human_training/human_snapshot')
l=json.loads((p/'E068_HUMAN_DATA_LOCK.json').read_text())
assert l['state']=='VERIFIED' and l['revision']=='455b7c58eaa9d5ea05f91cd1b5b603121599e758'
data=ds.dataset([str(x) for x in sorted((p/'data').glob('*.parquet'))],format='parquet')
train=('sb26','s5i5','lf52','tn36','g50t')
scan=data.scanner(columns=['env','guid','trajectory'],filter=ds.field('env').isin(train),batch_size=1)
sessions=collections.Counter();adv=collections.Counter();acts=collections.Counter();errors=collections.Counter();pairs=collections.Counter()
for batch in scan.to_batches():
 for row in batch.to_pylist():
  family=row['env'];sessions[family]+=1
  events=json.loads(row['trajectory'])
  prev=None
  for ev in events:
   d=ev.get('data',ev) if isinstance(ev,dict) else None
   if not isinstance(d,dict):prev=None;errors['no_event_data']+=1;continue
   level=d.get('levels_completed');action=d.get('action_input') or {}
   if level is None:prev=None;errors['no_level']+=1;continue
   a=action.get('id',action.get('action')) if isinstance(action,dict) else action
   try:aid=int(str(a).split('.')[-1].replace('ACTION',''))
   except Exception:errors['invalid_action']+=1;prev=None;continue
   if aid==0 or d.get('full_reset',False):
    prev=int(level);continue
   if prev is not None:
    step=max(0,int(level)-prev)
    if step:
     adv[family]+=step;acts[str(aid)]+=step;pairs[(family,str(aid))]+=step
   prev=int(level)
print('SELECTED_RAW_SESSIONS',json.dumps(sessions,sort_keys=True),flush=True)
print('RAW_LEVEL_ADVANCEMENTS_BY_FAMILY',json.dumps(adv,sort_keys=True),flush=True)
print('REWARD_ACTION_TYPES',json.dumps(acts,sort_keys=True),flush=True)
print('FAMILY_REWARD_ACTION_TYPES',dict((f+':'+a,v) for (f,a),v in sorted(pairs.items())),flush=True)
print('RAW_PARSING_WARNINGS',dict(errors),flush=True)
print('RAW_PRELIM_GATES',{
 'sessions_min20':sum(sessions.values())>=20,
 'advances_min30':sum(adv.values())>=30,
 'success_families_min4':sum(v>0 for v in adv.values())>=4,
 'positive_click_and_primitive':acts['6']>0 and sum(v for k,v in acts.items() if k!='6')>0,
 'all_five_families':set(sessions)==set(train)
},flush=True)
PY