#!/bin/bash
#SBATCH --job-name=arno_c6hash_audit
#SBATCH --partition=stampede
#SBATCH --time=00:05:00
#SBATCH --mem=2G
python3 - <<'PY'
from pathlib import Path
import sqlite3,zlib,hashlib,csv,io,json
R=Path.home()/'research_artifacts'
O=R/'mcp_uploads/jobs/arno_c6_context_reconciliation_v6_20261028'
O.mkdir(parents=True,exist_ok=True)
c=sqlite3.connect(f'file:{R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"}?mode=ro',uri=True)
files={k:zlib.decompress(v) for k,v in c.execute('SELECT source_path,content_zlib FROM arno_evidence_assets')}
get=lambda ending:next(b for k,b in files.items() if k.endswith(ending))
raw=get('C5_CONTEXT_190_FROZEN.csv');correct=get('C6_CONTEXT_QC_CORRECTIONS.csv')
expected='cecf7a170cb917e118e000af973d24e56e24e33afccd387a04a44e9629408015'
sha=lambda b:hashlib.sha256(b).hexdigest()
text=raw.decode('utf-8-sig')
lines=text.splitlines(keepends=True)
header=next(csv.reader(io.StringIO(text)))
casekey=next((x for x in header if x in ('case_id','control_case_id','matched_case_id')),None)
records=list(csv.DictReader(io.StringIO(text)))
hits=[dict(x) for x in records if '12897' in x.values()]
changefield='human_review_present_before_merge'
choices=[]
for value in ('MISSING','','missing','Missing','NA','N/A','None','null','Unknown','NOT_VERIFIABLE'):
 for newline in ('\r\n','\n'):
  for quoting in (csv.QUOTE_MINIMAL,csv.QUOTE_ALL):
   linesout=io.StringIO(newline='')
   w=csv.DictWriter(linesout,fieldnames=header,lineterminator=newline,quoting=quoting)
   w.writeheader()
   for row in records:
    if '12897' in row.values():
     row=dict(row);row[changefield]=value
    w.writerow(row)
   candidate=linesout.getvalue().encode()
   choices.append({'value':value,'newline':repr(newline),'quoting':quoting,'sha':sha(candidate),'matches':sha(candidate)==expected})
res={'status':'COMPLETE','original_C5_context_sha256':sha(raw),'C6_reported_context_sha256':expected,
 'C6_QC_correction_source_sha256':sha(correct),'header':header,
 'case_identifier_column':casekey,'case_12897_original_rows':hits,
 'candidate_count':len(choices),'matching_candidates':[x for x in choices if x['matches']],
 'C6_context_reconstruction_status':'MATCHED' if any(x['matches'] for x in choices) else 'NOT_BYTE_IDENTICAL_UNDER_TESTED_SINGLE_FIELD_FORMATS',
 'c6_correction_line':correct.decode('utf8','replace')}
(O/'C6_CONTEXT_SHA_AUDIT.json').write_text(json.dumps(res,indent=2)+'\n')
print(json.dumps(res,indent=2),flush=True)
PY