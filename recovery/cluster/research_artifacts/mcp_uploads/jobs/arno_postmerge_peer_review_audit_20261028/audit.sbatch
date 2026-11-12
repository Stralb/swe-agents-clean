#!/bin/bash
#SBATCH --job-name=arno_peer_review_qc
#SBATCH --partition=stampede
#SBATCH --time=00:09:00
#SBATCH --mem=3G
#SBATCH --cpus-per-task=1
python3 - <<'PY'
from pathlib import Path
import sqlite3,json,hashlib,zlib,datetime
R=Path.home()/'research_artifacts'
D=R/'mcp_uploads/jobs/arno_postmerge_peer_review_audit_20261028'
D.mkdir(parents=True,exist_ok=True)
DB=R/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'
c=sqlite3.connect(f'file:{DB}?mode=ro',uri=True,timeout=120)
c.execute('PRAGMA busy_timeout=120000')
rep={'audit_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'master':str(DB),
 'scope':'Post-merge observational counts, source hashes, case/pair joins, experiment arms; missing publication evidences stated conservatively.'}
try:
 names={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
 need=['cases','arno_classifications','arno_matched_control_pairs_C2',
 'arno_rq3_owp14_run_scans','arno_rq3_owp14_verified_patch_bytes',
 'arno_new70_final_findings','arno_new70_final_producing_changes','arno_new70_final_unresolved',
 'arno_new70_final_source_blobs','arno_rq2_c5_controls','arno_rq2_c5_corrections','arno_rq2_c6_pairs',
 'arno_rq2_c6_reproduced_tests','arno_rq2_c7_pathways','arno_rq3_t1_blind_pairs',
 'arno_rq3_t1_blind_sides','arno_evidence_assets','arno_recovery_claim_events_20261028']
 missing=sorted(set(need)-names)
 if missing:raise RuntimeError('MERGE_INCOMPLETE missing tables '+str(missing))
 counts={k:c.execute('SELECT COUNT(*) FROM '+k).fetchone()[0] for k in need}
 expected={
 'cases':3809,'arno_classifications':122,'arno_matched_control_pairs_C2':190,
 'arno_rq3_owp14_run_scans':40,'arno_rq3_owp14_verified_patch_bytes':40,
 'arno_new70_final_findings':237,'arno_new70_final_producing_changes':133,'arno_new70_final_unresolved':61,
 'arno_rq2_c5_controls':190,'arno_rq2_c5_corrections':42,
 'arno_rq2_c6_pairs':190,'arno_rq2_c6_reproduced_tests':9,'arno_rq2_c7_pathways':190,
 'arno_rq3_t1_blind_pairs':29,'arno_rq3_t1_blind_sides':58}
 mismatched={k:{'expected':v,'observed':counts[k]} for k,v in expected.items() if counts[k]!=v}
 if mismatched:raise RuntimeError('COUNTS_NOT_REPRODUCED '+json.dumps(mismatched))
 sha=lambda b:hashlib.sha256(b).hexdigest()
 integrity={
 'new70_orig_sha':all(sha(zlib.decompress(b))==h for h,b in c.execute('SELECT sha256,content_zlib FROM arno_new70_final_source_blobs')),
 'rq2_orig_sha':all(sha(zlib.decompress(b))==h for h,b in c.execute('SELECT source_sha256,content_zlib FROM arno_evidence_assets')),
 'owp_patch_sha':all(sha(zlib.decompress(b))==h for h,b in c.execute('SELECT patch_sha256,patch_zlib FROM arno_rq3_owp14_verified_patch_bytes'))}
 if not all(integrity.values()):raise RuntimeError('EMBEDDED_SOURCE_HASH_ROUNDTRIP_FAILURE')
 ids={r[0] for r in c.execute('SELECT id FROM cases')}
 match_cases={x for a,b in c.execute('SELECT positive_case_id,control_case_id FROM arno_matched_control_pairs_C2') for x in (a,b)}
 assert match_cases.issubset(ids)
 delta_pairset={(a,b,cid) for a,b,cid in c.execute('SELECT positive_case_id,control_case_id,control_blind_id FROM arno_rq2_c6_pairs')}
 old_pairset={(a,b,cid) for a,b,cid in c.execute('SELECT positive_case_id,control_case_id,blind_id FROM arno_matched_control_pairs_C2')}
 if delta_pairset!=old_pairset:raise RuntimeError('C2_TO_C6_MATCHED_PAIR_IDENTITY_DRIFT')
 unmatched=c.execute('SELECT COUNT(*) FROM arno_rq3_owp14_verified_patch_bytes p JOIN arno_rq3_owp14_run_scans s USING(case_id,arm) WHERE p.patch_sha256!=s.patch_sha256').fetchone()[0]
 if unmatched:raise RuntimeError('PATCH_TO_CODEQL_SHA_MISMATCH')
 complete=[row[0] for row in c.execute('SELECT case_id FROM arno_rq3_owp14_run_scans GROUP BY case_id HAVING COUNT(DISTINCT arm)=3')]
 if len(complete)!=12:raise RuntimeError('OWP_TRIPLE_COUNT_DRIFT')
 totals=dict(c.execute("SELECT arm,SUM(new_strong_count) FROM arno_rq3_owp14_run_scans WHERE case_id IN ("+','.join('?'*len(complete))+") GROUP BY arm",complete))
 if totals!={'O':21,'W':10,'P':15}:raise RuntimeError('OWP_TOTAL_DRIFT')
 anomalies=[]
 for key,condition in [
  ('RQ1_FINAL_NON_M','Final H/T adjudications for 109 non-M roots still require independent source confirmation'),
  ('RQ2_FROZEN_CONTEXT','C6 declared control-context SHA differs from C5 source; source transformation not reproduced'),
  ('RQ2_BOOTSTRAP','Original bootstrap replicates and intervals not independently regenerated'),
  ('RQ2_AI_HUMAN','Independent human validation not proven by AI-assisted within-pipeline QC'),
  ('RQ3_REPAIR','Seven-case final repair artifacts not linked to functional outcomes'),
  ('RQ3_CAUSAL','OWP functional equivalence and original issue-as-of-PR provenance not verified')]:
  anomalies.append({'key':key,'publication_qualification':condition})
 rep.update({'status':'PASS_WITH_QUALIFICATIONS','counts':counts,'hash_integrity':integrity,
             'C2_C6_exact_pair_identity':True,'OWP_patch_scanner_exact_sha':True,
             'OWP_complete_triples':len(complete),'OWP_totals':totals,
             'unresolved_for_peer_review':anomalies})
except Exception as e:
 rep['status']='FAILED';rep['error']=type(e).__name__+': '+str(e)
 raise
finally:
 c.close()
 (D/'PEER_REVIEW_AUDIT.json').write_text(json.dumps(rep,indent=2)+'\n')
 print(json.dumps(rep,indent=2),flush=True)
PY