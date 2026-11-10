#!/usr/bin/env python3
"""Add exactly the locally audited C5/C6/C7/T1 evidence tables to a pre-existing Wits master SQLite.
Additive, checks frozen C2 pair identities before BEGIN IMMEDIATE. No overwrites/updates.
Usage: python import_rq2_t1_delta_into_master.py MASTER.sqlite RQ2_T1_DELTA.sqlite
"""
from pathlib import Path
import sqlite3,sys,hashlib,zlib,json
TABLES=['arno_evidence_assets','arno_rq2_c5_controls','arno_rq2_c5_corrections','arno_rq2_c5_stability',
'arno_rq2_c6_pairs','arno_rq2_c6_omnibus','arno_rq2_c6_contingency','arno_rq2_c7_pathways',
'arno_rq3_t1_blind_pairs','arno_rq3_t1_blind_sides','arno_rq2_c6_reproduced_tests','arno_publication_evidence_status']
EXPECTED={'arno_rq2_c5_controls':190,'arno_rq2_c5_corrections':42,'arno_rq2_c6_pairs':190,
'arno_rq2_c6_omnibus':9,'arno_rq2_c6_contingency':165,'arno_rq2_c6_reproduced_tests':9,'arno_rq2_c7_pathways':190,'arno_rq3_t1_blind_pairs':29,'arno_rq3_t1_blind_sides':58,'arno_evidence_assets':40}
sha=lambda b:hashlib.sha256(b).hexdigest()
def run(master,delta):
    master=Path(master).expanduser().resolve();delta=Path(delta).expanduser().resolve()
    if not master.is_file() or not delta.is_file() or master==delta:raise RuntimeError('Existing, distinct master/delta files required')
    c=sqlite3.connect(str(master),timeout=180)
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA busy_timeout=180000')
    c.execute('ATTACH DATABASE ? AS delta',(f'file:{delta}?mode=ro',))
    try:
        sqlnames={r[0] for r in c.execute("SELECT name FROM delta.sqlite_master WHERE type='table'")}
        if not set(TABLES).issubset(sqlnames):raise RuntimeError('Required delta source tables missing')
        if c.execute('PRAGMA delta.foreign_key_check').fetchall() or c.execute('PRAGMA delta.quick_check').fetchone()[0]!='ok':raise RuntimeError('Delta integrity check failed')
        for table,n in EXPECTED.items():
            if c.execute('SELECT COUNT(*) FROM delta.'+table).fetchone()[0]!=n:raise RuntimeError('Delta count failed: '+table)
        if not all(sha(zlib.decompress(b))==h for h,b in c.execute('SELECT source_sha256,content_zlib FROM delta.arno_evidence_assets')):
            raise RuntimeError('Embedded original source hash failure')
        mainnames={r[0] for r in c.execute("SELECT name FROM main.sqlite_master WHERE type='table'")}
        if 'arno_matched_control_pairs_C2' not in mainnames or 'cases' not in mainnames:raise RuntimeError('Wrong master: missing frozen C2/cases')
        wanted={(r[0],r[1],r[2]) for r in c.execute('SELECT positive_case_id,control_case_id,control_blind_id FROM delta.arno_rq2_c6_pairs')}
        actual={(r[0],r[1],r[2]) for r in c.execute('SELECT positive_case_id,control_case_id,blind_id FROM main.arno_matched_control_pairs_C2')}
        if wanted!=actual:raise RuntimeError('FROZEN MATCH ID MISMATCH: C5/C6 not the same C2 cohort; refusing import. Missing='+str(sorted(wanted-actual)[:6])+' extra='+str(sorted(actual-wanted)[:6]))
        wanted_cases={r[0] for r in c.execute('SELECT positive_case_id FROM delta.arno_rq2_c6_pairs')}|{r[0] for r in c.execute('SELECT control_case_id FROM delta.arno_rq2_c6_pairs')}
        master_cases={r[0] for r in c.execute('SELECT id FROM main.cases')}
        if wanted_cases-master_cases:raise RuntimeError('Some case IDs absent from master: '+str(sorted(wanted_cases-master_cases)[:10]))
        present=[x for x in TABLES if x in mainnames]
        if present:
            if len(present)!=len(TABLES):raise RuntimeError('Partial evidence import; manual reconciliation required; no overwrite')
            for t in TABLES:
                if c.execute('SELECT COUNT(*) FROM main.'+t).fetchone()[0]!=c.execute('SELECT COUNT(*) FROM delta.'+t).fetchone()[0]:raise RuntimeError('Existing evidence table row count mismatch: '+t)
            mainhash=dict(c.execute('SELECT source_path,source_sha256 FROM main.arno_evidence_assets'))
            deltahash=dict(c.execute('SELECT source_path,source_sha256 FROM delta.arno_evidence_assets'))
            if mainhash!=deltahash:raise RuntimeError('Existing evidence SHA mismatches')
            print(json.dumps({'status':'ALREADY_IMPORTED_VERIFIED','tables':len(TABLES),'frozen_pairs':len(wanted)}));return
        c.execute('BEGIN IMMEDIATE')
        try:
            for t in TABLES:
                ddl=c.execute("SELECT sql FROM delta.sqlite_master WHERE type='table' AND name=?",(t,)).fetchone()[0]
                if not ddl.startswith('CREATE TABLE '+t+'('):raise RuntimeError('Unexpected schema in delta: '+t)
                c.execute(ddl)
                ncol=len(c.execute('PRAGMA table_info('+t+')').fetchall())
                c.executemany('INSERT INTO main.'+t+' VALUES('+','.join('?'*ncol)+')',c.execute('SELECT * FROM delta.'+t).fetchall())
            for t in TABLES:
                if c.execute('PRAGMA foreign_key_check('+t+')').fetchall():raise RuntimeError('Foreign-key check failed '+t)
            c.commit()
        except:
            c.rollback();raise
        print(json.dumps({'status':'IMPORTED_VERIFIED','new_tables':len(TABLES),'matched_pairs':190,'control_corrections':42,'C6_primary_comparisons':9,'C6_primary_p_values_independently_reproduced':9,'T1_blind_pairs':29,'T1_blind_sides':58,'all_C2_pair_ids_equal':True,'preserved_raw_sha256':True,'prior_tables_untouched':True},indent=2))
    finally:c.close()
if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('Usage: python import_rq2_t1_delta_into_master.py MASTER.sqlite RQ2_T1_DELTA.sqlite')
    run(sys.argv[1],sys.argv[2])
