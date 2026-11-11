#!/usr/bin/env python3
"""List and extract indexed evidence without executing any archived code."""
import argparse
import gzip
import hashlib
import json
import lzma
import sqlite3
import zlib
from pathlib import Path


def quote(s):
    return '"'+s.replace('"','""')+'"'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path,default=Path(__file__).with_name('research_dataset.sqlite'))
    sub=parser.add_subparsers(dest='action',required=True)
    listing=sub.add_parser('list');listing.add_argument('--case',type=int);listing.add_argument('--run')
    extracting=sub.add_parser('extract');extracting.add_argument('artifact_key');extracting.add_argument('output',type=Path)
    args=parser.parse_args()
    c=sqlite3.connect(args.db.resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
    c.execute('PRAGMA query_only=ON')
    if args.action=='list':
        clauses=[];values=[]
        if args.case is not None:clauses.append('case_id=?');values.append(args.case)
        if args.run is not None:clauses.append('run_id=?');values.append(args.run)
        sql='SELECT artifact_key,case_id,run_id,role,embedded,encoding,sha256 FROM review_artifact_index'
        if clauses:sql+=' WHERE '+' AND '.join(clauses)
        for row in c.execute(sql+' ORDER BY case_id,run_id,artifact_key',values):print(json.dumps(dict(row)))
        return
    a=c.execute('SELECT * FROM review_artifact_index WHERE artifact_key=?',(args.artifact_key,)).fetchone()
    if a is None:raise ValueError('Unknown artifact key')
    if not a['embedded']:raise ValueError('Payload not embedded in this row; consult locator and archive index')
    if args.output.exists():raise ValueError('Refusing to overwrite an existing output file')
    pk=json.loads(a['source_pk_json']);digest=hashlib.sha256();size=0
    tmp=args.output.with_name(args.output.name+'.partial')
    if tmp.exists():raise ValueError('Partial output already exists; choose a new destination')
    try:
        with tmp.open('xb') as f:
            if a['encoding']=='ordered_vault_chunks':
                chunks=c.execute('SELECT bytes,content_sha256 FROM study_archive_vault_chunks WHERE object_key=? ORDER BY sequence',(pk['object_key'],))
                for blob,sha in chunks:
                    if hashlib.sha256(blob).hexdigest()!=sha:raise ValueError('Vault chunk checksum mismatch')
                    f.write(blob);digest.update(blob);size+=len(blob)
            else:
                allowed={'study_imported_evidence_objects':'content_zlib','study_generated_patches':'patch_blob','study_sources':'embedded_bytes','study_evidence_assets':'content_zlib','study_rq_methodology_sources':'raw_zlib','study_rq3_owp14_original_artifacts':'source_zlib','study_rq3_owp14_verified_patch_bytes':'patch_zlib','study_rq3_owp14_verified_archive':'zip_zlib','study_rq3_owp14_original_transport':'raw_zlib','study_experiment_runs':'prompt_blob'}
                col=allowed.get(a['source_table'])
                if col!=a['payload_column']:raise ValueError('Unsupported payload table/column')
                sql='SELECT '+quote(col)+' FROM '+quote(a['source_table'])+' WHERE '+' AND '.join(quote(k)+'=?' for k in pk)
                row=c.execute(sql,list(pk.values())).fetchone()
                if row is None or row[0] is None:raise ValueError('Referenced payload is absent')
                raw=row[0].encode('utf-8') if isinstance(row[0],str) else bytes(row[0])
                enc=(a['encoding'] or '').lower()
                if enc in ('zlib','zlib/bytes','zlib/utf8'):
                    raw=zlib.decompress(raw)
                elif enc=='xz/json-utf8':raw=lzma.decompress(raw)
                elif enc in ('gzip','gz'):raw=gzip.decompress(raw)
                elif enc not in ('raw','utf-8','utf8','text','none','identity','csv/utf-8','json/utf-8','raw/original-file','raw/utf-8-sig;csv','original_gzip_tar'):raise ValueError('Unsupported encoding: '+enc)
                f.write(raw);digest.update(raw);size=len(raw)
        if a['sha256'] and digest.hexdigest()!=a['sha256']:raise ValueError('Artifact SHA-256 mismatch')
        if a['original_bytes'] is not None and size!=a['original_bytes']:raise ValueError('Artifact size mismatch')
        # Hard-link release refuses overwrite even if another process creates output now.
        import os
        os.link(tmp,args.output);tmp.unlink()
        print(json.dumps({'output':str(args.output),'bytes':size,'sha256':digest.hexdigest()}))
    except Exception:
        if tmp.exists():tmp.unlink()
        raise


if __name__=='__main__':main()
