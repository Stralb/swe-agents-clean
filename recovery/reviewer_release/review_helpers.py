import hashlib,json,sqlite3
from review_definitions import PURPOSES,group

def quote(name):
    return '"' + name.replace('"', '""') + '"'


def classify_run(row, fresh_ids):
    rid = row['run_id']; treatment = row['treatment']; family = row['experiment_family']
    if rid in fresh_ids:
        return 'LATER_NONBLIND_NEW_O', 'SUPPLEMENTARY_ONLY', 'Explicit fresh-O registry sets historical_O_recovered=0 and contributes_to_original_triple_count=0.'
    if family == 'RQ3_OWP14_ARCHIVED_SCAN_ARM' and row['status'] == 'ORIGINAL_ARCHIVED_PATCH_AND_SCANNER_RESULT_NOT_REEXECUTED':
        return 'ARCHIVED_ORIGINAL_OWP', 'HISTORICAL_CANDIDATE_PROTOCOL_REQUIRED', 'Explicit archived family and original-result status; not a fresh execution attestation.'
    if family == 'OCT2026_ARCHITECTURAL_GENERATION' and treatment == 'HISTORICAL_P1':
        return 'LATER_ANALYSIS_OF_HISTORICAL_PATCH', 'SUPPLEMENTARY_ONLY', 'Explicit HISTORICAL_P1 treatment in later architectural experiment family; not the original scanner execution.'
    if family == 'OCT2026_ARCHITECTURAL_GENERATION' and treatment == 'FROZEN_BASELINE':
        return 'LATER_BASELINE_SCAN', 'SUPPLEMENTARY_ONLY', 'Explicit FROZEN_BASELINE treatment in later architectural experiment family.'
    if family == 'OCT2026_ARCHITECTURAL_GENERATION':
        return 'LATER_ARCHITECTURAL_EXPERIMENT', 'SUPPLEMENTARY_ONLY', 'Separate architectural generation family; no promotion to historical O/W/P results.'
    return 'UNRESOLVED_ORIGIN', 'EXCLUDE_PENDING_REVIEW', 'No explicit origin rule matched; no date-based inference made.'


def build_catalog(c, counts, original_tables):
    for name in original_tables:
        domain, default = group(name)
        purpose = PURPOSES.get(name, default + ' Consult original schema and row-level provenance.')
        lifecycle = 'HISTORICAL_PRELIMINARY' if 'prelim' in name else 'HISTORICAL_LOG' if name in ('arno_stage_ledger', 'arno_rq_publication_claim_audit') else 'PRESERVED_SOURCE'
        c.execute('INSERT INTO review_table_catalog VALUES (?,?,?,?,?,?)', (name, domain, purpose, lifecycle, counts[name], 'Source field meanings and limitations are not rewritten by the review edition.'))
        for col in c.execute('PRAGMA table_info('+quote(name)+')').fetchall():
            notes = 'Original column; see source table purpose and row-level qualifications.'
            if col['name'] in ('case_id', 'run_id', 'source_key', 'root_id'):
                notes = 'Stable linkage identifier; declared foreign keys are catalogued separately.'
            if col['name'] in ('canonical_finding_id', 'producing_change_id'):
                notes = 'Respect cohort and preliminary/final version scope; do not join historical versions by bare identifier.'
            if col['name'].endswith(('zlib','blob','bytes')):
                notes += ' May hold binary data; use artifact index encoding, not automatic text conversion.'
            c.execute('INSERT INTO review_column_catalog VALUES (?,?,?,?,?,?,?)',(name,col['name'],col['type'],col['notnull'],col['pk'],col['dflt_value'],notes))
        for fk in c.execute('PRAGMA foreign_key_list('+quote(name)+')').fetchall():
            c.execute('INSERT INTO review_relationship_catalog VALUES (?,?,?,?,?,?,?,?)',(name,fk['id'],fk['seq'],fk['from'],fk['table'],fk['to'],fk['on_update'],fk['on_delete']))


def artifact_catalog(c):
    specs = [
      ('arno_chat_evidence_objects',['artifact_id'],'case_id','run_id','role','sha256','original_bytes','content_zlib','compression','source_locator'),
      ('arno_generated_patches',['patch_id'],None,'run_id',None,'content_sha256',None,'patch_blob',None,'patch_uri'),
      ('arno_sources',['source_key'],None,None,'source_kind','source_sha256',None,'embedded_bytes','embedded_encoding','source_locator'),
      ('arno_evidence_assets',['source_path'],None,None,'artifact_role','source_sha256','original_bytes','content_zlib',None,'source_path'),
      ('arno_rq_methodology_sources',['source_path'],None,None,'role','sha256','raw_size','raw_zlib',None,'source_path'),
      ('arno_rq3_owp14_original_artifacts',['source_path'],'case_id',None,'source_role','source_sha256','original_bytes','source_zlib',None,'source_path'),
      ('arno_rq3_owp14_verified_patch_bytes',['case_id','arm'],'case_id',None,None,'patch_sha256','original_patch_bytes','patch_zlib',None,'original_filename'),
      ('arno_rq3_owp14_verified_archive',['arm'],None,None,None,'original_zip_sha256','original_zip_bytes','zip_zlib',None,None),
      ('arno_rq3_owp14_original_transport',['source_path'],None,None,None,'sha256','raw_size','raw_zlib',None,'source_path'),
      ('arno_archive_vault_objects',['object_key'],'case_id',None,'source_kind','expected_sha256','original_bytes',None,None,'source_locator'),
    ]
    for table,pks,case,run,role,sha,size,payload,encoding,locator in specs:
        cols=set(pks+[x for x in (case,run,role,sha,size,encoding,locator) if x])
        expr=','.join(quote(x) for x in sorted(cols))
        if payload:expr+=','+quote(payload)+' IS NOT NULL AS payload_present'
        for row in c.execute('SELECT '+expr+' FROM '+quote(table)).fetchall():
            keys={k:row[k] for k in pks}; keyjson=json.dumps(keys,sort_keys=True)
            akey=table+':'+hashlib.sha256(keyjson.encode()).hexdigest()
            runid=row[run] if run else None;caseid=row[case] if case else None
            basis='Explicit source columns only; no filename-based case inference.'
            if runid and caseid is None:
                rr=c.execute('SELECT case_id FROM arno_experiment_runs WHERE run_id=?',(runid,)).fetchone()
                if rr:caseid=rr[0];basis='Explicit run_id join to arno_experiment_runs.'
            enc=row[encoding] if encoding else ('zlib' if payload and payload.endswith('zlib') else 'raw')
            embedded=int(row['payload_present']) if payload else int(table=='arno_archive_vault_objects')
            payload_column=payload
            if table=='arno_archive_vault_objects':enc='ordered_vault_chunks';payload_column='arno_archive_vault_chunks.bytes'
            c.execute('INSERT INTO review_artifact_index VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',(akey,table,keyjson,caseid,runid,row[role] if role else table,row[sha] if sha else None,row[size] if size else None,embedded,payload_column,enc or 'unspecified',row[locator] if locator else None,basis))
    # Main prompt fields are indexed without inventing missing original invocation metadata.
    for row in c.execute('SELECT run_id,case_id FROM arno_experiment_runs WHERE prompt_blob IS NOT NULL').fetchall():
        c.execute('INSERT INTO review_artifact_index VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',('run_prompt:'+row['run_id'],'arno_experiment_runs',json.dumps({'run_id':row['run_id']},sort_keys=True),row['case_id'],row['run_id'],'main_prompt',None,None,1,'prompt_blob','raw',None,'Explicit experiment run prompt field.'))


def claim_history(c):
    specs=[
      ('arno_rq_publication_claim_audit','claim_id','audit_status','paper_or_archive_value','caveat',0),
      ('arno_claim_status_supersession_20261029','claim_id','current_evidence_status','evidence','caveat',1),
      ('arno_postmerge_publication_readiness_20261028','audit_key','evidence_status','quantitative_summary','publication_qualification',0),
      ('arno_new70_final_publication_status','claim_key','verification','claim_text','qualifications',0),
      ('arno_publication_evidence_status','claim_key','status','source_asset','limitations',0),
    ]
    for table,key,status,statement,caveat,explicit in specs:
        for row in c.execute('SELECT * FROM '+table).fetchall():
            c.execute('INSERT INTO review_claim_history VALUES (?,?,?,?,?,?,?,?,?)',(table+':'+row[key],table,row[key],row[key],row['rq'],row[status],row[statement],row[caveat],explicit))


def quality(c):
    def issue(key,severity,kind,entity,message,interpretation):
        c.execute('INSERT INTO review_quality_issues VALUES (?,?,?,?,?,?)',(key,severity,kind,str(entity),message,interpretation))
    for r in c.execute('SELECT run_id FROM arno_experiment_runs WHERE prompt_blob IS NULL').fetchall():
        issue('prompt:'+r[0],'REVIEW','run',r[0],'MAIN_PROMPT_FIELD_NULL','Check input packets and indexed prompt artifacts; no claim that all original prompt bytes are lost.')
    for r in c.execute('SELECT run_id FROM arno_experiment_runs').fetchall():
        issue('functional:'+r[0],'LIMITATION','run',r[0],'FUNCTIONAL_VALIDITY_NOT_ATTESTED_BY_REVIEW_EDITION','Scanner completion and source status are retained; no functional equivalence inferred.')
    for r in c.execute('SELECT * FROM arno_chat_pending_runs').fetchall():
        issue('pending:'+r['run_id'],'UNRESOLVED','run',r['run_id'],'SOURCE_PENDING_RUN_RECORD','Historical pending record; inspect later run and artifact records before calling evidence missing.')
    for r in c.execute('SELECT claim_id FROM arno_rq_publication_claim_audit WHERE claim_id IN (SELECT claim_id FROM arno_claim_status_supersession_20261029)').fetchall():
        issue('superseded:'+r[0],'HISTORY','claim',r[0],'OLDER_AUDIT_HAS_EXPLICIT_SUPERSESSION','Use review_v_claims_current; retain original audit as provenance.')
    for t in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'arno_%'").fetchall():
        # Report pre-existing FK inconsistencies; never silently repair source data.
        try:
            for n,r in enumerate(c.execute('PRAGMA foreign_key_check('+quote(t[0])+')')):
                issue('fk:'+t[0]+':'+str(n),'UNRESOLVED','table',t[0],'DECLARED_FOREIGN_KEY_VIOLATION',json.dumps(list(r)))
        except sqlite3.DatabaseError as e:
            issue('fk_schema:'+t[0],'UNRESOLVED','table',t[0],'SOURCE_FOREIGN_KEY_CHECK_COULD_NOT_COMPLETE',str(e))
    for table in ('arno_generated_patches','arno_experiment_scans'):
        bad=c.execute('SELECT COUNT(*) FROM '+table+' t LEFT JOIN arno_experiment_runs r ON r.run_id=t.run_id WHERE r.run_id IS NULL').fetchone()[0]
        if bad:raise RuntimeError('Unexpected orphan run references in '+table)

