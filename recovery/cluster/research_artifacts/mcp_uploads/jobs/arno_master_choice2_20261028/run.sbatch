#!/bin/bash
#SBATCH --job-name=arno_choice_stage
#SBATCH --partition=stampede
#SBATCH --time=00:10:00
#SBATCH --mem=3G
python3 - <<'PY'
import csv,io,json,hashlib,zlib,sqlite3,collections,datetime
from pathlib import Path
base=Path.home()/'research_artifacts'
inputs={
'choice73':base/'implementation_choice_phase1_v1_0_49121/01_ELIGIBLE_73_PCS_45_CASES.csv',
'choice45':base/'implementation_choice_phase1_v1_0_49121/02_CASE_SPLIT_FROZEN.csv',
'choice_manifest':base/'implementation_choice_phase1_v1_0_49121/PHASE1_SELECTION_MANIFEST.json',
'pilot31_packets':base/'implementation_choice_phase2_v1_0_49124/PHASE2_CONTEXT_PACKETS_31.jsonl',
'holdout42_packets':base/'implementation_choice_phase5_holdout_v1_0_49129/PHASE5_HOLDOUT_CONTEXT_PACKETS_42.jsonl'}
out=base/'mcp_uploads/jobs/arno_master_choice2_20261028'
out.mkdir(parents=True,exist_ok=True)
report={'status':'STARTED','scope':'Frozen choice-study split/context; no new classifications'}
try:
 bs={k:p.read_bytes() for k,p in inputs.items()}
 def parse(k):return list(csv.DictReader(io.StringIO(bs[k].decode('utf-8-sig'))))
 pcs=parse('choice73');cases=parse('choice45')
 ids={x['Study Producing Change ID'] for x in pcs}
 split={int(x['Case ID']):x for x in cases}
 assert len(pcs)==len(ids)==73 and len(split)==45 and {int(x['Case ID']) for x in pcs}==set(split)
 assert collections.Counter(x['Study Partition'].upper() for x in pcs)=={'PILOT':31,'HOLDOUT':42}
 assert collections.Counter(x['Split'].upper() for x in cases)=={'PILOT':20,'HOLDOUT':25}
 assert all(x['Study Partition'].upper()==split[int(x['Case ID'])]['Split'].upper() for x in pcs)
 conn=sqlite3.connect(str(base/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'),timeout=45)
 conn.execute('PRAGMA foreign_keys=ON')
 assert conn.execute('SELECT COUNT(*) FROM arno_mechanism_selection').fetchone()[0]==455
 assert sum(conn.execute('SELECT EXISTS(SELECT 1 FROM arno_mechanism_selection WHERE decision_id=?)',(x,)).fetchone()[0] for x in ids)==73
 conn.execute('''CREATE TABLE arno_choice_case_split(
 case_id INTEGER PRIMARY KEY REFERENCES cases(id),partition TEXT NOT NULL,
 rank INTEGER UNIQUE NOT NULL,selection_hash TEXT UNIQUE NOT NULL,
 pc_count INTEGER NOT NULL,row_json TEXT NOT NULL,
 source_key TEXT NOT NULL REFERENCES arno_sources(source_key))''')
 conn.execute('''CREATE TABLE arno_choice_eligible_pc(
 pc_id TEXT PRIMARY KEY REFERENCES arno_mechanism_selection(decision_id),
 case_id INTEGER NOT NULL REFERENCES arno_choice_case_split(case_id),
 partition TEXT NOT NULL,row_json TEXT NOT NULL,
 source_key TEXT NOT NULL REFERENCES arno_sources(source_key))''')
 for k,raw in bs.items():
  conn.execute('INSERT INTO arno_sources VALUES(?,?,?,?,?,?,?,?,?)',(
   k,'frozen_choice_study_input',k,str(inputs[k]),hashlib.sha256(raw).hexdigest(),
   'zlib/bytes',zlib.compress(raw,9),'EMBEDDED_FROZEN','Not derived outcomes'))
 for x in cases:
  conn.execute('INSERT INTO arno_choice_case_split VALUES(?,?,?,?,?,?,?)',(
   int(x['Case ID']),x['Split'].upper(),int(x['Selection Rank']),
   x['Selection Hash'],int(x['Eligible Producing Changes In Case']),
   json.dumps(x,ensure_ascii=False),'choice45'))
 for x in pcs:
  conn.execute('INSERT INTO arno_choice_eligible_pc VALUES(?,?,?,?,?)',(
   x['Study Producing Change ID'],int(x['Case ID']),x['Study Partition'].upper(),
   json.dumps(x,ensure_ascii=False),'choice73'))
 conn.execute("UPDATE arno_stage_ledger SET detail=detail||'; added 73-PC/45-case frozen choice split, pilot31 and holdout42 context packets',last_updated_utc=? WHERE stage_number=5",(
  datetime.datetime.now(datetime.timezone.utc).isoformat(),))
 conn.commit()
 report['pcs']=conn.execute('SELECT COUNT(*) FROM arno_choice_eligible_pc').fetchone()[0]
 report['cases']=conn.execute('SELECT COUNT(*) FROM arno_choice_case_split').fetchone()[0]
 report['foreign_key_errors']=len(conn.execute('PRAGMA foreign_key_check(arno_choice_eligible_pc)').fetchall())
 report['source_sha256_ok']=all(hashlib.sha256(zlib.decompress(conn.execute('SELECT embedded_bytes FROM arno_sources WHERE source_key=?',(k,)).fetchone()[0])).hexdigest()==hashlib.sha256(v).hexdigest() for k,v in bs.items())
 conn.close()
 if report['pcs']!=73 or report['cases']!=45 or report['foreign_key_errors'] or not report['source_sha256_ok']:raise ValueError('QC mismatch')
 report['status']='COMPLETE'
except Exception as e:
 report['status']='FAILED';report['error']=str(e)
 raise
finally:
 (out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))
PY