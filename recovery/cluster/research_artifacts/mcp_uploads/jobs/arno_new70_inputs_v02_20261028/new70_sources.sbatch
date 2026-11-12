#!/bin/bash
#SBATCH --job-name=arno_new70_sources
#SBATCH --partition=stampede
#SBATCH --time=00:08:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
python3 - <<'PY'
import csv,io,json,hashlib,zlib,sqlite3,datetime
from pathlib import Path
root=Path.home()/'research_artifacts'
src=root/'new70_frozen_methodology_20260829T091932Z'
target=root/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'
out=root/'mcp_uploads/jobs/arno_new70_inputs_v02_20261028'
out.mkdir(parents=True,exist_ok=True)
sources={
 'new70_case_mapping':src/'90_LOCKED_FOR_LATER/case_mapping_FULL_NEW70.csv',
 'new70_blind_issues':src/'01_ISSUE_PASS1_BLIND/Blind_Issue_Source_NEW70.csv',
 'new70_blind_prs':src/'02_PR_PASS1_BLIND/Blind_PR_Source_NEW70.csv',
 'new70_stage4b_index':src/'03_STAGE4B_BLIND/stage4b_blind_evaluation_index_NEW70.csv'
}
result={'status':'STARTED','source_files':{k:str(p) for k,p in sources.items()},'kind':'FROZEN INPUTS, NOT CLASSIFICATION OUTPUTS'}
try:
 b={k:p.read_bytes() for k,p in sources.items()}
 def csvrows(k):return list(csv.DictReader(io.StringIO(b[k].decode('utf-8-sig'))))
 mapping={int(r['case_id']):r for r in csvrows('new70_case_mapping')}
 issues={int(r['Case ID']):r for r in csvrows('new70_blind_issues')}
 prs={int(r['Case ID']):r for r in csvrows('new70_blind_prs')}
 indexes={int(r['Case ID']):r for r in csvrows('new70_stage4b_index')}
 ids=set(mapping)
 assert len(ids)==70 and ids==set(issues)==set(prs)==set(indexes)
 for cid in ids:
  assert int(indexes[cid]['PR ID'])==int(mapping[cid]['pr_id'])
  assert int(issues[cid]['Review #'])==int(mapping[cid]['review_number'])==int(prs[cid]['Review #'])
 conn=sqlite3.connect(str(target),timeout=60)
 conn.execute('PRAGMA busy_timeout=60000')
 conn.execute('PRAGMA foreign_keys=ON')
 assert conn.execute('SELECT COUNT(*) FROM arno_classifications').fetchone()[0]==122
 assert conn.execute('SELECT COUNT(*) FROM arno_excluded_cases').fetchone()[0]==16
 assert all(conn.execute('SELECT 1 FROM cases WHERE id=?',(k,)).fetchone() for k in ids)
 assert not any(conn.execute('SELECT 1 FROM arno_classifications WHERE case_id=?',(k,)).fetchone() for k in ids)
 positives={r[0] for r in conn.execute('SELECT DISTINCT case_id FROM scanner_findings WHERE introduced=1')}
 assert len(positives&ids)==60
 conn.execute('''CREATE TABLE arno_new70_source_inputs(
   case_id INTEGER PRIMARY KEY REFERENCES cases(id),
   pr_id INTEGER NOT NULL REFERENCES pull_requests(id),
   review_number INTEGER NOT NULL UNIQUE,
   issue_title TEXT,issue_body TEXT,pr_title TEXT,pr_body TEXT,
   case_mapping_json TEXT NOT NULL,blind_issue_json TEXT NOT NULL,
   blind_pr_json TEXT NOT NULL,stage4b_index_json TEXT NOT NULL,
   evidence_filename TEXT,evidence_completeness TEXT,
   raw_promoted_flag INTEGER NOT NULL CHECK(raw_promoted_flag IN(0,1)),
   classification_status TEXT NOT NULL DEFAULT 'SOURCE_ONLY',
   source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
 )''')
 for key,raw in b.items():
  conn.execute('INSERT INTO arno_sources VALUES(?,?,?,?,?,?,?,?,?)',(
     key,'frozen_input_csv',key,str(sources[key]),hashlib.sha256(raw).hexdigest(),
     'zlib/bytes',zlib.compress(raw,9),'VERIFIED_INPUT_ONLY','No manual final labels inferred'))
 for k,r in mapping.items():
  d=indexes[k]
  conn.execute('INSERT INTO arno_new70_source_inputs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(
   k,int(r['pr_id']),int(r['review_number']),r['issue_title'],r['issue_body'],
   r['pr_title'],r['pr_body'],json.dumps(r,ensure_ascii=False),
   json.dumps(issues[k],ensure_ascii=False),json.dumps(prs[k],ensure_ascii=False),
   json.dumps(d,ensure_ascii=False),d['Blind Evidence File'],d['Stage4B Evidence Completeness'],
   int(k in positives),'SOURCE_ONLY','new70_case_mapping'))
  conn.execute('INSERT INTO arno_cohort_membership VALUES(?,?,?,?)',(k,'new70_historical_frozen','HISTORICALLY_ANALYSED','new70_case_mapping'))
  if k not in positives:
   conn.execute('INSERT INTO arno_cohort_membership VALUES(?,?,?,?)',(k,'new70_raw_unpromoted10','INTRODUCED_ZERO','new70_case_mapping'))
 conn.execute("UPDATE arno_stage_ledger SET status='partial',detail=?,last_updated_utc=? WHERE stage_number=3",(
   '70 NEW70 source inputs imported, final 70 manual classifications pending source recovery',
   datetime.datetime.now(datetime.timezone.utc).isoformat()))
 conn.commit()
 result['counts']={'rows':conn.execute('SELECT COUNT(*) FROM arno_new70_source_inputs').fetchone()[0],
    'promoted':conn.execute('SELECT SUM(raw_promoted_flag) FROM arno_new70_source_inputs').fetchone()[0],
    'unpromoted':conn.execute('SELECT COUNT(*) FROM arno_new70_source_inputs WHERE raw_promoted_flag=0').fetchone()[0],
    'first122':conn.execute('SELECT COUNT(*) FROM arno_classifications').fetchone()[0]}
 result['hashes']={k:hashlib.sha256(b[k]).hexdigest() for k in sources}
 result['foreign_key_violations_new70']=len(conn.execute('PRAGMA foreign_key_check(arno_new70_source_inputs)').fetchall())
 result['status']='COMPLETE'
 conn.close()
except Exception as e:
 result['status']='FAILED';result['error']=type(e).__name__+': '+str(e)
 raise
finally:
 (out/'NEW70_SOURCE_IMPORT_REPORT.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2),flush=True)
PY