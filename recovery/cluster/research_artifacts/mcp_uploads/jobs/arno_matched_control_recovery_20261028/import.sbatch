#!/bin/bash
#SBATCH --job-name=arno_C1_C2_C3_recover
#SBATCH --partition=stampede
#SBATCH --time=00:18:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=5G
python3 - <<'PY'
from pathlib import Path
import csv,io,hashlib,zlib,json,sqlite3,collections,datetime
root=Path.home()/'research_artifacts'
out=root/'mcp_uploads/jobs/arno_matched_control_recovery_20261028'
out.mkdir(parents=True,exist_ok=True)
db=root/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'
c1=root/'matched_control_c1_v1_1'
c2=root/'matched_control_c2_v1_0'
c3=root/'matched_control_c3_v1_0'
sources={
 'controls_C1_3809_opportunities':c1/'C1_CASE_SCANNER_OPPORTUNITY_3809.csv',
 'controls_C1_summary':c1/'C1_SUMMARY.json',
 'controls_C2_190_pairs':c2/'C2_MATCHED_PAIRS_FROZEN.csv',
 'controls_C2_summary':c2/'C2_SUMMARY.json',
 'controls_C2_audit':c2/'C2_AUDIT.json',
 'controls_C2_unmatched2':c2/'C2_UNMATCHED_POSITIVES.csv',
 'controls_C3_locked_id_map':c3/'90_LOCKED_MATCHING/C3_BLIND_ID_MAP_LOCKED.csv',
 'controls_C3_manifest_blind':c3/'C3_CONTROL_MANIFEST_BLINDED.csv',
 'controls_C3_issue_blind':c3/'01_ISSUE_BLIND/C3_ISSUE_BLIND_190.csv',
 'controls_C3_pr_blind':c3/'02_PR_BLIND/C3_PR_BLIND_190.csv',
 'controls_C3_context_raw':c3/'04_CONTEXT_SEPARATE/C3_CONTEXT_RAW_190.csv',
 'controls_C3_audit':c3/'99_QC/C3_AUDIT.json'
}
report={'status':'STARTED','scope':'Frozen C1 feasibility, C2 matched controls, C3 blinded inputs; no control annotation outcomes inferred.'}
try:
 blob={name:p.read_bytes() for name,p in sources.items()}
 def rows(k):return list(csv.DictReader(io.StringIO(blob[k].decode('utf-8-sig'))))
 opp=rows('controls_C1_3809_opportunities')
 pairs=rows('controls_C2_190_pairs')
 missed=rows('controls_C2_unmatched2')
 locked=rows('controls_C3_locked_id_map')
 blind=rows('controls_C3_manifest_blind')
 issues=rows('controls_C3_issue_blind')
 prs=rows('controls_C3_pr_blind')
 context=rows('controls_C3_context_raw')
 summary=json.loads(blob['controls_C2_summary'])
 audit=json.loads(blob['controls_C2_audit'])
 caudit=json.loads(blob['controls_C3_audit'])
 ids={int(r['positive_case_id']) for r in pairs}
 ctrlids={int(r['control_case_id']) for r in pairs}
 missids={int(r['positive_case_id']) for r in missed}
 alias={r['blind_id']:r for r in locked}
 if len(opp)!=3809 or len(pairs)!=len(ids)!=190 or len(ctrlids)!=190 or len(missed)!=2 or len(alias)!=190:
  raise ValueError('C1/C2/C3 cardinality does not match frozen audit')
 if missids!={13918,17460} or (ids & missids) or len(ids | missids)!=192:raise ValueError('C2 missing positive lineage')
 if summary['matched_pairs']!=190 or summary['positive_cases']!=192 or summary['unmatched_positives']!=2 or not audit['qc_pass'] or not caudit['qc_pass']:
  raise ValueError('C2/C3 original QC invalid')
 if hashlib.sha256(blob['controls_C1_3809_opportunities']).hexdigest()!=audit['expected_input_sha256']:
  raise ValueError('C1 source hash differs from frozen C2 audit')
 if hashlib.sha256(blob['controls_C2_190_pairs']).hexdigest()!=caudit['pairs_sha256']:
  raise ValueError('C2 pairs source hash differs from frozen C3 audit')
 c2pairs={(int(x['positive_case_id']),int(x['control_case_id']),x['match_tier']) for x in pairs}
 c3pairs={(int(x['positive_case_id']),int(x['control_case_id']),x['match_tier']) for x in locked}
 if c2pairs!=c3pairs:raise ValueError('C2->C3 locked map pair mismatch')
 for arr,desc in ((blind,'blinded manifest'),(issues,'issue blind'),(prs,'PR blind'),(context,'context raw')):
  vals={x['blind_id'] for x in arr}
  if len(arr)!=190 or vals!=set(alias):raise ValueError(desc+' ID mismatch')
 raw_impl=c3/'03_IMPLEMENTATION_FULL_RAW'
 blind_impl=c3/'03_IMPLEMENTATION_BLIND'
 packets={}
 for kind,directory in [('raw',raw_impl),('blind',blind_impl)]:
  if not directory.is_dir():raise ValueError('Missing C3 implementation directory '+str(directory))
  files={p.stem:p for p in directory.iterdir() if p.is_file() and p.suffix=='.txt'}
  if set(files)!=set(alias):
   raise ValueError('C3 '+kind+' implementation files missing '+str(sorted(set(alias)-set(files))[:20])+' unexpected '+str(sorted(set(files)-set(alias))[:20]))
  packets[kind]=files
 con=sqlite3.connect(str(db),timeout=90)
 con.execute('PRAGMA foreign_keys=ON')
 con.execute('PRAGMA busy_timeout=90000')
 historical={r[0] for r in con.execute("SELECT case_id FROM arno_classifications")} | {r[0] for r in con.execute("SELECT case_id FROM arno_new70_source_inputs")}
 if historical!=(ids|missids):raise ValueError('C2 positive cases do not cover exactly historical 192')
 originalcases={r[0] for r in con.execute('SELECT id FROM cases')}
 if {int(x['case_id']) for x in opp}!=originalcases or not ctrlids.issubset(originalcases) or (ctrlids & historical):
  raise ValueError('C1/C2 case ID lineage mismatch or overlap with positives')
 def asdict(arr,field='blind_id'):
  return {r[field]:r for r in arr}
 im=asdict(issues);pm=asdict(prs);cm=asdict(context);bm=asdict(blind)
 pairs_by_control={int(x['control_case_id']):x for x in pairs}
 now=datetime.datetime.now(datetime.timezone.utc).isoformat()
 con.execute('BEGIN IMMEDIATE')
 con.execute('''CREATE TABLE arno_matched_control_pairs_C2(
    positive_case_id INTEGER PRIMARY KEY REFERENCES cases(id),
    control_case_id INTEGER NOT NULL UNIQUE REFERENCES cases(id),
    blind_id TEXT NOT NULL UNIQUE,
    match_tier TEXT NOT NULL,
    same_repository INTEGER NOT NULL CHECK(same_repository IN(0,1)),
    positive_repository TEXT,control_repository TEXT,
    opportunity_relation TEXT,
    normalized_distance REAL,
    original_C2_row_json TEXT NOT NULL,
    original_C3_locked_row_json TEXT NOT NULL,
    source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
    provenance_kind TEXT NOT NULL DEFAULT 'C2_MATCHED_CONTROL_NOT_OUTCOME')''')
 con.execute('''CREATE TABLE arno_matched_control_unmatched_C2(
    positive_case_id INTEGER PRIMARY KEY REFERENCES cases(id),
    reason TEXT NOT NULL,original_row_json TEXT NOT NULL,
    source_key TEXT NOT NULL REFERENCES arno_sources(source_key))''')
 con.execute('''CREATE TABLE arno_matched_control_C1_opportunity(
    case_id INTEGER PRIMARY KEY REFERENCES cases(id),
    is_positive INTEGER NOT NULL CHECK(is_positive IN(0,1)),
    scanner_opportunity_signature TEXT,
    source_row_json TEXT NOT NULL,
    source_key TEXT NOT NULL REFERENCES arno_sources(source_key))''')
 con.execute('''CREATE TABLE arno_matched_control_C3_blind_inputs(
    blind_id TEXT PRIMARY KEY,
    positive_case_id INTEGER NOT NULL REFERENCES arno_matched_control_pairs_C2(positive_case_id),
    control_case_id INTEGER NOT NULL UNIQUE REFERENCES cases(id),
    issue_blind_json TEXT NOT NULL,
    pr_blind_json TEXT NOT NULL,
    context_raw_json TEXT NOT NULL,
    blinded_manifest_json TEXT NOT NULL,
    source_key TEXT NOT NULL REFERENCES arno_sources(source_key))''')
 con.execute('''CREATE TABLE arno_matched_control_C3_impl_packets(
    blind_id TEXT NOT NULL REFERENCES arno_matched_control_C3_blind_inputs(blind_id),
    packet_kind TEXT NOT NULL CHECK(packet_kind IN('raw','blind')),
    original_sha256 TEXT NOT NULL,
    byte_count INTEGER NOT NULL,
    compressed_bytes BLOB NOT NULL,
    source_path TEXT NOT NULL,
    source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
    PRIMARY KEY(blind_id,packet_kind))''')
 for k,raw in blob.items():
  con.execute('INSERT INTO arno_sources VALUES(?,?,?,?,?,?,?,?,?)',(
   k,'frozen_C1_C2_C3_matched_control_source',k,str(sources[k]),hashlib.sha256(raw).hexdigest(),
   'zlib/bytes',zlib.compress(raw,9),'COMPLETE_SOURCE_SHA_VERIFIED',
   'Original matched-control study inputs; contain frozen selection/requests, not independent annotations.'))
 for r in opp:
  con.execute('INSERT INTO arno_matched_control_C1_opportunity VALUES(?,?,?,?,?)',(
   int(r['case_id']),int(r['is_positive']),r['complete_opportunity_signature'],
   json.dumps(r,ensure_ascii=False,sort_keys=True),'controls_C1_3809_opportunities'))
 for r in pairs:
  cid=int(r['control_case_id']);b=next(x for x in locked if int(x['control_case_id'])==cid)
  con.execute('INSERT INTO arno_matched_control_pairs_C2 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(
   int(r['positive_case_id']),cid,b['blind_id'],r['match_tier'],int(r['same_repository']),
   r['positive_repository'],r['control_repository'],r['opportunity_relation'],
   float(r['normalized_distance']),json.dumps(r,ensure_ascii=False,sort_keys=True),
   json.dumps(b,ensure_ascii=False,sort_keys=True),'controls_C2_190_pairs','C2_MATCHED_CONTROL_NOT_OUTCOME'))
 for r in missed:
  con.execute('INSERT INTO arno_matched_control_unmatched_C2 VALUES(?,?,?,?)',(
    int(r['positive_case_id']),r['reason'],json.dumps(r,ensure_ascii=False,sort_keys=True),'controls_C2_unmatched2'))
 for b,r in alias.items():
  con.execute('INSERT INTO arno_matched_control_C3_blind_inputs VALUES(?,?,?,?,?,?,?)',(
    b,int(r['positive_case_id']),int(r['control_case_id']),
    json.dumps(im[b],ensure_ascii=False,sort_keys=True),
    json.dumps(pm[b],ensure_ascii=False,sort_keys=True),
    json.dumps(cm[b],ensure_ascii=False,sort_keys=True),
    json.dumps(bm[b],ensure_ascii=False,sort_keys=True),
    'controls_C3_locked_id_map'))
 for kind,fs in packets.items():
  for blind_id,f in fs.items():
   data=f.read_bytes()
   con.execute('INSERT INTO arno_matched_control_C3_impl_packets VALUES(?,?,?,?,?,?,?)',(
     blind_id,kind,hashlib.sha256(data).hexdigest(),len(data),zlib.compress(data,9),
     str(f),'controls_C3_audit'))
 con.execute("UPDATE arno_stage_ledger SET status='partial',detail='C1 all 3809 scanner-opportunity rows, C2 frozen 190 unique matched pairs+2 unmatched, C3 190 blinded issue/PR/context packets and all raw/blind implementation evidence packets recovered; no human annotation outcomes imported',last_updated_utc=? WHERE stage_number=7",(now,))
 con.commit()
 report['counts']={table:con.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in (
    'arno_matched_control_pairs_C2','arno_matched_control_unmatched_C2',
    'arno_matched_control_C1_opportunity','arno_matched_control_C3_blind_inputs',
    'arno_matched_control_C3_impl_packets')}
 report['controls_positive_cohort_exact192']=True
 report['C2_C3_pairs_identical']=True
 report['source_sha_ok']=all(hashlib.sha256(zlib.decompress(con.execute('SELECT embedded_bytes FROM arno_sources WHERE source_key=?',(k,)).fetchone()[0])).hexdigest()==hashlib.sha256(raw).hexdigest() for k,raw in blob.items())
 report['packet_sha_ok']=all(hashlib.sha256(zlib.decompress(comp)).hexdigest()==digest for comp,digest in con.execute('SELECT compressed_bytes,original_sha256 FROM arno_matched_control_C3_impl_packets'))
 report['fk_errors']=sum(len(con.execute('PRAGMA foreign_key_check('+table+')').fetchall()) for table in report['counts'])
 con.close()
 if report['counts']!={'arno_matched_control_pairs_C2':190,'arno_matched_control_unmatched_C2':2,'arno_matched_control_C1_opportunity':3809,
 'arno_matched_control_C3_blind_inputs':190,'arno_matched_control_C3_impl_packets':380} or not report['source_sha_ok'] or not report['packet_sha_ok'] or report['fk_errors']:
  raise RuntimeError('Post-commit validation failed')
 report['status']='COMPLETE'
except Exception as exc:
 report['status']='FAILED';report['error']=type(exc).__name__+': '+str(exc)
 raise
finally:
 (out/'CONTROLS_IMPORT_REPORT.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
 print(json.dumps(report,indent=2,ensure_ascii=False),flush=True)
PY