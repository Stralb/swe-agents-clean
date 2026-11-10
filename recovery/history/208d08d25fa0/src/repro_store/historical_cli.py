"""Reviewer CLI for original immutable research evidence.

Accepts either a private vault DIRECTORY or a self-contained portable .sqlite.
No evaluation, model calls, scanning, code execution or data mutations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


def _connect(source: Path):
    path=source if source.suffix=='.sqlite' else source/'catalog.sqlite'
    if not path.is_file():raise SystemExit('No SQLite catalog found at '+str(path))
    db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA query_only=ON')
    db.execute('PRAGMA foreign_keys=ON')
    return db


def _metadata(db, table: str) -> list[dict[str,Any]]:
    return [dict(x) for x in db.execute('SELECT * FROM '+table)]


def _has_table(db, table: str)->bool:
    return db.execute('SELECT 1 FROM sqlite_master WHERE type="table" AND name=?',(table,)).fetchone() is not None


def _archive_bytes(db,src:Path,sha:str)->bytes:
    row=db.execute('SELECT storage,inline_bytes,object_relpath,bytes FROM artifacts WHERE sha256=?',(sha,)).fetchone()
    if not row:raise SystemExit('Digest is not present in archive: '+sha)
    if row['storage']=='inline':raw=row['inline_bytes']
    elif _has_table(db,'embedded_artifacts'):
        item=db.execute('SELECT payload FROM embedded_artifacts WHERE sha256=?',(sha,)).fetchone()
        if not item:raise SystemExit('Portable copy missing blob: '+sha)
        raw=item['payload']
    else:
        if src.suffix=='.sqlite':raise SystemExit('Evidence bytes require original vault objects folder')
        expected=f'objects/{sha[:2]}/{sha[2:]}'
        if row['object_relpath']!=expected:raise SystemExit('Unsafe source object path')
        p=src/expected
        if p.is_symlink() or not p.is_file():raise SystemExit('Missing SHA-addressed object '+sha)
        raw=p.read_bytes()
    if raw is None or len(raw)!=row['bytes'] or hashlib.sha256(raw).hexdigest()!=sha:
        raise SystemExit('Evidence byte integrity check failed '+sha)
    return raw


def case(db,cid:str)->dict:
    if not cid.isdecimal():raise SystemExit('Expected numeric case id')
    cid=str(int(cid))
    runs=[dict(r) for r in db.execute('''SELECT run_pk,study,case_id,arm,iteration,
         status_from_source,patch_sha256,provenance_status
         FROM historical_generation_runs WHERE case_id=? ORDER BY study,iteration,arm''',(cid,))]
    scans=[dict(r) for r in db.execute('''SELECT r.study,r.arm,r.patch_sha256,
         s.source_codeql_version,s.source_suite,s.source_target_rule,s.source_reported_new_count,
         s.source_reported_target_count,s.source_reported_before_count,s.source_reported_after_count,
         s.source_functional_status,s.baseline_member_present,s.source_baseline_sha256
         FROM historical_scans s JOIN historical_generation_runs r USING(run_pk)
         WHERE r.case_id=? ORDER BY r.arm''',(cid,))]
    tests=[dict(r) for r in db.execute('''SELECT arm,test_kind,status_from_source,source_patch_sha256,
         source_member_id FROM historical_test_observations WHERE case_id=?
         ORDER BY arm,test_kind''',(cid,))]
    ann=[dict(r) for r in db.execute('''SELECT stage,label_name,label_json,coding_pass,verification
         FROM research_annotations WHERE unit_type='workflow' AND unit_id=?
         ORDER BY annotation_id''',(cid,))]
    files=[dict(r) for r in db.execute('''SELECT original_filename,source_path,source_generation,
         original_member_sha256,a.member_path FROM historical_file_index f
         JOIN archive_members a USING(member_id) WHERE source_case_id=? ORDER BY f.member_id''',(cid,))]
    return {'case_id':cid,'source_policy':'Only archive-traceable historical observations, no reanalysis',
           'historical_runs':runs,'historical_scans':scans,'historical_test_reports':tests,
           'previous_workbook_annotations':ann,'original_files':files}


def run(db,cid:str,arm:str,study:str)->dict:
    cid=str(int(cid))
    matches=[dict(x) for x in db.execute('''SELECT r.*, a.member_path as patch_path
         FROM historical_generation_runs r JOIN archive_members a ON a.member_id=r.patch_member_id
         WHERE r.case_id=? AND r.arm=? AND r.study=?''',(cid,arm,study))]
    if not matches:return {'status':'NO_MATCHING_HISTORICAL_RUN','case_id':cid,'arm':arm,'study':study}
    if len(matches)!=1:raise SystemExit('Ambiguous historical run identifiers')
    r=matches[0];r['source_metadata']=json.loads(r.pop('source_meta_json'))
    scans=[dict(x) for x in db.execute('''SELECT s.*,a.member_path as report_path,b.member_path as sarif_path
         FROM historical_scans s JOIN archive_members a ON a.member_id=s.report_member_id
         LEFT JOIN archive_members b ON b.member_id=s.sarif_member_id WHERE s.run_pk=?''',(r['run_pk'],))]
    for s in scans:
        s['source_result']=json.loads(s.pop('source_result_json'))
        s['sarif_findings_count']=db.execute('SELECT COUNT(*) FROM historical_sarif_findings WHERE scan_pk=?',(s['scan_pk'],)).fetchone()[0]
    tests=[dict(x) for x in db.execute('''SELECT test_kind,status_from_source,source_patch_sha256,source_member_id
         FROM historical_test_observations WHERE case_id=? AND arm=?''',(cid,arm))]
    return {'run':r,'scanner_observations':scans,'other_reported_tests':tests,
            'interpretation_warning':'Original observations only; scanner-clean is not a valid patch or absence of vulnerabilities'}


def search(db,phrase:str,limit:int=20)->list[dict]:
    return [dict(r) for r in db.execute('''SELECT f.member_path AS original_archive_member,
         snippet(historical_fts,1,'[',']','...',18) AS snippet
         FROM historical_fts AS f WHERE historical_fts MATCH ? LIMIT ?''',('\"'+phrase.replace('\"','\"\"')+'\"',max(1,min(limit,100))))]


def status(db)->dict:
    tbls=['historical_file_index','historical_generation_runs','historical_scans',
          'historical_sarif_findings','historical_test_observations','historical_study_register',
          'historical_recovery_targets','historical_text_index','historical_target_events','historical_claim_register','research_annotations','archive_members','sources','artifacts']
    return {'artifact_type':'PRIVATE_HISTORICAL_ORIGINAL_BYTES_AND_SOURCE_REPORTED_OBSERVATIONS',
           'tables':{t:db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in tbls},
           'run_breakdown':[dict(x) for x in db.execute('''SELECT study,arm,COUNT(*) AS count FROM historical_generation_runs
                 GROUP BY study,arm ORDER BY study,arm''')],
           'recovery_needed':[dict(x) for x in db.execute('''SELECT study_id,expected_name,current_status AS status
                 FROM historical_recovery_current WHERE current_status NOT IN ('locally_imported','source_verified')
                 ORDER BY study_id,priority''')],
           'scientific_warning':'This catalog is incomplete until missing historical originals are authenticated and imported'}


def verify(db,source:Path,deep:bool=True)->dict:
    fk=db.execute('PRAGMA foreign_key_check').fetchall()
    integrity=db.execute('PRAGMA integrity_check').fetchone()[0]
    arts=list(db.execute('SELECT sha256,bytes FROM artifacts ORDER BY sha256'))
    failures=[]
    if deep:
        for sha,n in arts:
            try:
                raw=_archive_bytes(db,source,sha)
                if len(raw)!=n:failures.append({'sha256':sha,'reason':'size'})
            except Exception as e:failures.append({'sha256':sha,'reason':str(e)[:200]})
    records=list(db.execute('SELECT record_id,payload_json,payload_sha256 FROM research_records'))
    invalid=[rid for rid,payload,digest in records if hashlib.sha256(payload.encode('utf-8')).hexdigest()!=digest]
    indexed=list(db.execute('SELECT archive_sha256,listed_members,verified_members,missing_from_index,mismatched_digest FROM historical_archive_audits'))
    runhash=db.execute('SELECT COUNT(*) FROM historical_scans WHERE patch_hash_agrees=0').fetchone()[0]
    return {'status':'PASS' if integrity=='ok' and not fk and not failures and not invalid and not runhash else 'FAIL',
            'sqlite_integrity':integrity,'foreign_key_errors':len(fk),
            'source_artifacts':len(arts),'all_blobs_checked':len(arts) if deep else 0,
            'blob_errors':failures[:30], 'record_hash_errors':invalid[:30],
            'scan_patch_hash_mismatches':runhash,
            'part_indices':[dict(zip(('sha256','listed','verified','unlisted','digest_errors'),r)) for r in indexed]}


def main(argv=None):
    p=argparse.ArgumentParser(description='Read-only historical research evidence reviewer')
    p.add_argument('--vault',required=True,type=Path,help='Private evidence DIRECTORY or portable .sqlite')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('status')
    c=sub.add_parser('case');c.add_argument('case_id')
    r=sub.add_parser('run');r.add_argument('case_id');r.add_argument('arm');r.add_argument('--study',default='OWP14')
    s=sub.add_parser('search');s.add_argument('query');s.add_argument('--limit',type=int,default=20)
    v=sub.add_parser('verify');v.add_argument('--quick',action='store_true')
    m=sub.add_parser('studies')
    claims=sub.add_parser('claims');claims.add_argument('--study')
    e=sub.add_parser('extract');e.add_argument('member_path');e.add_argument('--output',required=True,type=Path)
    args=p.parse_args(argv)
    with _connect(args.vault) as db:
        if args.command=='status':out=status(db)
        elif args.command=='case':out=case(db,args.case_id)
        elif args.command=='run':out=run(db,args.case_id,args.arm,args.study)
        elif args.command=='search':out=search(db,args.query,args.limit)
        elif args.command=='verify':out=verify(db,args.vault,not args.quick)
        elif args.command=='studies':out=_metadata(db,'historical_study_register')
        elif args.command=='claims':out=[dict(x) for x in db.execute(
            'SELECT * FROM historical_claim_register WHERE (? IS NULL OR study_id=?) ORDER BY claim_id',
            (args.study,args.study))]
        elif args.command=='extract':
            item=db.execute('SELECT member_sha256 FROM archive_members WHERE member_path=?',(args.member_path,)).fetchone()
            if not item:raise SystemExit('Original member not found by exact path')
            target=args.output.resolve()
            if target.exists():raise SystemExit('Refusing to overwrite existing file')
            target.parent.mkdir(parents=True,exist_ok=True)
            data=_archive_bytes(db,args.vault,item[0]);flags='xb'
            with target.open(flags) as f:f.write(data)
            out={'status':'EXACT_ORIGINAL_MEMBER_EXTRACTED','path':str(target),
                 'sha256':item[0],'bytes':len(data)}
        print(json.dumps(out,indent=2,ensure_ascii=False,default=str))

if __name__=='__main__': main()
