#!/usr/bin/env python3
import csv
import hashlib
import io
import json
import os
import sqlite3
import sys
import zlib
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

ROOT=Path.home() / "research_artifacts"
DB=ROOT / "ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
OUT=ROOT / "mcp_uploads/jobs/arno_v6_20261031_peerreview_readonly_v1"
OUT.mkdir(parents=True,exist_ok=True)
issues=[]
checks=[]
expected_uploads={
 "ARCHGEN_03581_R1":"aa9ee6513777e7913e339b5afc9048d8e26a135346852b3bd1e853c7600a0b6e",
 "ARCHGEN_08152_R1":"6c1b52fefde7b0a11968a9fdc0b5fb9baf48444f44231a0a9e8b7c975550503c",
 "ARCHGEN_12344_R1":"509d8924071b89dff959f2d3d39a20b39d75f2593b3124fe6c1853bb53bffb6a"
}
def issue(severity,scope,code,detail):
    issues.append(dict(severity=severity,scope=str(scope),code=code,detail=str(detail)))
def sha(data):
    return hashlib.sha256(data).hexdigest()
con=sqlite3.connect("file:"+quote(str(DB))+"?mode=ro",uri=True,timeout=60)
con.row_factory=sqlite3.Row
con.execute("PRAGMA query_only=ON")
con.execute("PRAGMA busy_timeout=60000")
def rows(sql,args=()):
    return [dict(r) for r in con.execute(sql,args).fetchall()]
def one(sql,args=()):
    return con.execute(sql,args).fetchone()[0]
evidence=rows("SELECT artifact_id,run_id,case_id,role,source_locator,sha256,original_bytes,compression,content_zlib,verification_status FROM arno_chat_evidence_objects")
metrics=rows("SELECT * FROM arno_chat_codeql_metrics")
ps=rows("SELECT patch_id,run_id,content_sha256,patch_blob,authenticity_status FROM arno_generated_patches")
patches={r['run_id']:r for r in ps if r['run_id']}
artifact_index=defaultdict(dict)
n_embedded=0
n_external=0
source_checked={}
for r in evidence:
    run=r['run_id'];role=r['role']
    if role in artifact_index[run]:
        issue('ERROR',run,'DUPLICATE_ROLE',role)
    artifact_index[run][role]=r
    if r['compression']=='zlib':
        n_embedded+=1
        try:
            blob=zlib.decompress(r['content_zlib'])
            if len(blob)!=r['original_bytes']:
                issue('ERROR',run,'EMBEDDED_SIZE_MISMATCH',role)
            if sha(blob)!=r['sha256']:
                issue('ERROR',run,'EMBEDDED_HASH_MISMATCH',role)
            if role=='after_sarif':
                try:
                    obj=json.loads(blob)
                    num=sum(len(x.get('results',[])) for x in obj.get('runs',[]))
                    result=next((m for m in metrics if m['run_id']==run),None)
                    if result and num!=result['after_total']:
                        issue('ERROR',run,'SARIF_RESULT_COUNT_MISMATCH',f"{num} != {result['after_total']}")
                except Exception as ex:
                    issue('ERROR',run,'SARIF_DECODE_ERROR',str(ex))
        except Exception as ex:
            issue('ERROR',run,'EMBEDDED_DECOMPRESS_ERROR',f"{role}: {ex}")
    elif r['compression']=='EXTERNAL_ONLY':
        n_external+=1
        key=r['sha256']
        if key not in source_checked:
            p=(ROOT / r['source_locator']).resolve()
            if not p.is_relative_to(ROOT.resolve()):
                issue('ERROR',run,'EXTERNAL_PATH_OUTSIDE_ROOT',str(p))
                source_checked[key]={'status':'OUTSIDE_ROOT'}
            elif not p.is_file():
                issue('ERROR',run,'EXTERNAL_SOURCE_MISSING',str(p))
                source_checked[key]={'status':'MISSING','path':str(p)}
            else:
                h=hashlib.sha256()
                n=0
                with p.open('rb') as f:
                    for chunk in iter(lambda:f.read(1024*1024),b''):
                        h.update(chunk);n+=len(chunk)
                source_checked[key]={'status':'HASH_MATCH' if h.hexdigest()==key else 'HASH_MISMATCH','size':n,'path':str(p)}
                if h.hexdigest()!=key or n!=r['original_bytes']:
                    issue('ERROR',run,'EXTERNAL_SOURCE_HASH_SIZE_MISMATCH',str(p))
        else:
            z=source_checked[key]
            if z.get('status')!='HASH_MATCH':
                issue('ERROR',run,'EXTERNAL_REFERENCE_TO_BAD_SOURCE',role)
    else:
        issue('ERROR',run,'UNKNOWN_COMPRESSION',role+': '+str(r['compression']))
for run,expected in expected_uploads.items():
    p=artifact_index.get(run,{}).get('patch')
    g=patches.get(run)
    if not p or p['sha256']!=expected:
        issue('ERROR',run,'UPLOADED_PATCH_NOT_MATCHED','Missing or incorrect patch evidence object')
    if not g or g['content_sha256']!=expected or sha(g['patch_blob'])!=expected:
        issue('ERROR',run,'UPLOADED_PATCH_NOT_MATCHED_GENERIC','Missing/incorrect arno_generated_patches blob')
    else:
        checks.append({'run':run,'uploaded_patch_sha256':'MATCH','generic_patch_bytes':len(g['patch_blob'])})
finding_counts={r['run_id']:r for r in rows("SELECT run_id,COUNT(*) AS n,SUM(CASE WHEN new_vs_baseline=1 THEN 1 ELSE 0 END) AS n_new,SUM(CASE WHEN matches_historical_p1=1 THEN 1 ELSE 0 END) AS n_hist FROM arno_chat_codeql_findings GROUP BY run_id")}
run_matrix=[]
for m in metrics:
    run=m['run_id'];a=artifact_index.get(run,{})
    fc=finding_counts.get(run,{})
    for field,col in [('after_total','n'),('new_vs_baseline','n_new'),('historical_p1_remaining','n_hist')]:
        if field=='historical_p1_remaining' and m[field] is None:
            continue
        if int(fc.get(col,0) or 0)!=int(m[field] or 0):
            issue('ERROR',run,'METRICS_FINDING_MISMATCH',f"{field}:{m[field]} vs {col}:{fc.get(col,0)}")
    if run.startswith('ARCHGEN_'):
        expected=['patch','after_sarif','self_written_prompt','result_json','warning_delta_json','source_zip_external','log_apply.log','log_apply_check.log']
        for role in expected:
            if role not in a:
                issue('ERROR',run,'REQUIRED_ARTIFACT_MISSING',role)
        if run!='ARCHGEN_22223_R1' and 'agent_receipt' not in a:
            issue('ERROR',run,'AGENT_RECEIPT_MISSING','expected agent_receipt')
        if run=='ARCHGEN_22223_R1' and 'agent_receipt' not in a:
            issue('LIMITATION',run,'AGENT_RECEIPT_NOT_RECOVERED','Historical run evidence has no original agent receipt; do not fabricate')
        if m['functional_status'] not in ('VERIFIED','FULLY_VERIFIED'):
            issue('LIMITATION',run,'FUNCTIONAL_ACCEPTANCE_NOT_VERIFIED',m['functional_status'])
        if m['source_kind']!='FULL_FROZEN_SNAPSHOT':
            issue('LIMITATION',run,'FILTERED_PROVISIONAL_SOURCE',m['source_kind'])
    if run in patches and 'patch' in a:
        pr=patches[run]
        raw=zlib.decompress(a['patch']['content_zlib'])
        if raw!=pr['patch_blob']:
            issue('ERROR',run,'PATCH_TABLE_BYTES_DIFFER','Evidence-object patch != general patch table')
    run_matrix.append(dict(run_id=run,case_id=m['case_id'],method=m['method'],source_kind=m['source_kind'],baseline_total=m['baseline_total'],after_total=m['after_total'],new_vs_baseline=m['new_vs_baseline'],historical_p1_new=m['historical_p1_new'],historical_p1_remaining=m['historical_p1_remaining'],findings_rows=fc.get('n',0),artifact_roles=len(a),patch_embedded=int('patch' in a),after_sarif_embedded=int('after_sarif' in a),baseline_sarif_embedded=int('baseline_sarif' in a),source_zip_verified=source_checked.get(a.get('source_zip_external',{}).get('sha256',''),{}).get('status','NONE'),functional_status=m['functional_status'],receipt_status=m['receipt_status']))
# The first 122/NEW70/D7/RQ2/RQ3 completeness are audited at the frozen-table level.
tables={
 'cases': 'cases','roots_342':'arno_d7_final_roots_342',
 'pc_root_lineages':'arno_pc_root_lineage','rq2_c6_pairs':'arno_rq2_c6_pairs',
 'new70_final_findings':'arno_new70_final_findings',
 'new70_final_producing_changes':'arno_new70_final_producing_changes',
 'experiment_runs':'arno_experiment_runs',
 'experiment_scans':'arno_experiment_scans',
 'archive_vault_objects':'arno_archive_vault_objects',
 'archive_vault_members':'arno_archive_vault_members',
 'scanner_findings':'scanner_findings'
}
counts={}
for label,table in tables.items():
    try:counts[label]=one('SELECT COUNT(*) FROM '+table)
    except Exception as ex:issue('ERROR','GLOBAL','TABLE_QUERY_FAILED',f"{table}: {ex}")
stages=rows("SELECT stage_number,stage_name,status,detail,last_updated_utc FROM arno_stage_ledger ORDER BY stage_number")
publication=rows("SELECT claim_key,rq,status,limitations FROM arno_publication_evidence_status")
readiness=rows("SELECT audit_key,rq,evidence_status,publication_qualification FROM arno_postmerge_publication_readiness_20261028")
for s in stages:
    if s['status']!='completed':
        issue('LIMITATION','STAGE_'+str(s['stage_number']),'STAGE_PARTIAL',s['stage_name']+': '+s['detail'][:300])
for r in readiness:
    if any(x in str(r['evidence_status']).upper() for x in ['GAP','UNVERIFIED','INCOMPLETE']):
        issue('LIMITATION',r['rq'],'PUBLICATION_READINESS_GAP',r['audit_key']+': '+r['evidence_status'])
summary={
 'audit_method':'READ_ONLY_CONSISTENCY_AND_SHA256_AUDIT',
 'live_db':str(DB),'live_db_bytes':DB.stat().st_size,
 'scope':'All 26 new CodeQL runs; 244 evidence objects; seven ARCHGEN runs; stage ledger and high-level research coverage',
 'evidence_objects':len(evidence),'compressed_objects_checked':n_embedded,
 'external_references_checked':n_external,'unique_source_zips_verified':source_checked,
 'codeql_runs':len(metrics),'normalized_finding_rows':one('SELECT COUNT(*) FROM arno_chat_codeql_findings'),
 'run_matrix_rows':len(run_matrix),'tables':counts,'stage_statuses':dict(Counter(x['status'] for x in stages)),
 'errors':sum(x['severity']=='ERROR' for x in issues),
 'limitations':sum(x['severity']=='LIMITATION' for x in issues),
 'error_details':[x for x in issues if x['severity']=='ERROR'],
 'uploaded_patches':checks,
 'notes':['This does not establish functional correctness, vulnerability exploitability, historical issue text immutability or peer-review quality of human annotation.','External source ZIPs are not in evidence blob table. Hash/path checked; avoid claiming self-contained source database.','Stored run-level scan comparisons are not new causal replications.','No master DB writes performed.']
}
for name,data in [('SUMMARY.json',summary),('GAPS.json',issues),('PUBLICATION_STATUS.json',dict(claims=publication,readiness=readiness,stages=stages))]:
    (OUT/name).write_text(json.dumps(data,indent=2,default=str)+'\n')
with (OUT/'RUN_MATRIX.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(run_matrix[0].keys()));w.writeheader();w.writerows(run_matrix)
with (OUT/'GAPS.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['severity','scope','code','detail']);w.writeheader();w.writerows(issues)
print(json.dumps({'status':'AUDIT_COMPLETED','errors':summary['errors'],'limitations':summary['limitations'],'evidence_objects':len(evidence),'checked_embedded':n_embedded,'unique_external_sources':len(source_checked),'codeql_runs':len(metrics),'findings':summary['normalized_finding_rows'],'out':str(OUT)},indent=2))
con.close()
