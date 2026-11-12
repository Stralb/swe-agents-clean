#!/bin/bash
#SBATCH --job-name=arno_rq_audit2
#SBATCH --partition=stampede
#SBATCH --time=00:14:00
#SBATCH --mem=3G
#SBATCH --cpus-per-task=1
python3 - <<'PY'
from pathlib import Path
import sqlite3,csv,io,json,hashlib,zlib,datetime
root=Path.home()/'research_artifacts'
db=root/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'
out=root/'mcp_uploads/jobs/arno_rq_audit_v02_20261028'
out.mkdir(parents=True,exist_ok=True)
sha=lambda b:hashlib.sha256(b).hexdigest()
date=datetime.datetime.now(datetime.timezone.utc).isoformat()
report={'status':'STARTED','purpose':'Reproduce paper claims and archive RQ methodologies, real scanner results and OWP original transport without interpreting missing outcomes.'}
try:
    csvpath=root/'prevention_pilot_phase2/screen65_codeql_summary_job70694/SCREEN65_CODEQL_RESULTS.csv'
    raw=csvpath.read_bytes()
    records=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    assert len(records)==65 and len({r['case_id'] for r in records})==65
    scans=[]
    for rec in records:
        cid=int(rec['case_id'])
        path=root/f'prevention_pilot_phase2/screen65_codeql_job70675/CASE_{cid:05d}/RESULT.json'
        b=path.read_bytes()
        j=json.loads(b)
        assert j['case_id']==cid and j['stage']==rec['state'] and j['source_type']==rec['source_type']
        assert j['findings']['new_strong_count']==int(rec['new_strong_count'] or 0)
        assert j['findings']['new_weak_count']==int(rec['new_weak_count'] or 0)
        scans.append((cid,rec,j,b,str(path.relative_to(root))))
    methodnames=[
    ('RQ1','root_codebook','D_COMPLETE_ROOT_PROVENANCE_v1_0/00_FROZEN/D0_PRODUCTION_ROUTE_CODEBOOK_FROZEN_v1.0.md'),
    ('RQ1','D_root_source_audit','D_COMPLETE_ROOT_PROVENANCE_v1_0/04_EVIDENCE_EXPORT/AUDIT/D_EVIDENCE_INDEPENDENT_AUDIT.json'),
    ('RQ1','D_root_build_qc','D_COMPLETE_ROOT_PROVENANCE_v1_0/04_EVIDENCE_EXPORT/AUDIT/D_EVIDENCE_BUILD_QC.json'),
    ('RQ1','choice_selection','implementation_choice_phase1_v1_0_49121/PHASE1_SELECTION_MANIFEST.json'),
    ('RQ1','choice_frozen_protocol','implementation_choice_phase1_v1_0_49121/README_PHASE1_FROZEN.md'),
    ('RQ1','pilot_method','implementation_choice_phase2_v1_0_49124/README_PHASE2_METHOD.md'),
    ('RQ1','holdout_method','implementation_choice_phase5_holdout_v1_0_49129/README_PHASE5_HOLDOUT_METHOD.md'),
    ('RQ2','C1_method','matched_control_c1_v1_1/C1_REPORT.md'),
    ('RQ2','C2_method','matched_control_c2_v1_0/C2_REPORT.md'),
    ('RQ2','C2_balance','matched_control_c2_v1_0/C2_MATCHING_VARIABLE_BALANCE.csv'),
    ('RQ2','C3_method','matched_control_c3_v1_0/C3_REPORT.md'),
    ('RQ2','C3_issue_template','matched_control_c3_v1_0/C3_ANNOTATION_TEMPLATE_ISSUE.csv'),
    ('RQ2','C3_PR_template','matched_control_c3_v1_0/C3_ANNOTATION_TEMPLATE_PR.csv'),
    ('RQ2','C3_impl_template','matched_control_c3_v1_0/C3_ANNOTATION_TEMPLATE_IMPLEMENTATION.csv'),
    ('RQ3','scanner65_csv','prevention_pilot_phase2/screen65_codeql_summary_job70694/SCREEN65_CODEQL_RESULTS.csv'),
    ('RQ3','scanner65_json','prevention_pilot_phase2/screen65_codeql_summary_job70694/SCREEN65_CODEQL_SUMMARY.json'),
    ('RQ3','seven_issue_manifest','mcp_uploads/seven_minimal_info_intake_20261020/ISSUE_SUMMARY.json'),
    ('ALL','master_checkpoint','mcp_uploads/arno_master_20261028/MASTER_CHECKPOINT_v06_20261028.txt')]
    methods=[(rq,role,rel,(root/rel).read_bytes()) for rq,role,rel in methodnames]
    chunks=[]
    for cond,rel,num in [
    ('O','mcp_uploads/owp14_20261018_transfer_v1',6),
    ('W','mcp_uploads/owp14_w14_20261018_transfer_v1',5),
    ('P','mcp_uploads/owp14_user_p14_20261018_transfer_v1',4)]:
        paths=sorted((root/rel).glob('chunk_*.txt'))
        assert len(paths)==num
        for i,p in enumerate(paths,1):
            assert p.name==f'chunk_{i:02d}.txt'
            chunks.append((cond,str(p.relative_to(root)),i,p.read_bytes()))
    conn=sqlite3.connect(str(db),timeout=180)
    conn.execute('PRAGMA busy_timeout=180000')
    conn.execute('PRAGMA foreign_keys=ON')
    caseids={x[0] for x in conn.execute('SELECT id FROM cases')}
    assert all(r[0] in caseids for r in scans)
    conn.execute('BEGIN IMMEDIATE')
    conn.execute('''CREATE TABLE arno_rq3_codeql_screen65_original(
    case_id INTEGER PRIMARY KEY REFERENCES cases(id),source_snapshot_type TEXT NOT NULL,
    generator_claim TEXT,scan_state TEXT NOT NULL,scanner_suite TEXT NOT NULL,
    before_total INTEGER,after_total INTEGER,new_strong INTEGER,new_weak INTEGER,
    historical_target_rules TEXT,new_rule_summary TEXT,
    summary_csv_sha256 TEXT NOT NULL,original_summary_row_json TEXT NOT NULL,
    result_source_path TEXT NOT NULL,result_sha256 TEXT NOT NULL,result_zlib BLOB NOT NULL,
    link_to_generated_patch_status TEXT NOT NULL, functional_status TEXT NOT NULL)''')
    for cid,rec,j,b,rel in scans:
        conn.execute('INSERT INTO arno_rq3_codeql_screen65_original VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(
        cid,rec['source_type'],rec['generation_claim'],rec['state'],j['suite'],
        int(rec['before_total']),int(rec['after_total']),int(rec['new_strong_count'] or 0),
        int(rec['new_weak_count'] or 0),rec['historical_target_rules'],
        rec['new_rule_summary'],sha(raw),json.dumps(rec,sort_keys=True),rel,
        sha(b),zlib.compress(b,9),'CASE_ONLY_NO_PATCH_HASH_LINK','NOT_VERIFIED'))
    conn.execute('''CREATE TABLE arno_rq_methodology_sources(
    source_path TEXT PRIMARY KEY, rq TEXT NOT NULL, role TEXT NOT NULL,
    sha256 TEXT NOT NULL,raw_size INTEGER NOT NULL,raw_zlib BLOB NOT NULL,
    integrity_status TEXT NOT NULL,human_verification TEXT NOT NULL)''')
    for rq,role,rel,b in methods:
        conn.execute('INSERT INTO arno_rq_methodology_sources VALUES(?,?,?,?,?,?,?,?)',(
        rel,rq,role,sha(b),len(b),zlib.compress(b,9),
        'SOURCE_BYTES_PRESERVED_SHA256','NOT_DETERMINED_FROM_FILE_EXISTENCE'))
    conn.execute('''CREATE TABLE arno_rq3_owp14_original_transport(
    source_path TEXT PRIMARY KEY,condition_name TEXT NOT NULL,
    part_number INTEGER NOT NULL,sha256 TEXT NOT NULL,
    raw_size INTEGER NOT NULL,raw_zlib BLOB NOT NULL,status TEXT NOT NULL)''')
    for cond,rel,i,b in chunks:
        conn.execute('INSERT INTO arno_rq3_owp14_original_transport VALUES(?,?,?,?,?,?,?)',(
        rel,cond,i,sha(b),len(b),zlib.compress(b,9),'UNDECODED_UNMATCHED_SOURCE'))
    conn.execute('''CREATE TABLE arno_rq_publication_claim_audit(
    claim_id TEXT PRIMARY KEY,rq TEXT NOT NULL,
    paper_or_archive_value TEXT NOT NULL,database_value TEXT,
    reproduce_sql TEXT,audit_status TEXT NOT NULL,
    caveat TEXT NOT NULL,audit_utc TEXT NOT NULL)''')
    claims=[
    ('RQ1_MINED_CASES','RQ1',3809,'SELECT COUNT(*) FROM cases'),
    ('RQ1_SCANNER_POSITIVE','RQ1',192,'SELECT SUM(is_positive) FROM arno_matched_control_C1_opportunity'),
    ('RQ1_PRODUCING_CHANGES','RQ1',455,'SELECT COUNT(*) FROM arno_frozen_broad_attribution'),
    ('RQ1_ROOT_CENSUS','RQ1',342,'SELECT COUNT(*) FROM arno_root_decisions'),
    ('RQ1_FINAL_M','RQ1',233,'SELECT COUNT(*) FROM arno_d7_final_M_roots_233'),
    ('RQ1_M_INCOMPLETE','RQ1',24,"SELECT COUNT(*) FROM arno_d7_final_M_roots_233 WHERE final_tier='INCOMPLETE'"),
    ('RQ2_MATCHED_PAIRS','RQ2',190,'SELECT COUNT(*) FROM arno_matched_control_pairs_C2'),
    ('RQ2_UNMATCHED','RQ2',2,'SELECT COUNT(*) FROM arno_matched_control_unmatched_C2'),
    ('RQ3_SCANNER65','RQ3',65,'SELECT COUNT(*) FROM arno_rq3_codeql_screen65_original'),
    ('RQ3_PATCH_BYTES','RQ3',91,'SELECT COUNT(*) FROM arno_recovered_agent_patch_bytes')]
    checked=[]
    for key,rq,expected,sql in claims:
        got=conn.execute(sql).fetchone()[0]
        status='COUNT_REPRODUCED' if got==expected else 'COUNT_MISMATCH'
        conn.execute('INSERT INTO arno_rq_publication_claim_audit VALUES(?,?,?,?,?,?,?,?)',(
        key,rq,str(expected),str(got),sql,status,
        'Count only; no human adjudication or causal interpretation inferred.',date))
        checked.append({'id':key,'expected':expected,'observed':got,'status':status})
    pending=[
    ('RQ1_H_T_FULL','RQ1','Reported H=6,T=103','Full final H/T adjudication rows not recovered into master; 233 M verified separately.'),
    ('RQ1_NEW70_237','RQ1','Reported final canonical findings=237','Authoritative final 237 rows absent; 254 candidates are preliminary.'),
    ('RQ2_PAIRED_SEMANTICS','RQ2','Reported issue specificity 63.7%/77.9%, p=0.00052; alignment 84.2%/96.3%, p=0.001','Finished raw paired semantic judgments and exact test implementation not in master.'),
    ('RQ2_HUMAN_QC','RQ2','Matched-control annotation outcomes','C3 templates and evidence present; populated review outputs not verified.'),
    ('RQ3_OWP','RQ3','Reported 12 complete O/W/P triples, 21/10/15 recorded new alerts','Transport bytes preserved; full treatment-to-patch/result linkage not recovered.'),
    ('RQ3_REPAIR','RQ3','Reported scanner-negative 3/7 before and 7/7 after repair','Final patched implementation, scanner outcomes and functional checks not linked.'),
    ('RQ1_HUMAN','RQ1','Human validation of coding','First-pass/QC preserved, independent human adjudication not established.')]
    for key,rq,value,caveat in pending:
        conn.execute('INSERT INTO arno_rq_publication_claim_audit VALUES(?,?,?,?,?,?,?,?)',(
        key,rq,value,None,None,'REPORTED_NOT_REPRODUCED',caveat,date))
    conn.commit()
    checks={
    'screen65_rows':conn.execute('SELECT COUNT(*) FROM arno_rq3_codeql_screen65_original').fetchone()[0],
    'method_files':conn.execute('SELECT COUNT(*) FROM arno_rq_methodology_sources').fetchone()[0],
    'OWP_transport_parts':conn.execute('SELECT COUNT(*) FROM arno_rq3_owp14_original_transport').fetchone()[0],
    'claims':conn.execute('SELECT COUNT(*) FROM arno_rq_publication_claim_audit').fetchone()[0],
    'scanner_sha_ok':all(sha(zlib.decompress(b))==h for b,h in conn.execute('SELECT result_zlib,result_sha256 FROM arno_rq3_codeql_screen65_original')),
    'method_sha_ok':all(sha(zlib.decompress(b))==h for b,h in conn.execute('SELECT raw_zlib,sha256 FROM arno_rq_methodology_sources')),
    'transport_sha_ok':all(sha(zlib.decompress(b))==h for b,h in conn.execute('SELECT raw_zlib,sha256 FROM arno_rq3_owp14_original_transport')),
    'fk_errors':len(conn.execute('PRAGMA foreign_key_check(arno_rq3_codeql_screen65_original)').fetchall())}
    report.update({'counts':checks,'claim_checks':checked,'reported_not_reproduced':pending,'screen65_source_sha256':sha(raw)})
    conn.close()
    if checks['screen65_rows']!=65 or checks['method_files']!=len(methods) or checks['OWP_transport_parts']!=15 or checks['claims']!=17 or not all(checks[k] for k in ['scanner_sha_ok','method_sha_ok','transport_sha_ok']) or checks['fk_errors']:
        raise ValueError('Post-commit verification mismatch')
    report['status']='COMPLETE'
except Exception as e:
    report['status']='FAILED'
    report['error']=type(e).__name__+': '+str(e)
    raise
finally:
    (out/'RQ_AUDIT_REPORT.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(report,indent=2,ensure_ascii=False),flush=True)
PY