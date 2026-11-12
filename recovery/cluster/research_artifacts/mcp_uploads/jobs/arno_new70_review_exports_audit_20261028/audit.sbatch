#!/bin/bash
#SBATCH --job-name=arno_new70_exports
#SBATCH --partition=stampede
#SBATCH --time=00:04:00
#SBATCH --mem=2G
python3 - <<'PY'
import csv,json,hashlib,collections
from pathlib import Path
root=Path.home()/'research_artifacts'
p=Path.home()/'new/malicious-issue-miner-rate-smart/data/final-study-snapshot-20260829/manual-review'
out=root/'mcp_uploads/jobs/arno_new70_review_exports_audit_20261028'
out.mkdir(parents=True,exist_ok=True)
report={}
for name in ('new70_review_cases.csv','new70_review_findings.csv'):
 f=p/name
 with f.open(encoding='utf-8-sig',newline='') as fd:
  reader=csv.DictReader(fd);rows=list(reader);cols=reader.fieldnames
 item={'path':str(f),'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),
       'rows':len(rows),'fields':cols,'case_id_fields':[c for c in cols if 'case' in c.lower() and 'id' in c.lower()],
       'classification_fields':[c for c in cols if any(t in c.lower() for t in ('risk','final','classif','review','qc','status','verdict','canonical'))],
       'sample_first_row_keys':{k:str(rows[0].get(k,''))[:140] for k in cols[:22]} if rows else {}}
 for col in item['classification_fields'][:12]:
  freq=collections.Counter(str(r.get(col,''))[:100] for r in rows)
  if len(freq)<=15:item.setdefault('value_counts',{})[col]=dict(freq)
 report[name]=item
(out/'EXPORT_AUDIT.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:{x:v for x,v in val.items() if x not in ('sample_first_row_keys','value_counts')} for k,val in report.items()},indent=2))
PY