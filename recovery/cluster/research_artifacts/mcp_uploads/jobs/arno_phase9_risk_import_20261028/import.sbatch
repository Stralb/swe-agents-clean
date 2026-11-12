#!/bin/bash
#SBATCH --job-name=arno_phase9_risk
#SBATCH --partition=stampede
#SBATCH --time=00:07:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
python3 - <<'PY'
import base64,lzma,json,hashlib,sqlite3,datetime,collections
from pathlib import Path
root=Path.home()/'research_artifacts'
db=root/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'
inp=root/'mcp_uploads/arno_master_20261028/new70_phase9_risk_core_lzma_base64.txt'
out=root/'mcp_uploads/jobs/arno_phase9_risk_import_20261028'
out.mkdir(parents=True,exist_ok=True)
report={'stage':'Phase 9 original risk classifications / frozen first pass and QC','status':'STARTED',
'origin_local_zip_sha256':'2517a3173cfc1d7dfd436cdf8a6dc7902692cdbc2e4110bf21154b7b59fabe0a',
'original_phase9_csv_sha256':'72d9f7c5d9f7983adb92940f65b5393b2b7231fffc4d041f44cdac19bb1fefe9'}
try:
 compressed=base64.b64decode(inp.read_text().strip(),validate=True)
 assert hashlib.sha256(compressed).hexdigest()=='018d7f97d9bb890f2f9c058a980ced75452e06fd70902a6c6d7b05a152b30d4a'
 original=lzma.decompress(compressed)
 assert hashlib.sha256(original).hexdigest()=='28251af152ea0107676c3becc38f8988b7cc76054a520ebddcfad03e5cb3fa23'
 data=json.loads(original.decode('utf-8'))
 expected_cols=['Case ID','First-pass Risk Label','First-pass Rationale','QC Review / Correction','QC Note','Final Provisional Risk Label','Final Risk Rationale','Evidence Channels Considered','Remaining Uncertainty','Human Review / Correction']
 assert data['columns']==expected_cols
 rows=[dict(zip(expected_cols,row)) for row in data['rows']]
 ids={int(r['Case ID']) for r in rows}
 assert len(rows)==len(ids)==70
 counts1=collections.Counter(r['First-pass Risk Label'] for r in rows)
 countsF=collections.Counter(r['Final Provisional Risk Label'] for r in rows)
 assert counts1=={'Benign ordinary':66,'Benign ambiguous':4}
 assert countsF=={'Benign ordinary':68,'Benign ambiguous':2}
 corrections={int(r['Case ID']) for r in rows if r['QC Review / Correction']}
 assert corrections=={16633,33183}
 remaining={int(r['Case ID']) for r in rows if r['Final Provisional Risk Label']=='Benign ambiguous'}
 assert remaining=={16791,20086}
 assert all(not r['Human Review / Correction'] for r in rows)
 con=sqlite3.connect(str(db),timeout=60)
 con.execute('PRAGMA busy_timeout=60000')
 con.execute('PRAGMA foreign_keys=ON')
 frozen_ids={r[0] for r in con.execute('SELECT case_id FROM arno_new70_source_inputs')}
 assert frozen_ids==ids,'Phase9 cohort does not match frozen NEW70'
 assert con.execute('SELECT COUNT(*) FROM arno_classifications').fetchone()[0]==122
 assert con.execute('SELECT COUNT(*) FROM arno_excluded_cases').fetchone()[0]==16
 con.execute('''CREATE TABLE arno_new70_phase9_risk(
   case_id INTEGER PRIMARY KEY REFERENCES arno_new70_source_inputs(case_id),
   first_pass_risk_label TEXT NOT NULL,
   first_pass_rationale TEXT NOT NULL,
   qc_correction TEXT,
   qc_note TEXT,
   final_risk_label TEXT NOT NULL,
   final_risk_rationale TEXT NOT NULL,
   evidence_channels_considered TEXT,
   remaining_uncertainty TEXT,
   human_review_correction TEXT,
   original_row_json TEXT NOT NULL,
   source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
   label_kind TEXT NOT NULL DEFAULT 'PROVISIONAL_ORIGINAL_PHASE9'
 )''')
 con.execute('''CREATE TABLE arno_new70_phase9_risk_events(
    case_id INTEGER NOT NULL REFERENCES arno_new70_phase9_risk(case_id),
    event_stage TEXT NOT NULL CHECK(event_stage IN ('first_pass','qc_correction','final')),
    label TEXT NOT NULL,notes TEXT,source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
    PRIMARY KEY(case_id,event_stage))''')
 sourcekey='new70_phase9_risk_core10_frozen'
 con.execute('INSERT INTO arno_sources VALUES(?,?,?,?,?,?,?,?,?)',(
   sourcekey,'frozen_phase9_manual_risk','NEW70 Phase9 final 70-case risk labels/rationales/QC',
   'User-supplied ZIP NEW70_Phase9_Risk_Assessment_FINAL_v1.0.zip, member risk CSV',
   hashlib.sha256(original).hexdigest(),'xz/json-utf8',compressed,'EXACT_CORE10_FIELD_ROUNDTRIP_VERIFIED',
   'Ten original named risk/annotation fields embedded in a source-faithful JSON field table. Original ZIP and complete 16-column CSV remain locally supplied; outer ZIP SHA256 '+report['origin_local_zip_sha256']+'; CSV SHA256 '+report['original_phase9_csv_sha256']+'; Case Evidence Summary and row SHA columns not yet embedded on cluster.'
 ))
 for r in rows:
  cid=int(r['Case ID'])
  con.execute('INSERT INTO arno_new70_phase9_risk VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(
   cid,r['First-pass Risk Label'],r['First-pass Rationale'],r['QC Review / Correction'],r['QC Note'],
   r['Final Provisional Risk Label'],r['Final Risk Rationale'],
   r['Evidence Channels Considered'],r['Remaining Uncertainty'],
   r['Human Review / Correction'],json.dumps(r,ensure_ascii=False,sort_keys=True),sourcekey,'PROVISIONAL_ORIGINAL_PHASE9'))
  for stage,label,note in (
    ('first_pass',r['First-pass Risk Label'],r['First-pass Rationale']),
    ('final',r['Final Provisional Risk Label'],r['Final Risk Rationale'])):
    con.execute('INSERT INTO arno_new70_phase9_risk_events VALUES(?,?,?,?,?)',(
      cid,stage,label,note,sourcekey))
  if r['QC Review / Correction']:
    con.execute('INSERT INTO arno_new70_phase9_risk_events VALUES(?,?,?,?,?)',(
      cid,'qc_correction',r['Final Provisional Risk Label'],r['QC Note'],sourcekey))
 con.execute("UPDATE arno_new70_source_inputs SET classification_status='PHASE9_VERIFIED_CORE_FIELDS' WHERE case_id IN (SELECT case_id FROM arno_new70_phase9_risk)")
 con.execute("UPDATE arno_stage_ledger SET status='partial',detail='All 70 frozen Phase9 risk labels and original/finite QC rationales imported (68 ordinary;2 ambiguous), human review empty; awaiting full raw archive embedding and other phase outputs',last_updated_utc=? WHERE stage_number=3",(datetime.datetime.now(datetime.timezone.utc).isoformat(),))
 con.commit()
 report['counts']={
  'new70_risk_cases':con.execute('SELECT COUNT(*) FROM arno_new70_phase9_risk').fetchone()[0],
  'annotation_events':con.execute('SELECT COUNT(*) FROM arno_new70_phase9_risk_events').fetchone()[0],
  'corrected':con.execute("SELECT COUNT(*) FROM arno_new70_phase9_risk_events WHERE event_stage='qc_correction'").fetchone()[0],
  'first122_unchanged':con.execute('SELECT COUNT(*) FROM arno_classifications').fetchone()[0]}
 report['source_roundtrip_ok']=hashlib.sha256(lzma.decompress(con.execute('SELECT embedded_bytes FROM arno_sources WHERE source_key=?',(sourcekey,)).fetchone()[0])).hexdigest()==hashlib.sha256(original).hexdigest()
 report['fk_errors']=sum(len(con.execute('PRAGMA foreign_key_check('+t+')').fetchall()) for t in ('arno_new70_phase9_risk','arno_new70_phase9_risk_events'))
 con.close()
 if report['counts']!={'new70_risk_cases':70,'annotation_events':142,'corrected':2,'first122_unchanged':122} or not report['source_roundtrip_ok'] or report['fk_errors']:
  raise ValueError('Post-import QC failed')
 report['status']='COMPLETE'
except Exception as e:
 report['status']='FAILED';report['error']=type(e).__name__+': '+str(e)
 raise
finally:
 (out/'IMPORT_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(report,indent=2,ensure_ascii=False),flush=True)
PY