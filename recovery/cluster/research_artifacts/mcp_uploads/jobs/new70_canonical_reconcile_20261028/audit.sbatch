#!/bin/bash
#SBATCH --job-name=arno_new70_canonical_audit
#SBATCH --partition=stampede
#SBATCH --time=00:05:00
#SBATCH --mem=2G
python3 - <<'PY'
from pathlib import Path
import csv,sqlite3,collections,json,datetime
root=Path.home()/'research_artifacts'
base=Path.home()/'new/malicious-issue-miner-rate-smart/data/final-study-snapshot-20260829/manual-review/new70-step1'
path=base/'Step1_Canonical_Findings_NEW70.csv'
with path.open(encoding='utf-8-sig',newline='') as f:
 data=list(csv.DictReader(f))
con=sqlite3.connect('file:'+str(root/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite')+'?mode=ro',uri=True)
links={r[0] for r in con.execute("SELECT canonical_finding_id FROM arno_canonical_id_pc_links WHERE cohort='new70'")}
con.close()
ids={r['Canonical Finding ID'] for r in data}
unmapped=[r for r in data if r['Canonical Finding ID'] not in links]
counts=collections.Counter(r['Case ID'] for r in unmapped)
report={'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'path':str(path),'candidate_rows':len(data),'candidate_unique_ids':len(ids),
 'frozen_mapped_ids':len(links),'mapped_ids_in_candidate':len(ids&links),
 'frozen_mapped_not_in_candidate':sorted(links-ids),
 'other_candidate_count':len(unmapped),'unmapped_by_case':dict(counts),
 'case17701_candidate_rows':sum(r['Case ID']=='17701' for r in data),
 'case17701_unmapped_count':counts['17701'],
 'case17701_statuses':dict(collections.Counter(r['QC Status'] for r in data if r['Case ID']=='17701')),
 'other_unmapped_status_counts':dict(collections.Counter(r['QC Status'] for r in unmapped if r['Case ID']!='17701')),
 'all_candidate_qc_status':dict(collections.Counter(r['QC Status'] for r in data)),
 'first_20_other_unmapped':[(r['Canonical Finding ID'],r['Case ID'],r['QC Status']) for r in unmapped if r['Case ID']!='17701'][:20],
}
out=root/'mcp_uploads/jobs/new70_canonical_reconcile_20261028'
out.mkdir(parents=True,exist_ok=True)
(out/'CANONICAL_RECONCILIATION.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
PY