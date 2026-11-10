#!/bin/bash
#SBATCH --job-name=arno_root_lineage
#SBATCH --partition=stampede
#SBATCH --time=00:10:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
python3 - <<'PY'
from pathlib import Path
import csv, io, json, hashlib, zlib, sqlite3, datetime, collections
root=Path.home()/'research_artifacts'
src=root/'D_COMPLETE_ROOT_PROVENANCE_v1_0/01_INPUT'
db=root/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'
out=root/'mcp_uploads/jobs/arno_master_mechanism_root_v01_20261028'
out.mkdir(parents=True,exist_ok=True)
sources={
 'c5_pc_to_root_final':src/'C5_PC_TO_ROOT_FINAL.csv',
 'c6_root_census':src/'C6_ROOT_CENSUS.csv',
 'd1_root_index':src/'D1_ROOT_INDEX_342.csv',
 'd1_root_pc_crosswalk':src/'D1_ROOT_PC_EVIDENCE_CROSSWALK_455.csv'
}
report={'status':'STARTED','scope':'FROZEN C5/C6 and D1 mechanism/provenance crosswalk; not final causal adjudication','paths':{k:str(x) for k,x in sources.items()}}
try:
    blob={k:x.read_bytes() for k,x in sources.items()}
    def parse(k):return list(csv.DictReader(io.StringIO(blob[k].decode('utf-8-sig'))))
    c5=parse('c5_pc_to_root_final')
    c6=parse('c6_root_census')
    d1=parse('d1_root_index')
    links=parse('d1_root_pc_crosswalk')
    ids5={x['PC ID'] for x in c5}
    idsL={x['C_PC ID'] for x in links}
    roots6={x['Root ID'] for x in c6}
    roots1={x['Root ID'] for x in d1}
    assert len(c5)==len(links)==len(ids5)==len(idsL)==455,('PC mismatch',len(c5),len(links))
    assert ids5==idsL
    assert len(c6)==len(d1)==len(roots6)==len(roots1)==342
    assert roots6==roots1
    assert {x['Root ID'] for x in c5}<=roots6
    case_ids={int(x['Case ID']) for x in c5}
    assert len(case_ids)==191
    index={x['C_PC ID']:x for x in links}
    c5index={x['PC ID']:x for x in c5}
    for pc,r in c5index.items():
        if r['Root ID']!=index[pc]['C_Root ID'] or int(r['Case ID'])!=int(index[pc]['C_Case ID']):
            raise ValueError('D1/C5 mapping mismatch at '+pc)
    con=sqlite3.connect(str(db),timeout=40)
    con.execute('PRAGMA foreign_keys=ON')
    con.execute('PRAGMA busy_timeout=40000')
    if con.execute('SELECT COUNT(*) FROM arno_classifications').fetchone()[0]!=122:raise ValueError('first122 lost')
    if con.execute('SELECT COUNT(*) FROM arno_new70_source_inputs').fetchone()[0]!=70:raise ValueError('new70 source missing')
    if con.execute('SELECT COUNT(*) FROM arno_root_decisions').fetchone()[0]!=0:raise ValueError('root rows already exist')
    if con.execute('SELECT COUNT(*) FROM arno_mechanism_selection').fetchone()[0]!=0:raise ValueError('mechanism rows already exist')
    all_cases={i[0] for i in con.execute('SELECT id FROM cases WHERE id IN ('+','.join('?' for _ in case_ids)+')',tuple(case_ids))}
    if all_cases!=case_ids:raise ValueError('Missing root case foreign keys')
    con.execute('''CREATE TABLE arno_pc_root_lineage(
       producing_change_id TEXT PRIMARY KEY,
       case_id INTEGER NOT NULL REFERENCES cases(id),
       root_id TEXT NOT NULL REFERENCES arno_root_decisions(root_id),
       original_c5_row_json TEXT NOT NULL,
       source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
    )''')
    for k,raw in blob.items():
        con.execute('INSERT INTO arno_sources VALUES(?,?,?,?,?,?,?,?,?)',(
            k,'frozen_classification_or_linkage_csv',k,str(sources[k]),
            hashlib.sha256(raw).hexdigest(),'zlib/bytes',zlib.compress(raw,9),
            'ROW_COUNT_ID_JOIN_VERIFIED','Frozen historical records; no new annotation or inferred causal conclusion'))
    for r in c6:
        con.execute('''INSERT INTO arno_root_decisions
         (root_id,case_id,mechanism_decision_id,producing_change_ids_json,root_coding_json,evidence_source_key,coding_status)
         VALUES(?,?,?,?,?,?,?)''',(
            r['Root ID'],int(r['Case ID']),None,
            json.dumps([x.strip() for x in r['Producing Change IDs'].split(';') if x.strip()]),
            json.dumps(r,ensure_ascii=False,sort_keys=True),
            'c6_root_census','FROZEN_C6_ROOT_CENSUS_NOT_FINAL_D_CODING'))
    for r in c5:
        key=r['PC ID'];d=index[key]
        con.execute('''INSERT INTO arno_mechanism_selection
         (decision_id,case_id,producing_change_id,choice_summary,evidence_json,evidence_source_key,coding_status)
         VALUES(?,?,?,?,?,?,?)''',(
           key,int(r['Case ID']),key,
           d.get('PROV_Security-Relevant Mechanism') or r.get('Finding-Producing Change'),
           json.dumps(d,ensure_ascii=False,sort_keys=True),'d1_root_pc_crosswalk',
           'FROZEN_PROV_PHASE7_RECORD_NOT_INDEPENDENT_CAUSAL_DECISION'))
        con.execute('INSERT INTO arno_pc_root_lineage VALUES(?,?,?,?,?)',(
            key,int(r['Case ID']),r['Root ID'],json.dumps(r,ensure_ascii=False,sort_keys=True),
            'c5_pc_to_root_final'))
    utc=datetime.datetime.now(datetime.timezone.utc).isoformat()
    con.execute("UPDATE arno_stage_ledger SET status='partial',detail=?,last_updated_utc=? WHERE stage_number=4",(
       '455 frozen mapped producing changes imported; 122 and 70 canonical-finding rows not yet completely imported',utc))
    con.execute("UPDATE arno_stage_ledger SET status='partial',detail=?,last_updated_utc=? WHERE stage_number=5",(
       '455 phase7 mechanism/provenance evidence rows imported; implementation-choice pilot/holdout decision coding pending',utc))
    con.execute("UPDATE arno_stage_ledger SET status='partial',detail=?,last_updated_utc=? WHERE stage_number=6",(
       '342 frozen C6 root census rows and 455 PC->root links imported; later D final root adjudications pending',utc))
    con.commit()
    report['counts']={
      'pc_mechanism_rows':con.execute('SELECT COUNT(*) FROM arno_mechanism_selection').fetchone()[0],
      'root_rows':con.execute('SELECT COUNT(*) FROM arno_root_decisions').fetchone()[0],
      'pc_root_links':con.execute('SELECT COUNT(*) FROM arno_pc_root_lineage').fetchone()[0],
      'workflow_count':con.execute('SELECT COUNT(DISTINCT case_id) FROM arno_pc_root_lineage').fetchone()[0],
      'distinct_linked_roots':con.execute('SELECT COUNT(DISTINCT root_id) FROM arno_pc_root_lineage').fetchone()[0],
      'first122':con.execute('SELECT COUNT(*) FROM arno_classifications').fetchone()[0],
      'new70_source_inputs':con.execute('SELECT COUNT(*) FROM arno_new70_source_inputs').fetchone()[0]
    }
    report['foreign_key_violations']=sum(len(con.execute('PRAGMA foreign_key_check('+t+')').fetchall()) for t in ('arno_mechanism_selection','arno_root_decisions','arno_pc_root_lineage'))
    report['embedded_sha_match']={k:hashlib.sha256(zlib.decompress(con.execute('SELECT embedded_bytes FROM arno_sources WHERE source_key=?',(k,)).fetchone()[0])).hexdigest()==hashlib.sha256(raw).hexdigest() for k,raw in blob.items()}
    con.close()
    expected={'pc_mechanism_rows':455,'root_rows':342,'pc_root_links':455,'workflow_count':191,'distinct_linked_roots':342,'first122':122,'new70_source_inputs':70}
    if report['counts']!=expected or report['foreign_key_violations'] or not all(report['embedded_sha_match'].values()):
        raise RuntimeError('Post-insert validation mismatch: '+str(report))
    report['status']='COMPLETE'
except Exception as exc:
    report['status']='FAILED';report['error']=type(exc).__name__+': '+str(exc)
    raise
finally:
    (out/'MECHANISM_ROOT_IMPORT_REPORT.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(report,indent=2,ensure_ascii=False),flush=True)
PY