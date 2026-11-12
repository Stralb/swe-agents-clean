#!/bin/bash
#SBATCH --job-name=arno7_evidence_import
#SBATCH --partition=stampede
#SBATCH --time=00:12:00
#SBATCH --mem=5G
#SBATCH --cpus-per-task=1
python3 - <<'PY'
from pathlib import Path
import json,sqlite3,hashlib,zipfile,zlib,datetime
R=Path.home()/'research_artifacts'
src=R/'prevention_pilot_phase2/FINAL_SEVEN_CASE_RESEARCH_HANDOFF_20261020/COMPLETE_7_CASE_RESEARCH_HANDOFF_20261020.zip'
db=R/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'
O=R/'mcp_uploads/jobs/arno_seven_case_final_import_v6_20261028'
O.mkdir(parents=True,exist_ok=True)
sha=lambda b:hashlib.sha256(b).hexdigest()
expected_outer='24fa0b48f97d2ec91e03c118f5342df30080bba2fbf6646d4e777bfdf3584b17'
receipt={'status':'PREFLIGHT','archive_path':str(src.relative_to(R)),'claims':'Scanner outcome only, no independent functional verification; historical agent vs researcher intervention identity retained.'}
try:
    b=src.read_bytes()
    if sha(b)!=expected_outer:raise RuntimeError('Outer frozen archive SHA mismatch')
    records=[];components=[]
    with zipfile.ZipFile(src) as z:
        if z.testzip() is not None:raise RuntimeError('ZIP CRC verification failed')
        idxb=z.read('MASTER_INDEX.json');idx=json.loads(idxb)
        cases=['03429','03581','08152','12344','22223','31207','32759']
        if idx['cases']!=cases:raise RuntimeError('Wrong seven-case cohort')
        if idx['full_functional_acceptance_proven'] or idx['minimum_additive_issue_information_demonstrated']:
            raise RuntimeError('Unexpected claim status; manual review')
        manifest={item['case']:item for item in idx['results']}
        if set(manifest)!=set(cases):raise RuntimeError('Manifest case identity mismatch')
        names=set(z.namelist())
        for num in cases:
            cid=int(num)
            patchname=f'FINAL_PATCHES/CASE_{num}_FINAL.patch'
            resultname=f'CASE_DETAILS/CASE_{num}_FINAL_RESULT.json'
            aftername=f'CASE_DETAILS/{num}/FINAL_after.sarif'
            for fname in (patchname,resultname,aftername):
                if fname not in names:raise RuntimeError('Missing required member '+fname)
            patch=z.read(patchname); rb=z.read(resultname); sarif=z.read(aftername)
            result=json.loads(rb)
            expected_patch=result.get('new_patch_sha256',result.get('patch_sha256'))
            if sha(patch)!=expected_patch or sha(patch)!=manifest[num]['final_patch_sha256']:
                raise RuntimeError('Final patch hash drift '+num)
            if sha(rb)!=manifest[num]['final_result_sha256']:raise RuntimeError('Final result hash drift '+num)
            if result.get('new_strong_count')!=0 or result.get('new_conservative_count')!=0:
                raise RuntimeError('Result is not zero new findings '+num)
            if result.get('scan_completed',result.get('scanner_negative_both',False)) is not True:
                raise RuntimeError('Final scan did not complete '+num)
            sj=json.loads(sarif)
            if not isinstance(sj.get('runs'),list):raise RuntimeError('Invalid CodeQL SARIF '+num)
            initial_result=f'CASE_DETAILS/{num}/INITIAL_RESULT.json'
            original_initial=z.read(initial_result) if initial_result in names else None
            initial_before=f'CASE_DETAILS/{num}/INITIAL_before.sarif'
            original_before=z.read(initial_before) if initial_before in names else None
            initial_after=f'CASE_DETAILS/{num}/INITIAL_after.sarif'
            original_after=z.read(initial_after) if initial_after in names else None
            known_researcher=num in ('03429','12344')
            caution={'03429':'TEST_FIXTURE_SPECIFIC; POTENTIALLY_NOT_STRICT_ADDITIVE; OFFLINE_TEST_MISSING_TYPESCRIPT',
                     '03581':'NO_FULL_COMMENTARY_WEBVIEW_FUNCTIONAL_VERIFICATION',
                     '08152':'GRAMMY_PLUGIN_LOCKFILE_INSTALL_AND_TYPECHECK_UNVERIFIED',
                     '12344':'RESEARCHER_AUTHORED; FILTERED_SOURCE_PROVISIONAL; NATIVE_DPAPI_UNVERIFIED; OFFLINE_TEST_MISSING_TYPESCRIPT',
                     '22223':'NO_INDEPENDENT_AUTHORIZED_DOWNLOAD_TEST',
                     '31207':'POTENTIAL_CODEQL_DATAFLOW_INDIRECTION; COMPOSE_AND_HEALTHCHECK_UNVERIFIED',
                     '32759':'WINDOWS_NATIVE_EXECUTION_ARGUMENT_SEMANTICS_UNTESTED'}[num]
            records.append({'cid':cid,'num':num,'patchname':patchname,'resultname':resultname,'aftername':aftername,
                    'patch':patch,'rb':rb,'sarif':sarif,'result':result,'initial_result':original_initial,
                    'initial_before':original_before,'initial_after':original_after,
                    'initial_new':manifest[num]['P1_initial_new'],
                    'researcher_authored':known_researcher,'caution':caution})
        for fname,ref in idx['source_archives'].items():
            if fname not in names:raise RuntimeError('Missing source bundle '+fname)
            sb=z.read(fname)
            if len(sb)!=ref['bytes'] or sha(sb)!=ref['sha256']:raise RuntimeError('Inner archived bundle digest mismatch '+fname)
            components.append({'path':fname,'sha256':sha(sb),'bytes':len(sb)})
        start=z.read('START_HERE.md')
    conn=sqlite3.connect(str(db),timeout=180)
    conn.execute('PRAGMA busy_timeout=180000');conn.execute('PRAGMA foreign_keys=ON')
    ids={x[0] for x in conn.execute('SELECT id FROM cases WHERE id IN (3429,3581,8152,12344,22223,31207,32759)')}
    if ids!={r['cid'] for r in records}:raise RuntimeError('Seven cases missing from frozen master')
    if conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='arno_seven_final_repair_case_evidence'").fetchone()[0]:
        raise RuntimeError('Final seven table exists; no duplicate/overwrite')
    conn.execute('BEGIN IMMEDIATE')
    conn.execute('''CREATE TABLE arno_seven_final_repair_archive(
      source_key TEXT PRIMARY KEY, original_path TEXT NOT NULL, original_sha256 TEXT NOT NULL,
      original_bytes INTEGER NOT NULL, source_zip_zlib BLOB NOT NULL,
      archive_index_zlib BLOB NOT NULL, start_here_zlib BLOB NOT NULL,
      component_digest_manifest_json TEXT NOT NULL,
      provenance_status TEXT NOT NULL)''')
    conn.execute('''CREATE TABLE arno_seven_final_repair_case_evidence(
      case_id INTEGER PRIMARY KEY REFERENCES cases(id), final_patch_name TEXT NOT NULL,
      final_patch_sha256 TEXT NOT NULL, final_patch_zlib BLOB NOT NULL,
      final_result_name TEXT NOT NULL, final_result_sha256 TEXT NOT NULL, final_result_zlib BLOB NOT NULL,
      final_after_sarif_name TEXT NOT NULL, final_after_sarif_sha256 TEXT NOT NULL, final_after_sarif_zlib BLOB NOT NULL,
      initial_result_zlib BLOB, initial_before_sarif_zlib BLOB, initial_after_sarif_zlib BLOB,
      p1_initial_new_alert_count INTEGER NOT NULL, final_strong_new INTEGER NOT NULL,
      final_conservative_new INTEGER NOT NULL, final_scan_completed INTEGER NOT NULL,
      intervention_origin TEXT NOT NULL, functional_acceptance_status TEXT NOT NULL,
      causal_prevention_status TEXT NOT NULL, publication_qualification TEXT NOT NULL,
      exact_source_archive_key TEXT NOT NULL REFERENCES arno_seven_final_repair_archive(source_key))''')
    conn.execute('INSERT INTO arno_seven_final_repair_archive VALUES(?,?,?,?,?,?,?,?,?)',(
        'SEVEN_CASE_HANDOFF_20261020',str(src.relative_to(R)),sha(b),len(b),zlib.compress(b,1),
        zlib.compress(idxb,9),zlib.compress(start,9),
        json.dumps(components,sort_keys=True),'ORIGINAL_FULL_ARCHIVE_HASH_CRC_AND_NESTED_SHA256_VERIFIED'))
    for item in records:
        r=item;origin='RESEARCHER_AUTHORED_TARGETED_REPAIR' if r['researcher_authored'] else 'NOT_INDEPENDENTLY_ESTABLISHED_FROM_RESULT'
        conn.execute('INSERT INTO arno_seven_final_repair_case_evidence VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(
            r['cid'],r['patchname'],sha(r['patch']),zlib.compress(r['patch'],9),
            r['resultname'],sha(r['rb']),zlib.compress(r['rb'],9),
            r['aftername'],sha(r['sarif']),zlib.compress(r['sarif'],9),
            zlib.compress(r['initial_result'],9) if r['initial_result'] else None,
            zlib.compress(r['initial_before'],9) if r['initial_before'] else None,
            zlib.compress(r['initial_after'],9) if r['initial_after'] else None,
            r['initial_new'],0,0,1,origin,'NOT_FULLY_VERIFIED','NOT_DEMONSTRATED',r['caution'],
            'SEVEN_CASE_HANDOFF_20261020'))
    if conn.execute('PRAGMA foreign_key_check(arno_seven_final_repair_case_evidence)').fetchall():
       raise RuntimeError('Imported seven-case FK check failed')
    conn.commit()
    status={
      'status':'COMPLETE','source_zip_sha256':sha(b),'source_zip_bytes':len(b),
      'cases':conn.execute('SELECT COUNT(*) FROM arno_seven_final_repair_case_evidence').fetchone()[0],
      'all_patch_sha_roundtrip':all(sha(zlib.decompress(v))==h for h,v in conn.execute('SELECT final_patch_sha256,final_patch_zlib FROM arno_seven_final_repair_case_evidence')),
      'all_scanner_results_hash_roundtrip':all(sha(zlib.decompress(v))==h for h,v in conn.execute('SELECT final_result_sha256,final_result_zlib FROM arno_seven_final_repair_case_evidence')),
      'all_sarif_sha_roundtrip':all(sha(zlib.decompress(v))==h for h,v in conn.execute('SELECT final_after_sarif_sha256,final_after_sarif_zlib FROM arno_seven_final_repair_case_evidence')),
      'scanner_negative_count':conn.execute('SELECT COUNT(*) FROM arno_seven_final_repair_case_evidence WHERE final_strong_new=0 AND final_conservative_new=0 AND final_scan_completed=1').fetchone()[0],
      'independent_full_functional_acceptance':0,
      'researcher_authored_explicit':2,
      'source_archive_hash_roundtrip':all(sha(zlib.decompress(v))==h for h,v in conn.execute('SELECT original_sha256,source_zip_zlib FROM arno_seven_final_repair_archive'))}
    if not all(status[x] for x in ('all_patch_sha_roundtrip','all_scanner_results_hash_roundtrip','all_sarif_sha_roundtrip','source_archive_hash_roundtrip')):raise RuntimeError('Hash mismatch after transaction')
    receipt=status
    conn.close()
except Exception as e:
    receipt['status']='FAILED';receipt['error']=type(e).__name__+': '+str(e)
    raise
finally:
    (O/'SEVEN_CASE_IMPORT_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2),flush=True)
PY