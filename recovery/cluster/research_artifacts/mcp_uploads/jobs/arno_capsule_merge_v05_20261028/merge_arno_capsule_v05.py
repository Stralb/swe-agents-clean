#!/usr/bin/env python3
"""Merge the lossless 2026-10-28 recovered source capsule into the original Wits master.

This script never touches the original 29 Aug mined snapshot, only a specified
pre-existing ARNO_RESEARCH_MASTER.sqlite. It is strict and fails closed.

Usage (after transferring capsule alongside master):
 python3 merge_arno_capsule_v05.py --master /path/to/ARNO_RESEARCH_MASTER.sqlite \
   --capsule /path/to/ARNO_Research_Source_Evidence_Capsule_v05_20261028.sqlite \
   --report /path/to/merge_report.json
"""
import argparse, collections, datetime, hashlib, json, sqlite3, zlib
from pathlib import Path


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--master',required=True)
    ap.add_argument('--capsule',required=True)
    ap.add_argument('--report',required=True)
    args=ap.parse_args()
    master=Path(args.master).resolve()
    capsule=Path(args.capsule).resolve()
    report_path=Path(args.report).resolve()
    if master==capsule or master.name!='ARNO_RESEARCH_MASTER.sqlite':
        raise ValueError('Refusing noncanonical master or same master/capsule file')
    if not master.is_file() or not capsule.is_file():
        raise FileNotFoundError('Both existing master and source capsule are required')
    report={'status':'STARTED','master':str(master),'capsule':str(capsule),
            'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'capsule_sha256':hashlib.sha256(capsule.read_bytes()).hexdigest(),
            'operations':[]}
    c=sqlite3.connect(str(master),timeout=90)
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA busy_timeout=90000')
    try:
        c.execute('ATTACH DATABASE ? AS recovery',(f'file:{capsule}?mode=ro',))
        # Ensure the capsule itself is readable, not merely an arbitrary sqlite file.
        spec={k:json.loads(v) for k,v in c.execute('SELECT key,value FROM recovery.capsule_manifest')}
        if spec['role'].find('source evidence recovery capsule')<0:
            raise ValueError('Capsule role mismatch')
        expected=spec['checks']
        if expected['original_step1']!=605 or expected['original_step2']!=605 or expected['original_step3']!=322 or expected['new70_phase8']!=70 or expected['new70_phase9']!=70:
            raise ValueError('Source capsule counts are inconsistent')
        existing={
            'original_122':c.execute('SELECT COUNT(*) FROM arno_classifications').fetchone()[0],
            'new70_70':c.execute('SELECT COUNT(*) FROM arno_new70_source_inputs').fetchone()[0],
            'phase9_current_70':c.execute('SELECT COUNT(*) FROM arno_new70_phase9_risk').fetchone()[0],
            'frozen_broad_455':c.execute('SELECT COUNT(*) FROM arno_frozen_broad_attribution').fetchone()[0],
            'original_finding_ids_605':c.execute("SELECT COUNT(*) FROM arno_canonical_id_pc_links WHERE cohort='original122'").fetchone()[0],
        }
        if existing!={'original_122':122,'new70_70':70,'phase9_current_70':70,'frozen_broad_455':455,'original_finding_ids_605':605}:
            raise ValueError(f'Master not in expected restored state: {existing}')
        report['prior_master_counts']=existing
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='arno_recovery_v05_sources'").fetchone():
            raise ValueError('Capsule V05 appears already merged: refusing double import')
        # Every original first-cohort finding ID/case must match the already published mapping.
        mismatch=c.execute('''SELECT COUNT(*) FROM recovery.frozen_original_step1 s
            LEFT JOIN arno_canonical_id_pc_links l
              ON l.canonical_finding_id=s.canonical_finding_id AND l.cohort='original122'
            WHERE l.canonical_finding_id IS NULL OR l.case_id!=s.case_id''').fetchone()[0]
        if mismatch:raise ValueError(f'{mismatch} original Step1 identity conflicts')
        mismatch=c.execute('''SELECT COUNT(*) FROM recovery.frozen_original_step2 s
            LEFT JOIN arno_canonical_id_pc_links l
              ON l.canonical_finding_id=s.canonical_finding_id AND l.cohort='original122'
            WHERE l.canonical_finding_id IS NULL OR l.case_id!=s.case_id
              OR l.producing_change_id!=s.producing_change_id''').fetchone()[0]
        if mismatch:raise ValueError(f'{mismatch} original Step2 PC crosswalk conflicts')
        mismatch=c.execute('''SELECT COUNT(*) FROM recovery.frozen_original_step3 s
            LEFT JOIN arno_frozen_broad_attribution l
              ON l.producing_change_id=s.producing_change_id AND l.cohort='original122'
            WHERE l.producing_change_id IS NULL OR l.case_id!=s.case_id
              OR l.attribution!=s.final_attribution''').fetchone()[0]
        if mismatch:raise ValueError(f'{mismatch} original Step3 attribution conflicts')
        mismatch=c.execute('''SELECT COUNT(*) FROM recovery.frozen_new70_phase8 s
            LEFT JOIN arno_new70_source_inputs n ON n.case_id=s.case_id
            WHERE n.case_id IS NULL''').fetchone()[0]
        if mismatch:raise ValueError(f'{mismatch} Phase8 cases absent from frozen NEW70')
        mismatch=c.execute('''SELECT COUNT(*) FROM recovery.frozen_new70_phase9 s
            LEFT JOIN arno_new70_phase9_risk p ON p.case_id=s.case_id
            WHERE p.case_id IS NULL OR p.final_risk_label!=s.final_label
              OR p.first_pass_risk_label!=s.first_pass_label''').fetchone()[0]
        if mismatch:raise ValueError(f'{mismatch} Phase9 labels conflict with existing core import')
        report['crosswalk_conflicts']=0
        # Write new tables in a single transaction and keep all previous versions.
        c.execute('BEGIN IMMEDIATE')
        c.executescript('''
            CREATE TABLE arno_recovery_v05_sources (
              source_key TEXT PRIMARY KEY REFERENCES arno_sources(source_key),
              capsule_original_key TEXT NOT NULL, originating_member TEXT NOT NULL,
              original_bytes_size INTEGER NOT NULL,
              original_sha256 TEXT NOT NULL
            );
            CREATE TABLE arno_original_step1_detail (
              canonical_finding_id TEXT PRIMARY KEY REFERENCES arno_canonical_id_pc_links(canonical_finding_id),
              case_id INTEGER NOT NULL REFERENCES cases(id),rule_id TEXT,severity TEXT,scanner TEXT,
              finding_description TEXT,row_json TEXT NOT NULL,original_row_number INTEGER NOT NULL,
              source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
            );
            CREATE TABLE arno_original_step2_detail (
              canonical_finding_id TEXT PRIMARY KEY REFERENCES arno_original_step1_detail(canonical_finding_id),
              case_id INTEGER NOT NULL REFERENCES cases(id),source_producing_change_id TEXT NOT NULL,
              mapping_status TEXT,changed_locations TEXT,diff_evidence TEXT,
              row_json TEXT NOT NULL,original_row_number INTEGER NOT NULL,
              source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
            );
            CREATE TABLE arno_original_step3_detail (
              source_producing_change_id TEXT PRIMARY KEY,
              case_id INTEGER NOT NULL REFERENCES cases(id),first_pass_attribution TEXT,
              first_pass_basis TEXT,qc_correction TEXT,final_attribution TEXT NOT NULL,
              attribution_basis TEXT,attribution_reason TEXT,row_json TEXT NOT NULL,
              original_row_number INTEGER NOT NULL,source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
            );
            CREATE TABLE arno_original_case_synthesis (
              case_id INTEGER PRIMARY KEY REFERENCES arno_classifications(case_id),row_json TEXT NOT NULL,
              source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
            );
            CREATE TABLE arno_original_full_risk_source (
              case_id INTEGER PRIMARY KEY REFERENCES arno_classifications(case_id),row_json TEXT NOT NULL,
              source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
            );
            CREATE TABLE arno_new70_phase8_synthesis (
              case_id INTEGER PRIMARY KEY REFERENCES arno_new70_source_inputs(case_id),
              repository TEXT,case_evidence_summary TEXT,producing_change_profile TEXT,
              qc_status TEXT,qc_note TEXT,frozen_synthesis_input_sha256 TEXT,
              full_original_row_json TEXT NOT NULL,source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
            );
            CREATE TABLE arno_new70_phase9_full_source (
              case_id INTEGER PRIMARY KEY REFERENCES arno_new70_phase9_risk(case_id),
              complete_original_row_json TEXT NOT NULL,
              source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
            );
        ''')
        source_map={}
        for orig_name,fn,sha,blob,size,typ,parent,notes in c.execute('SELECT source_key,filename,sha256,raw_bytes,bytes_count,source_type,parent_source_key,notes FROM recovery.source_files'):
            raw=zlib.decompress(blob)
            if len(raw)!=size or hashlib.sha256(raw).hexdigest()!=sha:raise ValueError(f'Source bytes mismatch {orig_name}')
            key='recovery_v05:'+orig_name
            source_map[orig_name]=key
            c.execute('INSERT INTO arno_sources VALUES(?,?,?,?,?,?,?,?,?)',(
                key,'lossless_recovered_source',fn,
                'Uploaded 2026-10-28 source archive or workbook; capsule '+capsule.name,
                sha,'zlib/bytes',blob,'ORIGINAL_BYTES_VERIFIED',notes
            ))
            c.execute('INSERT INTO arno_recovery_v05_sources VALUES(?,?,?,?,?)',(
                key,orig_name,fn,size,sha))
        def insert_batch(sql,rows):
            c.executemany(sql,rows)
            report['operations'].append({'rows_imported':len(rows),'destination_sql':sql.split('VALUES')[0][:125]})
        step1=list(c.execute('SELECT canonical_finding_id,case_id,rule_id,severity,scanner,description,original_row_json,source_row_number FROM recovery.frozen_original_step1'))
        insert_batch('INSERT INTO arno_original_step1_detail VALUES(?,?,?,?,?,?,?,?,?)',[(x[0],*x[1:],source_map['first122_workbook_raw']) for x in step1])
        step2=list(c.execute('SELECT canonical_finding_id,case_id,producing_change_id,mapping_status,changed_locations,diff_evidence,original_row_json,source_row_number FROM recovery.frozen_original_step2'))
        insert_batch('INSERT INTO arno_original_step2_detail VALUES(?,?,?,?,?,?,?,?,?)',[(x[0],*x[1:],source_map['first122_workbook_raw']) for x in step2])
        step3=list(c.execute('SELECT producing_change_id,case_id,first_pass_attribution,first_pass_basis,qc_correction,final_attribution,attribution_basis,attribution_reason,original_row_json,source_row_number FROM recovery.frozen_original_step3'))
        insert_batch('INSERT INTO arno_original_step3_detail VALUES(?,?,?,?,?,?,?,?,?,?,?)',[(x[0],*x[1:],source_map['first122_workbook_raw']) for x in step3])
        for sheet,table in [('Case_Synthesis','arno_original_case_synthesis'),('Risk_Assessment','arno_original_full_risk_source')]:
            source=list(c.execute('SELECT case_id,original_row_json FROM recovery.source_rows WHERE source_key=? AND sheet_or_member=? ORDER BY row_number',('first122_workbook_raw',sheet)))
            insert_batch(f'INSERT INTO {table} VALUES(?,?,?)',[(x[0],x[1],source_map['first122_workbook_raw']) for x in source])
        ph8=list(c.execute('SELECT case_id,repository,case_evidence_summary,producing_change_profile,qc_status,qc_note,frozen_synthesis_input_sha256,original_row_json FROM recovery.frozen_new70_phase8'))
        insert_batch('INSERT INTO arno_new70_phase8_synthesis VALUES(?,?,?,?,?,?,?,?,?)',[(x[0],*x[1:],source_map['zip_member:NEW70_Phase9_Risk_Input_FROZEN_v1.0.csv']) for x in ph8])
        ph9=list(c.execute('SELECT case_id,original_row_json FROM recovery.frozen_new70_phase9'))
        insert_batch('INSERT INTO arno_new70_phase9_full_source VALUES(?,?,?)',[(x[0],x[1],source_map['zip_member:NEW70_Phase9_Risk_Assessment_FINAL_v1.0.csv']) for x in ph9])
        update=datetime.datetime.now(datetime.timezone.utc).isoformat()
        c.execute("UPDATE arno_stage_ledger SET detail=detail||'; V05 lossless 605 Step1,605 Step2,322 Step3 originals,122 case/risk source rows and original full workbook source embedded',last_updated_utc=? WHERE stage_number=2",(update,))
        c.execute("UPDATE arno_stage_ledger SET detail=detail||'; V05 complete Phase8 input and Phase9 full 16-column source plus original ZIP and all 10 archive members embedded',last_updated_utc=? WHERE stage_number=3",(update,))
        c.execute("UPDATE arno_stage_ledger SET detail=detail||'; V05 original 605 Step1 detailed rows,605 Step2 detailed mapping rows,322 Step3 exact first-pass/QC rows imported; final NEW70 237 canonical still missing',last_updated_utc=? WHERE stage_number=4",(update,))
        c.commit()
        # Verify after commit using table-specific foreign key checks (avoid full 37GB DB scan).
        new_tables=['arno_recovery_v05_sources','arno_original_step1_detail','arno_original_step2_detail','arno_original_step3_detail','arno_original_case_synthesis','arno_original_full_risk_source','arno_new70_phase8_synthesis','arno_new70_phase9_full_source']
        report['post_counts']={name:c.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in new_tables}
        report['new_foreign_key_violations']={name:len(c.execute('PRAGMA foreign_key_check('+name+')').fetchall()) for name in new_tables}
        report['sha_source_bytes_verified']=all(hashlib.sha256(zlib.decompress(x[0])).hexdigest()==x[1] for x in c.execute("SELECT embedded_bytes,source_sha256 FROM arno_sources WHERE source_key LIKE 'recovery_v05:%'"))
        if sum(report['new_foreign_key_violations'].values()) or not report['sha_source_bytes_verified']:
            raise RuntimeError('Post-commit validation mismatch; inspect before further operations')
        expected_counts={'arno_recovery_v05_sources':12,'arno_original_step1_detail':605,'arno_original_step2_detail':605,'arno_original_step3_detail':322,'arno_original_case_synthesis':122,'arno_original_full_risk_source':122,'arno_new70_phase8_synthesis':70,'arno_new70_phase9_full_source':70}
        if report['post_counts']!=expected_counts:raise RuntimeError('Post-commit row count mismatch')
        report['status']='COMPLETE'
    except Exception as ex:
        try:c.rollback()
        except Exception:pass
        report['status']='FAILED';report['error']=type(ex).__name__+': '+str(ex)
        raise
    finally:
        c.close()
        report_path.parent.mkdir(parents=True,exist_ok=True)
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
