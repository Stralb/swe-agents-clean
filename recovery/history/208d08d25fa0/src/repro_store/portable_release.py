"""Create a portable private reviewer DB with every SHA-addressed evidence byte.

Input vault is READ ONLY. Output must not exist. No experiments are run.
The standalone .sqlite duplicates external content-addressed objects as embedded
BLOBs so a reviewer can query/extract evidence with only one database file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from .store import EvidenceError, EvidenceStore


def build_portable(vault: Path, destination: Path) -> dict:
    vault=Path(vault).resolve()
    destination=Path(destination).resolve()
    if destination.exists():raise EvidenceError('Portable database exists: will not overwrite')
    if destination.parent==vault or vault in destination.parents:
        raise EvidenceError('Portable database must be outside original vault')
    original=EvidenceStore(vault)
    original_summary=original.verify()
    if original_summary['status']!='PASS':raise EvidenceError('Original input vault integrity failed')
    src=sqlite3.connect(original.db_path.as_uri()+'?mode=ro',uri=True)
    target=sqlite3.connect(destination)
    try:
        src.backup(target)
        target.execute('PRAGMA foreign_keys=ON')
        target.execute('''CREATE TABLE embedded_artifacts (
            sha256 TEXT PRIMARY KEY REFERENCES artifacts(sha256),
            bytes INTEGER NOT NULL,
            payload BLOB NOT NULL,
            CHECK(bytes=length(payload))
        )''')
        target.execute('''CREATE TRIGGER embedded_no_update BEFORE UPDATE ON embedded_artifacts
                   BEGIN SELECT RAISE(ABORT,'immutable embedded evidence'); END''')
        target.execute('''CREATE TRIGGER embedded_no_delete BEFORE DELETE ON embedded_artifacts
                   BEGIN SELECT RAISE(ABORT,'immutable embedded evidence'); END''')
        count=0
        all_bytes=0
        for digest,n,storage,rel in src.execute('''SELECT sha256,bytes,storage,object_relpath
                                               FROM artifacts WHERE storage='object' ORDER BY sha256'''):
            expected=f'objects/{digest[:2]}/{digest[2:]}'
            if rel!=expected:raise EvidenceError('Unexpected content path in source store')
            file=vault/expected
            if file.is_symlink() or not file.is_file():raise EvidenceError('Missing original object '+digest)
            cur=target.execute('INSERT INTO embedded_artifacts(sha256,bytes,payload) VALUES (?, ?, zeroblob(?))',
                               (digest,n,n))
            h=hashlib.sha256();size=0
            with target.blobopen('embedded_artifacts','payload',cur.lastrowid) as blob:
                with file.open('rb') as reader:
                    while True:
                        b=reader.read(1024*1024)
                        if not b:break
                        h.update(b);size+=len(b);blob.write(b)
            if h.hexdigest()!=digest or size!=n:
                raise EvidenceError('Source object byte hash mismatch '+digest)
            count+=1;all_bytes+=size
        target.commit()
        integrity=target.execute('PRAGMA integrity_check').fetchone()[0]
        if integrity!='ok':raise EvidenceError('Created portable DB is corrupt: '+integrity)
        fk=target.execute('PRAGMA foreign_key_check').fetchall()
        if fk:raise EvidenceError('Created portable DB has FK errors: '+str(fk[:3]))
        return {'status':'PRIVATE_PORTABLE_DATABASE_BUILT','portable_db':str(destination),
                'embedded_external_objects':count,'embedded_external_bytes':all_bytes,
                'artifacts_with_inline_original_bytes':src.execute("SELECT COUNT(*) FROM artifacts WHERE storage='inline'").fetchone()[0],
                'total_source_artifacts':original_summary['artifacts'],
                'bytes_verified_against_source_sha256':all_bytes,
                'independent_source_verification':'input vault prechecked; portable SHA verification required before release'}
    except Exception:
        target.close();destination.unlink(missing_ok=True)
        raise
    finally:
        src.close()
        try:target.close()
        except Exception:pass


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('original_vault',type=Path)
    p.add_argument('destination',type=Path)
    a=p.parse_args(argv)
    print(json.dumps(build_portable(a.original_vault,a.destination),indent=2))

if __name__=='__main__':main()
