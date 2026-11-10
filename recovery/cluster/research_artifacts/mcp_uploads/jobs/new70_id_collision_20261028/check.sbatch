#!/bin/bash
#SBATCH --job-name=arno_new70_id_test
#SBATCH --partition=stampede
#SBATCH --time=00:05:00
#SBATCH --mem=2G
python3 - <<'PY'
from pathlib import Path
import csv,sqlite3,json,collections
root=Path.home()/'research_artifacts'
src=Path.home()/'new/malicious-issue-miner-rate-smart/data/final-study-snapshot-20260829/manual-review/new70-step1/Step1_Canonical_Findings_NEW70.csv'
with src.open(encoding='utf-8-sig',newline='') as f:
 rows=list(csv.DictReader(f))
candidate={r['Canonical Finding ID']:r for r in rows}
con=sqlite3.connect('file:'+str(root/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite')+'?mode=ro',uri=True)
links=list(con.execute("SELECT canonical_finding_id,case_id,producing_change_id FROM arno_canonical_id_pc_links WHERE cohort='new70'"))
con.close()
matched=[];mismatch=[];missing=[]
for cf,case,pc in links:
 if cf not in candidate:missing.append([cf,case,pc])
 elif int(candidate[cf]['Case ID'])==case:matched.append([cf,case,pc])
 else:mismatch.append([cf,case,int(candidate[cf]['Case ID']),pc])
counts={
 'frozen_provenance_links':len(links),
 'candidate_row_ids':len(candidate),
 'id_and_case_both_match':len(matched),
 'id_matches_but_case_disagrees':len(mismatch),
 'frozen_id_absent_from_candidate':len(missing),
 'mismatch_examples':mismatch[:25],
 'matched_case_ids':dict(collections.Counter(str(x[1]) for x in matched)),
 'candidate_17701_count':sum(int(r['Case ID'])==17701 for r in rows),
 'frozen_provenance_17701_count':sum(case==17701 for _,case,_ in links)
}
out=root/'mcp_uploads/jobs/new70_id_collision_20261028'
out.mkdir(parents=True,exist_ok=True)
(out/'ID_ASSIGNMENT_COMPARISON.json').write_text(json.dumps(counts,indent=2)+'\n')
print(json.dumps(counts,indent=2)[:7000])
PY