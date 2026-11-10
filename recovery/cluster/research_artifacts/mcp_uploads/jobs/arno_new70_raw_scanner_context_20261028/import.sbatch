#!/bin/bash
#SBATCH --job-name=arno_new70_raw_scanner
#SBATCH --partition=stampede
#SBATCH --time=00:10:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
python3 - <<'PY'
from pathlib import Path
import csv,io,datetime,json,zlib,hashlib,sqlite3,collections
root=Path.home()/'research_artifacts'
source=root/'new70_frozen_methodology_20260829T091932Z/90_LOCKED_FOR_LATER'
master=root/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'
out=root/'mcp_uploads/jobs/arno_new70_raw_scanner_context_20261028'
out.mkdir(parents=True,exist_ok=True)
src={
 'NEW70_20260829_frozen_scanner_raw_255':source/'scanner_findings_raw_NEW70.csv',
 'NEW70_20260829_frozen_context_70':source/'context_source_NEW70.csv',
 'NEW70_20260829_frozen_source_QC':root/'new70_frozen_methodology_20260829T091932Z/99_MANIFEST/QC_SUMMARY.json'
}
report={'status':'STARTED','stage':'frozen raw scanner audit and issue context inputs; not final causal vulnerability labels'}
try:
 blob={key:p.read_bytes() for key,p in src.items()}
 def data(key):return list(csv.DictReader(io.StringIO(blob[key].decode('utf-8-sig'))))
 findings=data('NEW70_20260829_frozen_scanner_raw_255')
 context=data('NEW70_20260829_frozen_context_70')
 qc=json.loads(blob['NEW70_20260829_frozen_source_QC'])
 ids={int(r['case_id']) for r in findings}
 ctxids={int(r['Case ID']) for r in context}
 rawids={int(r['raw_finding_id']) for r in findings}
 if not (len(findings)==len(rawids)==255 and len(context)==len(ctxids)==70 and ids==ctxids and qc['new_cases']==70 and qc['raw_scanner_findings']==255):
  raise ValueError('Source sizes/IDs do not match original QC')
 flag=collections.Counter(r['introduced'].strip() for r in findings)
 if flag!={'1':229,'0':26}:raise ValueError('Unexpected introduced counts '+str(flag))
 con=sqlite3.connect(str(master),timeout=60)
 con.execute('PRAGMA foreign_keys=ON')
 con.execute('PRAGMA busy_timeout=60000')
 masterids={r[0] for r in con.execute('SELECT case_id FROM arno_new70_source_inputs')}
 if ids!=masterids:raise ValueError('NEW70 frozen candidate IDs differ from mapped 70')
 con.execute('''CREATE TABLE arno_new70_scanner_raw_frozen(
   raw_finding_id INTEGER PRIMARY KEY,
   case_id INTEGER NOT NULL REFERENCES arno_new70_source_inputs(case_id),
   pr_id INTEGER NOT NULL,scanner TEXT NOT NULL,
   finding_type TEXT,severity TEXT,rule_id TEXT,cwe TEXT,
   file_path TEXT,line_number INTEGER,description TEXT,evidence TEXT,
   raw_json TEXT,introduced INTEGER NOT NULL CHECK(introduced IN(0,1)),
   created_at TEXT,original_row_json TEXT NOT NULL,
   source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
   evidence_stage TEXT NOT NULL DEFAULT 'RAW_FROZEN_NOT_FINAL')''')
 con.execute('''CREATE TABLE arno_new70_context_frozen(
   case_id INTEGER PRIMARY KEY REFERENCES arno_new70_source_inputs(case_id),
   review_number INTEGER NOT NULL,issue_author TEXT,
   author_association TEXT,human_review_before_merge TEXT,
   original_context_json TEXT NOT NULL,
   source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
 )''')
 for key,raw in blob.items():
  con.execute('INSERT INTO arno_sources VALUES(?,?,?,?,?,?,?,?,?)',(
   key,'frozen_aug29_new70_method_input',key,str(src[key]),hashlib.sha256(raw).hexdigest(),
   'zlib/bytes',zlib.compress(raw,9),'RAW_INPUT_BYTES_SHA_VERIFIED',
   'Preserve preliminary scanner findings introduced flags and context independently of final Phase6 labels.'))
 for r in findings:
  con.execute('INSERT INTO arno_new70_scanner_raw_frozen VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(
   int(r['raw_finding_id']),int(r['case_id']),int(r['pr_id']),r['scanner'],r['finding_type'],
   r['severity'],r['rule_id'],r['cwe'],r['file_path'],int(r['line']) if r.get('line') else None,
   r['description'],r['evidence'],r['raw_json'],int(r['introduced']),r['created_at'],
   json.dumps(r,sort_keys=True,ensure_ascii=False),
   'NEW70_20260829_frozen_scanner_raw_255','RAW_FROZEN_NOT_FINAL'))
 for r in context:
  con.execute('INSERT INTO arno_new70_context_frozen VALUES(?,?,?,?,?,?,?)',(
   int(r['Case ID']),int(r['Review #']),r['Issue Author'],
   r['Issue Author Association'],r['Human Review Present Before Merge'],
   json.dumps(r,sort_keys=True,ensure_ascii=False),'NEW70_20260829_frozen_context_70'))
 stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
 con.execute("UPDATE arno_stage_ledger SET detail=detail||'; 255 raw NEW70 scanner rows with introduced flag (229 true,26 false), 70 frozen context records preserved; distinct from final manual finding labels',last_updated_utc=? WHERE stage_number=4",(stamp,))
 con.commit()
 report['counts']={
 'raw_findings':con.execute('SELECT COUNT(*) FROM arno_new70_scanner_raw_frozen').fetchone()[0],
 'promoted_raw_rows':con.execute('SELECT COUNT(*) FROM arno_new70_scanner_raw_frozen WHERE introduced=1').fetchone()[0],
 'unpromoted_raw_rows':con.execute('SELECT COUNT(*) FROM arno_new70_scanner_raw_frozen WHERE introduced=0').fetchone()[0],
 'context_rows':con.execute('SELECT COUNT(*) FROM arno_new70_context_frozen').fetchone()[0],
 'first122':con.execute('SELECT COUNT(*) FROM arno_classifications').fetchone()[0]}
 report['source_integrity']={key:hashlib.sha256(zlib.decompress(con.execute('SELECT embedded_bytes FROM arno_sources WHERE source_key=?',(key,)).fetchone()[0])).hexdigest()==hashlib.sha256(raw).hexdigest() for key,raw in blob.items()}
 report['foreign_key_errors']=sum(len(con.execute('PRAGMA foreign_key_check('+t+')').fetchall()) for t in ('arno_new70_scanner_raw_frozen','arno_new70_context_frozen'))
 con.close()
 if report['counts']!={'raw_findings':255,'promoted_raw_rows':229,'unpromoted_raw_rows':26,'context_rows':70,'first122':122} or report['foreign_key_errors'] or not all(report['source_integrity'].values()):
  raise ValueError('Post-commit QC failed')
 report['status']='COMPLETE'
except Exception as exc:
 report['status']='FAILED';report['error']=type(exc).__name__+': '+str(exc)
 raise
finally:
 (out/'IMPORT_REPORT.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
 print(json.dumps(report,indent=2,ensure_ascii=False))
PY