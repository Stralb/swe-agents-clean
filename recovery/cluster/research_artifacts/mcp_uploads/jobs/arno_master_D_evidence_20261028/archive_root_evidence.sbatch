#!/bin/bash
#SBATCH --job-name=arno_D_evidence_import
#SBATCH --partition=stampede
#SBATCH --time=00:15:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
python3 - <<'PY'
from pathlib import Path
import csv,datetime,hashlib,io,json,sqlite3,zlib,tarfile,collections
root=Path.home()/'research_artifacts'
base=root/'D_COMPLETE_ROOT_PROVENANCE_v1_0'
db=root/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'
out=root/'mcp_uploads/jobs/arno_master_D_evidence_20261028'
out.mkdir(parents=True,exist_ok=True)
report={'status':'STARTED','stage':'D: frozen root coder evidence, not completed root coder decisions'}
sources={
 'D_evidence_master_archive_v1_1':base/'D_EVIDENCE_EXPORT_MASTER_v1.1.tar.gz',
 'D_pass_A_original_archive_v1_1':base/'D_PASS_A_BUNDLE_v1.1.tar.gz',
 'D_pass_B_blind_archive_v1_1':base/'D_PASS_B_BLIND_BUNDLE_v1.1.tar.gz',
 'D_private_crosswalk_archive_v1_1':base/'D_PRIVATE_CROSSWALK_v1.1.tar.gz',
 'D_frozen_codebook':base/'00_FROZEN/D0_PRODUCTION_ROUTE_CODEBOOK_FROZEN_v1.0.md',
 'D_index_342':base/'04_EVIDENCE_EXPORT/AUDIT/D_EVIDENCE_INDEX_342.csv',
 'D_independent_audit':base/'04_EVIDENCE_EXPORT/AUDIT/D_EVIDENCE_INDEPENDENT_AUDIT.json',
 'D_build_QC':base/'04_EVIDENCE_EXPORT/AUDIT/D_EVIDENCE_BUILD_QC.json',
 'D_v1_1_repair_QC':base/'04_EVIDENCE_EXPORT/AUDIT/D_EVIDENCE_V1_1_REPAIR_QC.json',
 'D_bundle_SHA_manifest':base/'D_EVIDENCE_DELIVERABLE_SHA256_v1.1.txt'
}
try:
    expected_archives={
       'D_evidence_master_archive_v1_1':'251f4c4f4fd7b3ba84e82d2c20e7af681322bf87e241ba793b006e2169db2b18',
       'D_pass_A_original_archive_v1_1':'cb6612a776b605ca91b3febc6afe2095ee4a64c1500b27c90310676a0b4d9515',
       'D_pass_B_blind_archive_v1_1':'e3971ca6235b72469a649ae07325c4bc4feefdbb82ed27faba2b86e865641656',
       'D_private_crosswalk_archive_v1_1':'42ae613f1c30c8be7261657be9c3d031cbc52cbea9614d2238bd7123dc7acf5f'
    }
    bs={name:p.read_bytes() for name,p in sources.items()}
    hashes={name:hashlib.sha256(data).hexdigest() for name,data in bs.items()}
    for name,digest in expected_archives.items():
        if hashes[name]!=digest:raise ValueError('Frozen bundle hash mismatch for '+name)
    audit=json.loads(bs['D_independent_audit'])
    if audit['status']!='PASS' or audit['actual']['pass_A_roots']!=342 or audit['actual']['pass_B_roots']!=342 or audit['actual']['private_crosswalk_rows']!=342:raise ValueError('D audit invalid')
    index=list(csv.DictReader(io.StringIO(bs['D_index_342'].decode('utf-8-sig'))))
    keys={r['root_id'] for r in index}
    if len(index)!=342 or len(keys)!=342:raise ValueError('Unexpected D index rows')
    for name in expected_archives:
        with tarfile.open(fileobj=io.BytesIO(bs[name]),mode='r:gz') as tar:
            names=tar.getnames()
            if not names:raise ValueError('Empty archive '+name)
            if len(names)>5000:raise ValueError('Unexpected archive member count')
            report.setdefault('archive_members',{})[name]={'count':len(names),'first_five':names[:5]}
    conn=sqlite3.connect(str(db),timeout=70)
    conn.execute('PRAGMA busy_timeout=70000')
    conn.execute('PRAGMA foreign_keys=ON')
    if conn.execute('SELECT COUNT(*) FROM arno_root_decisions').fetchone()[0]!=342:raise ValueError('Frozen C6 roots missing')
    roots={r[0]:r[1] for r in conn.execute('SELECT root_id,case_id FROM arno_root_decisions')}
    if keys!=set(roots):raise ValueError('D root index IDs differ from frozen C6')
    for r in index:
        if int(r['case_id'])!=roots[r['root_id']]:raise ValueError('Case IDs differ for '+r['root_id'])
    conn.execute('''CREATE TABLE arno_D_root_evidence_index (
      root_id TEXT PRIMARY KEY REFERENCES arno_root_decisions(root_id),
      case_id INTEGER NOT NULL REFERENCES cases(id),
      producing_change_count INTEGER NOT NULL,
      pass_A_evidence_items INTEGER NOT NULL,
      pass_B_evidence_items INTEGER NOT NULL,
      issue_preintro_human_status TEXT,
      true_base_target_status TEXT,bounded_repo_search_status TEXT,
      project_instructions_status TEXT,dependency_toolchain_status TEXT,
      external_guidance_status TEXT,chronology_status TEXT,
      frozen_row_json TEXT NOT NULL,
      source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
      evidence_kind TEXT NOT NULL DEFAULT 'PRE_ADJUDICATION_EVIDENCE_PACKET'
    )''')
    for name,blob in bs.items():
        encoding='original_gzip_tar' if name in expected_archives else 'zlib/bytes'
        content=blob if encoding=='original_gzip_tar' else zlib.compress(blob,9)
        conn.execute('INSERT INTO arno_sources VALUES(?,?,?,?,?,?,?,?,?)',(
         name,'frozen_D_root_evidence_export',name,str(sources[name]),hashes[name],
         encoding,content,'ORIGINAL_BYTES_VERIFIED_BY_SHA256',
         'Frozen 342 root coder packets and method evidence only; not independent coder labels.'
        ))
    for r in index:
        conn.execute('''INSERT INTO arno_D_root_evidence_index VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
            r['root_id'],int(r['case_id']),int(r['pc_count']),
            int(r['pass_A_evidence_items']),int(r['pass_B_evidence_items']),
            r['channel_issue_and_preintro_human'],r['channel_true_base_target'],
            r['channel_bounded_repository_search'],r['channel_project_instructions'],
            r['channel_dependency_toolchain'],r['channel_external_guidance'],
            r['channel_chronology'],json.dumps(r,ensure_ascii=False,sort_keys=True),
            'D_index_342','PRE_ADJUDICATION_EVIDENCE_PACKET'
        ))
    utc=datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn.execute("UPDATE arno_stage_ledger SET status='partial',detail=detail||'; D v1.1 342-root full/blind evidence archives, private crosswalk, codebook, QC and root-index imported; final coder decisions still missing',last_updated_utc=? WHERE stage_number=6",(utc,))
    conn.commit()
    report['counts']={'D_index_roots':conn.execute('SELECT COUNT(*) FROM arno_D_root_evidence_index').fetchone()[0],
       'root_census_unchanged':conn.execute('SELECT COUNT(*) FROM arno_root_decisions').fetchone()[0],
       'original_classifications_unchanged':conn.execute('SELECT COUNT(*) FROM arno_classifications').fetchone()[0],
       'new70_phase9_labels_unchanged':conn.execute('SELECT COUNT(*) FROM arno_new70_phase9_risk').fetchone()[0]}
    report['source_sha256_verified']={name:hashlib.sha256(conn.execute('SELECT embedded_bytes FROM arno_sources WHERE source_key=?',(name,)).fetchone()[0] if name in expected_archives else zlib.decompress(conn.execute('SELECT embedded_bytes FROM arno_sources WHERE source_key=?',(name,)).fetchone()[0])).hexdigest()==hashes[name] for name in sources}
    report['foreign_key_violations']=len(conn.execute('PRAGMA foreign_key_check(arno_D_root_evidence_index)').fetchall())
    conn.close()
    if report['counts']!={'D_index_roots':342,'root_census_unchanged':342,'original_classifications_unchanged':122,'new70_phase9_labels_unchanged':70} or report['foreign_key_violations'] or not all(report['source_sha256_verified'].values()):
        raise ValueError('Post-import integrity failure')
    report['status']='COMPLETE'
except Exception as exc:
    report['status']='FAILED';report['error']=type(exc).__name__+': '+str(exc)
    raise
finally:
    (out/'D_ROOT_EVIDENCE_IMPORT_REPORT.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(report,indent=2,ensure_ascii=False))
PY