#!/bin/bash
#SBATCH --job-name=arno_choice_diag
#SBATCH --partition=stampede
#SBATCH --time=00:03:00
#SBATCH --mem=1G
python3 - <<'PY'
import csv,collections,json
from pathlib import Path
root=Path.home()/'research_artifacts'
a=root/'implementation_choice_phase1_v1_0_49121/01_ELIGIBLE_73_PCS_45_CASES.csv'
b=root/'implementation_choice_phase1_v1_0_49121/02_CASE_SPLIT_FROZEN.csv'
with a.open(encoding='utf-8-sig',newline='') as f:p=list(csv.DictReader(f))
with b.open(encoding='utf-8-sig',newline='') as f:c=list(csv.DictReader(f))
q={'eligible_rows':len(p),'partitions':dict(collections.Counter(x['Study Partition'] for x in p)),
'cases':len(c),'split_counts':dict(collections.Counter(x['Split'] for x in c)),
'first':{k:p[0][k] for k in ('Study Partition','Study Producing Change ID','Case ID')}}
out=root/'mcp_uploads/jobs/arno_choice_diag_20261028/COUNTS.json'
out.write_text(json.dumps(q,indent=2)+'\n')
print(json.dumps(q))
PY