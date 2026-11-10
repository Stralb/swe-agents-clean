#!/bin/bash
#SBATCH --job-name=arno_D7_M233_import
#SBATCH --partition=stampede
#SBATCH --time=00:10:00
#SBATCH --mem=2G
python3 - <<'PY'
import csv,sqlite3,hashlib,zlib,json,collections,datetime,io
from pathlib import Path
root=Path.home()/'research_artifacts'
src=root/'D7_FINAL_M_ROOTS_233_WITH_COHORTS.csv'
master=root/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'
out=root/'mcp_uploads/jobs/arno_master_D7_M233_import_v02_20261028'
out.mkdir(parents=True,exist_ok=True)
report={'status':'STARTED','scope':'Only D7 M-routed final adjudications (233/342), not all root decisions'}
try:
 raw=src.read_bytes()
 expected_sha='83e23d84dd572219fca5817588a91d1cc668f76178759b6430825fa590ee9573'
 if hashlib.sha256(raw).hexdigest()!=expected_sha:raise ValueError('D7 frozen source digest changed')
 rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
 ids={r['root_id'] for r in rows}
 if len(rows)!=233 or len(ids)!=233:raise ValueError('D7 row count or duplicate IDs')
 counts=collections.Counter(r['final_route'] for r in rows)
 tiers=collections.Counter(r['final_tier'] for r in rows)
 cohorts=collections.Counter(r['d7_m_cohort'] for r in rows)
 if counts!={'M':233} or cohorts!={'DISCOVERY_DERIVED':56,'NEW_HOLDOUT':177} or tiers!={'INCOMPLETE':24,'T3':33,'T4':128,'T1':32,'T2':12,'T5':4}:
  raise ValueError('D7 distribution differs from verified frozen audit')
 if any(not r['adjudication_rationale'].strip() for r in rows):raise ValueError('D7 rationale missing')
 con=sqlite3.connect(str(master),timeout=60)
 con.execute('PRAGMA busy_timeout=60000')
 con.execute('PRAGMA foreign_keys=ON')
 masterroots=dict(con.execute('SELECT root_id,case_id FROM arno_root_decisions'))
 if len(masterroots)!=342:raise ValueError('Master 342 C6 root census missing')
 if not ids.issubset(masterroots):raise ValueError('Source includes roots outside C6 census')
 pcmap=collections.defaultdict(set)
 for pc,root_id in con.execute('SELECT producing_change_id,root_id FROM arno_pc_root_lineage'):pcmap[root_id].add(pc)
 for r in rows:
  if int(r['case_id'])!=masterroots[r['root_id']]:raise ValueError('Root case differs '+r['root_id'])
  parsed={x.strip() for x in r['pc_ids'].split('|') if x.strip()}
  if int(r['pc_count'])!=len(parsed) or parsed!=pcmap[r['root_id']]:
   raise ValueError('D7 PC lineage mismatch: '+r['root_id']+' expected '+str(sorted(pcmap[r['root_id']]))+' got '+str(sorted(parsed)))
 con.execute('''CREATE TABLE arno_d7_final_M_roots_233(
    root_id TEXT PRIMARY KEY REFERENCES arno_root_decisions(root_id),
    case_id INTEGER NOT NULL REFERENCES cases(id),
    final_route TEXT NOT NULL CHECK(final_route='M'),
    final_tier TEXT NOT NULL,
    d7_cohort TEXT NOT NULL,
    pass_a_route TEXT,pass_b_route TEXT,
    mandatory_d4 TEXT,d4_reasons TEXT,
    final_evidence_complete TEXT,final_chronology_ok TEXT,
    final_route_confidence TEXT,final_explanation_confidence TEXT,
    adjudication_rationale TEXT NOT NULL,
    original_row_json TEXT NOT NULL,
    source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
    final_adjudication_status TEXT NOT NULL DEFAULT 'FINAL_D7_M_SUBSET'
 )''')
 con.execute('''CREATE VIEW arno_v_D7_roots_not_in_M233 AS
   SELECT r.root_id,r.case_id,r.coding_status
   FROM arno_root_decisions r LEFT JOIN arno_d7_final_M_roots_233 d
   ON d.root_id=r.root_id WHERE d.root_id IS NULL''')
 sk='D7_FINAL_M_ROOTS_233_WITH_COHORTS_original'
 con.execute('INSERT INTO arno_sources VALUES(?,?,?,?,?,?,?,?,?)',(
    sk,'frozen_final_root_adjudication_subset','D7 final M roots 233 with cohorts',str(src),
    expected_sha,'zlib/bytes',zlib.compress(raw,9),'VERIFIED_D7_233_SOURCE_BYTES',
    '233 M-routed roots with full independent blind coding and adjudication fields; 109 other C6 roots not classified by this file.'))
 for r in rows:
  con.execute('INSERT INTO arno_d7_final_M_roots_233 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(
    r['root_id'],int(r['case_id']),r['final_route'],r['final_tier'],r['d7_m_cohort'],
    r['pass_a_route'],r['pass_b_route'],r['mandatory_d4'],r['d4_reasons'],
    r['final_evidence_complete'],r['final_chronology_ok'],
    r['final_route_confidence'],r['final_explanation_confidence'],
    r['adjudication_rationale'],json.dumps(r,ensure_ascii=False,sort_keys=True),sk,'FINAL_D7_M_SUBSET'))
 con.execute("UPDATE arno_stage_ledger SET status='partial',detail=detail||'; D7 final M-only subset 233/342 roots imported (56 discovery-derived and 177 holdout), full blind coding and adjudication preserved; remaining 109 excluded from this file, status not inferred',last_updated_utc=? WHERE stage_number=6",(datetime.datetime.now(datetime.timezone.utc).isoformat(),))
 con.commit()
 report['counts']={
   'final_D7_M_roots':con.execute('SELECT COUNT(*) FROM arno_d7_final_M_roots_233').fetchone()[0],
   'root_census':con.execute('SELECT COUNT(*) FROM arno_root_decisions').fetchone()[0],
   'D7_not_in_M_subset':con.execute('SELECT COUNT(*) FROM arno_v_D7_roots_not_in_M233').fetchone()[0],
   'original_classifications':con.execute('SELECT COUNT(*) FROM arno_classifications').fetchone()[0],
   'new70_risk':con.execute('SELECT COUNT(*) FROM arno_new70_phase9_risk').fetchone()[0]}
 report['tier_counts']=dict(tiers)
 report['cohort_counts']=dict(cohorts)
 report['zero_PC_case_mismatches']=True
 report['sha_roundtrip']=hashlib.sha256(zlib.decompress(con.execute('SELECT embedded_bytes FROM arno_sources WHERE source_key=?',(sk,)).fetchone()[0])).hexdigest()==expected_sha
 report['fk_errors']=len(con.execute('PRAGMA foreign_key_check(arno_d7_final_M_roots_233)').fetchall())
 con.close()
 if report['counts']!={'final_D7_M_roots':233,'root_census':342,'D7_not_in_M_subset':109,'original_classifications':122,'new70_risk':70} or not report['sha_roundtrip'] or report['fk_errors']:raise ValueError('Post-import QC mismatch')
 report['status']='COMPLETE'
except Exception as ex:
 report['status']='FAILED';report['error']=type(ex).__name__+': '+str(ex)
 raise
finally:
 (out/'D7_M233_IMPORT_REPORT.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
 print(json.dumps(report,indent=2,ensure_ascii=False))
PY