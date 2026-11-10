#!/bin/bash
#SBATCH --job-name=arno_owp14_restore
#SBATCH --partition=stampede
#SBATCH --time=00:11:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
python3 - <<'PY'
from pathlib import Path
import sqlite3,json,hashlib,zlib,csv,io,collections,datetime
R=Path.home()/'research_artifacts'
D=R/'mcp_uploads/jobs/arno_rq3_owp14_restore_20261028'
D.mkdir(parents=True,exist_ok=True)
DB=R/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'
src=R/'prevention_pilot_phase2/owp14_allarm_comparison_job71212'
sha=lambda b:hashlib.sha256(b).hexdigest()
report={'status':'STARTED','scope':'Frozen October O/W/P 14-case run artifacts; original CodeQL SARIF and result JSON preserved. Not proven causal prevention or functional equivalence.'}
try:
    summary_raw=(src/'OWP14_SUMMARY.json').read_bytes()
    summary=json.loads(summary_raw)
    asserts={int(x['case_id']):x for x in summary['cases']}
    assert len(asserts)==14 and summary['CodeQL_version']=='2.25.6'
    arms={
    'O':R/'prevention_pilot_phase2/owp14_user12_o_codeql_job71159',
    'W':R/'prevention_pilot_phase2/owp14_user14_w_codeql_job71209',
    'P':R/'prevention_pilot_phase2/owp14_user14_p_codeql_job71204'}
    rows=[];files=[]
    for cid,a in asserts.items():
      for arm,folder in arms.items():
        if a[arm+'_scan']!='SCAN_COMPLETE':continue
        d=folder/f'CASE_{cid:05d}'
        raw=(d/'RESULT.json').read_bytes();j=json.loads(raw)
        if int(j['case_id'])!=cid or j['arm']!=arm or j['stage']!='SCAN_COMPLETE':
          raise ValueError('Case/condition/state mismatch '+str(cid)+' '+arm)
        if j['patch_sha256']!=a[arm+'_patch_sha256'] or j['new_strong_total']!=a[arm+'_new'] or j['new_strong_target_rule']!=a[arm+'_target']:
          raise ValueError('Case/condition/hash/count mismatch '+str(cid)+' '+arm)
        if j['current_codeql_version']!=summary['CodeQL_version']:raise ValueError('Version mismatch')
        rows.append((cid,arm,a,j,raw,str((d/'RESULT.json').relative_to(R))))
        files.append((cid,arm,str((d/'after.sarif').relative_to(R)),(d/'after.sarif').read_bytes()))
    if len(rows)!=40:raise ValueError('Expected 40 observations; got '+str(len(rows)))
    complete=[a for a in asserts.values() if all(a[arm+'_scan']=='SCAN_COMPLETE' for arm in ('O','W','P'))]
    if len(complete)!=12:raise ValueError('Expected 12 complete triples')
    totals={arm:sum(int(a[arm+'_new']) for a in complete) for arm in ('O','W','P')}
    if totals!={'O':21,'W':10,'P':15}:raise ValueError('Reported experiment totals changed '+str(totals))
    extras=[]
    for filename in ['OWP14_SUMMARY.json','OWP14_SCANNER_COMPARISON.csv','OWP14_SCANNER_COMPARISON.md','OWP14_NEW_ALERTS_ALL_ARMS.json']:
      b=(src/filename).read_bytes();extras.append((str((src/filename).relative_to(R)),b))
    c=sqlite3.connect(str(DB),timeout=180)
    c.execute('PRAGMA busy_timeout=180000')
    c.execute('PRAGMA foreign_keys=ON')
    if len({r[0] for r in rows}-{t[0] for t in c.execute('SELECT id FROM cases')}):raise ValueError('Missing case master IDs')
    existing={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'arno_rq3_owp14_run_scans' in existing:raise ValueError('Refusing overwrite: OWP14 already imported')
    c.execute('BEGIN IMMEDIATE')
    c.execute('''CREATE TABLE arno_rq3_owp14_run_scans(
      case_id INTEGER NOT NULL REFERENCES cases(id),arm TEXT NOT NULL CHECK(arm IN ('O','W','P')),
      scan_state TEXT NOT NULL,source_snapshot_type TEXT NOT NULL,codeql_version TEXT NOT NULL,
      historical_target_rule TEXT,new_strong_count INTEGER NOT NULL,new_conservative_count INTEGER NOT NULL,
      target_new_strong INTEGER NOT NULL,patch_sha256 TEXT NOT NULL,
      functional_status TEXT NOT NULL,baseline_codeql_version_match INTEGER,
      original_result_path TEXT NOT NULL,result_sha256 TEXT NOT NULL,original_result_zlib BLOB NOT NULL,
      frozen_summary_row_json TEXT NOT NULL,patch_bytes_match_status TEXT NOT NULL,
      PRIMARY KEY(case_id,arm))''')
    c.execute('''CREATE TABLE arno_rq3_owp14_original_artifacts(
      source_path TEXT PRIMARY KEY,case_id INTEGER,arm TEXT,
      source_sha256 TEXT NOT NULL,original_bytes INTEGER NOT NULL,
      source_zlib BLOB NOT NULL,source_role TEXT NOT NULL)''')
    for cid,arm,a,j,raw,rel in rows:
      c.execute('INSERT INTO arno_rq3_owp14_run_scans VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(
        cid,arm,j['stage'],j['source_type'],j['current_codeql_version'],j.get('target_rule'),
        j['new_strong_total'],j['new_conservative_total'],j['new_strong_target_rule'],j['patch_sha256'],
        j['functional_status'],int(bool(j.get('baseline_version_match'))),rel,sha(raw),zlib.compress(raw,9),
        json.dumps(a,sort_keys=True),'HASH_RECORDED_GENERATED_PATCH_BYTES_NOT_INDEPENDENTLY_MATCHED'))
    for cid,arm,rel,b in files:
      c.execute('INSERT INTO arno_rq3_owp14_original_artifacts VALUES(?,?,?,?,?,?,?)',
        (rel,cid,arm,sha(b),len(b),zlib.compress(b,9),'CODEQL_AFTER_SARIF'))
    for rel,b in extras:
      c.execute('INSERT INTO arno_rq3_owp14_original_artifacts VALUES(?,?,?,?,?,?,?)',
        (rel,None,None,sha(b),len(b),zlib.compress(b,9),'FROZEN_RESULTS_SOURCE'))
    c.execute('''CREATE TABLE arno_rq3_owp14_reproduction_checks(
      claim_key TEXT PRIMARY KEY,expected TEXT NOT NULL,observed TEXT NOT NULL,
      status TEXT NOT NULL,qualification TEXT NOT NULL)''')
    checks=[
    ('OWP14_ARCHIVED_CASES','14',str(len(asserts)),'COUNT_REPRODUCED','All 14 source rows; only 12 have complete O/W/P triples'),
    ('OWP14_SCANNER_ARMS','40',str(len(rows)),'COUNT_REPRODUCED','Scanner outcomes only; issues completion not established'),
    ('OWP14_COMPLETE_TRIPLES','12',str(len(complete)),'COUNT_REPRODUCED','Two cases lack O outputs, no imputation'),
    ('OWP14_NEW_STRONG_O','21',str(totals['O']),'COUNT_REPRODUCED','Across the 12 complete triples only'),
    ('OWP14_NEW_STRONG_W','10',str(totals['W']),'COUNT_REPRODUCED','Across the 12 complete triples only'),
    ('OWP14_NEW_STRONG_P','15',str(totals['P']),'COUNT_REPRODUCED','Across the 12 complete triples only')]
    c.executemany('INSERT INTO arno_rq3_owp14_reproduction_checks VALUES(?,?,?,?,?)',checks)
    if c.execute('PRAGMA foreign_key_check(arno_rq3_owp14_run_scans)').fetchall():raise ValueError('FK errors')
    c.commit()
    checks2={'cases':len(asserts),'scan_arms':len(rows),'triples':len(complete),'totals':totals,
    'raw_json_hash_roundtrip':all(sha(zlib.decompress(b))==h for h,b in c.execute('SELECT result_sha256,original_result_zlib FROM arno_rq3_owp14_run_scans')),
    'raw_artifacts_hash_roundtrip':all(sha(zlib.decompress(b))==h for h,b in c.execute('SELECT source_sha256,source_zlib FROM arno_rq3_owp14_original_artifacts')),
    'artifacts':len(extras)+len(files)}
    if not checks2['raw_json_hash_roundtrip'] or not checks2['raw_artifacts_hash_roundtrip']:raise ValueError('Post-commit hash verification failed')
    report['counts']=checks2;report['status']='COMPLETE'
    c.close()
except Exception as e:
    report['status']='FAILED';report['error']=type(e).__name__+': '+str(e);raise
finally:
    (D/'OWP14_RESTORATION_REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)
PY