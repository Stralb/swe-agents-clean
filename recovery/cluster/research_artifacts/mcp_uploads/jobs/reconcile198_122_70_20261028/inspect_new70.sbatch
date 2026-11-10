#!/bin/bash
#SBATCH --job-name=arno_reconcile70
#SBATCH --partition=stampede
#SBATCH --time=00:08:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
python3 - <<'PY'
import collections,csv,datetime,hashlib,json,sqlite3
from pathlib import Path
home=Path.home()
out=home/'research_artifacts/mcp_uploads/jobs/reconcile198_122_70_20261028'
out.mkdir(parents=True,exist_ok=True)
db=home/'new/malicious-issue-miner-rate-smart/data/final-study-snapshot-20260829/full3809-scanner-complete-20260829.db'
source=home/'research_artifacts/new70_frozen_methodology_20260829T091932Z/03_STAGE4B_BLIND/stage4b_diff_size_metrics_NEW70.csv'
con=sqlite3.connect('file:'+str(db)+'?mode=ro',uri=True,timeout=20)
con.execute('PRAGMA query_only=ON')
with source.open('r',encoding='utf-8-sig',newline='') as f:
  entries=list(csv.DictReader(f))
ids=[int(r['Case ID']) for r in entries]
assert len(ids)==70 and len(set(ids))==70
sql='''SELECT c.id, c.status,c.downstream_signal,c.final_label,c.review_notes,
COUNT(sf.id) AS sf_rows,
SUM(CASE WHEN sf.introduced=1 THEN 1 ELSE 0 END) AS introduced_rows,
GROUP_CONCAT(DISTINCT sf.scanner) AS scanners,
GROUP_CONCAT(DISTINCT CASE WHEN sf.introduced=1 THEN sf.rule_id ELSE NULL END) AS introduced_rules,
(SELECT COUNT(*) FROM scanner_runs sr WHERE sr.case_id=c.id) AS scanner_runs,
(SELECT GROUP_CONCAT(DISTINCT sr.status) FROM scanner_runs sr WHERE sr.case_id=c.id) AS run_statuses
FROM cases c LEFT JOIN scanner_findings sf ON sf.case_id=c.id
WHERE c.id=?
GROUP BY c.id,c.status,c.downstream_signal,c.final_label,c.review_notes'''
fields=['case_id','db_status','downstream_signal','db_final_label','review_notes','sf_rows','introduced_rows','scanners','introduced_rules','scanner_runs','run_statuses']
rows=[]
for i in ids:
  res=con.execute(sql,(i,)).fetchone()
  if res is None: rows.append({'case_id':i,'db_status':'MISSING_CASE'})
  else:rows.append(dict(zip(fields,res)))
for r in rows:r['raw_positive_criteria']=bool(r.get('introduced_rows') and r['introduced_rows']>0)
csv_out=out/'NEW70_SCANNER_RECONCILIATION.csv'
with csv_out.open('x',encoding='utf-8',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields+['raw_positive_criteria'])
 w.writeheader();w.writerows(rows)
missing=[r for r in rows if not r['raw_positive_criteria']]
report={
 'source_db':str(db),
 'new70_frozen_source':str(source),
 'new70_count':len(ids),
 'new70_with_introduced_findings':len(rows)-len(missing),
 'new70_no_introduced_findings':len(missing),
 'missing_ids':[r['case_id'] for r in missing],
 'missing_case_details':missing,
 'all_rows_summary_by_db_status':dict(collections.Counter(r['db_status'] for r in rows)),
 'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
 'csv_sha256':hashlib.sha256(csv_out.read_bytes()).hexdigest(),
 'read_only':True,
 'collected_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()
}
(out/'NEW70_RECONCILIATION_REPORT.json').write_text(json.dumps(report,indent=2,default=str)+'\n')
con.close()
print(json.dumps({k:report[k] for k in ('new70_count','new70_with_introduced_findings','new70_no_introduced_findings','missing_ids','all_rows_summary_by_db_status')},indent=2))
PY