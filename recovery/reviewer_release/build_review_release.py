from review_definitions import SCHEMA,POLICY,VIEWS
from review_docs import README,QUERIES
from review_helpers import quote,classify_run,build_catalog,artifact_catalog,claim_history,quality


"""Build a lossless reviewer edition; never alter the research master or vault."""


import csv


import hashlib


import itertools


import json


import os


import shutil


import sqlite3


import time


from pathlib import Path


ROOT = Path('/home-mscluster/astrauss/research_artifacts')


SOURCE = ROOT / 'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'


SNAPDIR = ROOT / 'ARNO_MASTER_DB/snapshots/backup_20261110_v1'


SNAPSHOT = SNAPDIR / 'ARNO_RESEARCH_MASTER.sqlite'


OUT = ROOT / 'ARNO_REVIEW_RELEASE_20261111_v1'


DB = OUT / 'ARNO_RESEARCH_MASTER_REVIEW.sqlite'


JOB = ROOT / 'mcp_uploads/jobs/review_release_20261111_v1'


STATUS = JOB / 'status.json'


PROGRESS = {'state': 'starting', 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}


def save(state, **kwargs):
    PROGRESS.update(state=state, **kwargs)
    tmp = STATUS.with_suffix('.tmp')
    tmp.write_text(json.dumps(PROGRESS, indent=2))
    tmp.replace(STATUS)
    print(json.dumps({'state': state, **kwargs}), flush=True)


def ro(path):
    c = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    c.execute('PRAGMA query_only=ON')
    c.row_factory = sqlite3.Row
    return c


def export(c, sql, path):
    cur = c.execute(sql)
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow([x[0] for x in cur.description])
        for row in cur:
            w.writerow(row)


def main():
    JOB.mkdir(parents=True,exist_ok=True)
    if OUT.exists():raise RuntimeError('Release destination already exists; refusing overwrite')
    OUT.mkdir()
    (OUT/'tables').mkdir()
    cert=json.loads((SNAPDIR/'status.json').read_text())
    entry=next(x for x in cert['files'] if x['name']=='ARNO_RESEARCH_MASTER.sqlite')
    if entry['integrity_check']!='ok':raise RuntimeError('Original snapshot lacks successful integrity check')
    expected=entry['sha256'];source_stats=(SOURCE.stat().st_size,SOURCE.stat().st_mtime_ns)
    if source_stats!=(entry['source_before']['bytes'],entry['source_before']['mtime_ns']):
        raise RuntimeError('Live master differs from the previously verified snapshot source; new snapshot required')
    save('copy_verified_snapshot',total_bytes=entry['bytes'])
    h=hashlib.sha256();n=0;last=time.monotonic()
    with SNAPSHOT.open('rb') as src,DB.open('xb') as dst:
        for block in iter(lambda:src.read(8*1024*1024),b''):
            h.update(block);dst.write(block);n+=len(block)
            if time.monotonic()-last>20:
                save('copy_verified_snapshot',copied_bytes=n,total_bytes=entry['bytes']);last=time.monotonic()
        dst.flush();os.fsync(dst.fileno())
    if n!=entry['bytes'] or h.hexdigest()!=expected:raise RuntimeError('Verified snapshot copy checksum mismatch')
    save('build_review_layer',snapshot_sha256_verified=expected)
    c=sqlite3.connect(str(DB));c.row_factory=sqlite3.Row
    original_schema=[tuple(r) for r in c.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_autoindex%' ORDER BY type,name")]
    original_tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    counts={t:c.execute('SELECT COUNT(*) FROM '+quote(t)).fetchone()[0] for t in original_tables}
    if counts!=entry['tables']:raise RuntimeError('Snapshot table counts differ from verified backup certificate')
    c.executescript(SCHEMA)
    c.executemany('INSERT INTO review_policy VALUES (?,?)',POLICY.items())
    build_catalog(c,counts,original_tables)
    fresh_ids={r[0] for r in c.execute('SELECT run_id FROM arno_owp14_fresh_o_reruns_20261031')}
    for r in c.execute('SELECT * FROM arno_experiment_runs').fetchall():
        cls,policy,basis=classify_run(r,fresh_ids)
        ev=json.dumps({'experiment_family':r['experiment_family'],'treatment':r['treatment'],'source_status':r['status'],'fresh_registry_member':r['run_id'] in fresh_ids},sort_keys=True)
        c.execute('INSERT INTO review_run_catalog VALUES (?,?,?,?,?,?,?)',(r['run_id'],cls,policy,basis,ev,'NOT_ATTESTED_SOURCE_QUALIFICATIONS_PRESERVED','NOT_INFERRED_FROM_HASH_OR_SCANNER_EXECUTION'))
    artifact_catalog(c);claim_history(c);quality(c)
    for name,sql in VIEWS.items():c.execute('CREATE VIEW '+name+' AS '+sql)
    c.commit()
    save('validate_review_layer')
    view_counts={name:c.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in VIEWS}
    checks={'review_v_cases':3809,'review_v_original122':122,'review_v_new70_final_findings':237,'review_v_producing_changes':455,'review_v_final_root_coding':342,'review_v_matched_pairs':190,'review_v_reproduced_statistics':9,'review_v_runs':68,'review_v_archived_owp_runs':40,'review_v_later_exploratory_runs':28}
    for k,v in checks.items():
        if view_counts[k]!=v:raise RuntimeError('View validation failed: '+k)
    for table,n in counts.items():
        if c.execute('SELECT COUNT(*) FROM '+quote(table)).fetchone()[0]!=n:raise RuntimeError('Original row count changed: '+table)
    current_schema=[tuple(r) for r in c.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_autoindex%' AND name NOT LIKE 'review_%' ORDER BY type,name")]
    if current_schema!=original_schema:raise RuntimeError('Original source schema changed')
    fresh=c.execute("SELECT COUNT(*) FROM review_v_archived_owp_runs WHERE run_id IN (SELECT run_id FROM arno_owp14_fresh_o_reruns_20261031)").fetchone()[0]
    if fresh:raise RuntimeError('New reruns leaked into historical O/W/P view')
    fk_review=list(c.execute('PRAGMA foreign_key_check(review_run_catalog)'))
    if fk_review:raise RuntimeError('Review run catalog has broken references')
    for name,sql in [('table_catalog','SELECT * FROM review_table_catalog ORDER BY domain,table_name'),('column_catalog','SELECT * FROM review_column_catalog ORDER BY table_name,column_name'),('relationships','SELECT * FROM review_relationship_catalog ORDER BY child_table,foreign_key_id,column_sequence'),('runs','SELECT * FROM review_v_runs ORDER BY evidence_class,case_id,run_id'),('current_claims','SELECT * FROM review_v_claims_current ORDER BY rq,claim_id'),('claim_history','SELECT * FROM review_claim_history ORDER BY rq,claim_key,source_table'),('artifacts','SELECT * FROM review_artifact_index ORDER BY case_id,run_id,artifact_key'),('quality_issues','SELECT * FROM review_quality_issues ORDER BY severity,entity_type,entity_key'),('policy','SELECT * FROM review_policy ORDER BY policy_key')]:
        export(c,sql,OUT/'tables'/ (name+'.csv'))
    (OUT/'SOURCE_SCHEMA.sql').write_text('\n\n'.join(r[3]+';' for r in original_schema if r[3]),encoding='utf-8')
    (OUT/'REVIEW_SCHEMA.sql').write_text(SCHEMA+'\n'+'\n\n'.join('CREATE VIEW '+k+' AS '+v+';' for k,v in VIEWS.items()),encoding='utf-8')
    (OUT/'README.md').write_text(README,encoding='utf-8')
    (OUT/'REPRODUCE.sql').write_text(QUERIES,encoding='utf-8')
    shutil.copyfile(JOB/'artifact_reader.py',OUT/'artifact_reader.py')
    shutil.copyfile(JOB/'build_review_release.py',OUT/'build_review_release.py')
    shutil.copyfile(JOB/'review_definitions.py',OUT/'review_definitions.py')
    shutil.copyfile(JOB/'review_helpers.py',OUT/'review_helpers.py')
    shutil.copyfile(JOB/'review_docs.py',OUT/'review_docs.py')
    report={'original_snapshot_integrity_check':'ok (from original backup certificate)','input_copy_sha256':expected,'original_tables_preserved':len(original_tables),'original_row_counts':counts,'original_schema_unchanged':True,'review_view_counts':view_counts,'historical_owp_excludes_fresh_reruns':True,'primary_analysis_automatically_selected':False,'source_master_unchanged':source_stats==(SOURCE.stat().st_size,SOURCE.stat().st_mtime_ns),'full_experiments_replayed':False,'source_limits_not_resolved_by_formatting':True}
    if not report['source_master_unchanged']:raise RuntimeError('Live master changed during build')
    c.close()
    (OUT/'VALIDATION.json').write_text(json.dumps(report,indent=2))
    save('hash_final_release')
    manifest={'release':'ARNO_REVIEW_RELEASE_20261111_v1','database':DB.name,'source_snapshot_sha256':expected,'original_master_preserved':True,'vault_payload_already_embedded':True,'notes':'No scientific labels overwritten. Later experimental runs remain distinct from original archived runs.','files':{}}
    for p in sorted(OUT.rglob('*')):
        if not p.is_file():continue
        digest=hashlib.sha256()
        with p.open('rb') as f:
            for b in iter(lambda:f.read(8*1024*1024),b''):digest.update(b)
        manifest['files'][str(p.relative_to(OUT))]={'bytes':p.stat().st_size,'sha256':digest.hexdigest()}
    (OUT/'MANIFEST.json').write_text(json.dumps(manifest,indent=2))
    (OUT/'SHA256SUMS').write_text(''.join(x['sha256']+'  '+name+'\n' for name,x in manifest['files'].items()))
    save('complete',release_directory=str(OUT),database_bytes=DB.stat().st_size,database_sha256=manifest['files'][DB.name]['sha256'],original_tables_preserved=len(original_tables),review_views=len(VIEWS))


if __name__=='__main__':
    try:main()
    except Exception as e:
        save('failed',error_type=type(e).__name__,error=str(e)[:1500])
        raise

