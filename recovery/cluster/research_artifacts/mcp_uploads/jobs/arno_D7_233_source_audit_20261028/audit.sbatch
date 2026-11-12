#!/bin/bash
#SBATCH --job-name=arno_d7_233_qc
#SBATCH --partition=stampede
#SBATCH --time=00:05:00
#SBATCH --mem=2G
python3 - <<'PY'
import csv,sqlite3,hashlib,collections,json
from pathlib import Path
root=Path.home()/'research_artifacts'
base=root/'D7_FINAL_M_ROOTS_233_WITH_COHORTS.csv'
duplicate=root/'D7_FINAL_M_ROOTS_233_WITH_COHORTS(1).csv'
out=root/'mcp_uploads/jobs/arno_D7_233_source_audit_20261028'
out.mkdir(parents=True,exist_ok=True)
with base.open(encoding='utf-8-sig',newline='') as f:
 rd=csv.DictReader(f);rows=list(rd);columns=rd.fieldnames
unique={r['root_id'] for r in rows}
con=sqlite3.connect('file:'+str(root/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite')+'?mode=ro',uri=True)
master={r[0]:r[1] for r in con.execute('SELECT root_id,case_id FROM arno_root_decisions')}
con.close()
missing=sorted(unique-set(master))
wrong_case=[(r['root_id'],r['case_id'],master.get(r['root_id'])) for r in rows if r['root_id'] in master and int(r['case_id'])!=master[r['root_id']]]
qc={
 'source':str(base),'source_bytes':base.stat().st_size,'source_sha256':hashlib.sha256(base.read_bytes()).hexdigest(),
 'duplicate_source_identical':base.read_bytes()==duplicate.read_bytes(),
 'rows':len(rows),'unique_root_ids':len(unique),'unique_cases':len({r['case_id'] for r in rows}),
 'columns':columns,'root_ids_absent_from_master_342':missing,'case_identity_mismatches':wrong_case,
 'route_counts':dict(collections.Counter(r['final_route'] for r in rows)),
 'tier_counts':dict(collections.Counter(r['final_tier'] for r in rows)),
 'cohort_counts':dict(collections.Counter(r['d7_m_cohort'] for r in rows)),
 'pass_a_route_counts':dict(collections.Counter(r['pass_a_route'] for r in rows)),
 'pass_b_route_counts':dict(collections.Counter(r['pass_b_route'] for r in rows)),
 'evidence_complete_counts':dict(collections.Counter(r['final_evidence_complete'] for r in rows)),
 'mandatory_d4_counts':dict(collections.Counter(r['mandatory_d4'] for r in rows)),
 'adjudication_rationale_nonempty':sum(bool(r['adjudication_rationale'].strip()) for r in rows),
 'not_in_final_233':len(set(master)-unique),'not_in_final_233_sample':sorted(set(master)-unique)[:20],
 'sample':[{k:r[k] for k in ('root_id','case_id','d7_m_cohort','final_route','final_tier','adjudication_rationale')} for r in rows[:4]]
}
(out/'D7_233_SOURCE_AUDIT.json').write_text(json.dumps(qc,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:v for k,v in qc.items() if k not in ('columns','sample','not_in_final_233_sample')},indent=2))
PY