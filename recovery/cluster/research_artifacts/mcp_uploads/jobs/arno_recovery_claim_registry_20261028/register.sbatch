#!/bin/bash
#SBATCH --job-name=arno_claim_event
#SBATCH --partition=stampede
#SBATCH --time=00:05:00
#SBATCH --mem=1G
python3 - <<'PY'
import sqlite3,json,datetime
from pathlib import Path
root=Path.home()/'research_artifacts'
d=root/'mcp_uploads/jobs/arno_recovery_claim_registry_20261028'
d.mkdir(parents=True,exist_ok=True)
db=root/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'
c=sqlite3.connect(str(db),timeout=120)
c.execute('PRAGMA busy_timeout=120000')
required=['arno_rq3_owp14_run_scans','arno_rq3_owp14_verified_patch_bytes','arno_matched_control_pairs_C2','arno_rq_publication_claim_audit']
if not all(c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",(x,)).fetchone()[0]==1 for x in required):raise RuntimeError('Input tables missing')
if c.execute('SELECT COUNT(*) FROM arno_rq3_owp14_run_scans').fetchone()[0]!=40:raise RuntimeError('40 arms not present')
if c.execute('SELECT COUNT(*) FROM arno_rq3_owp14_verified_patch_bytes').fetchone()[0]!=40:raise RuntimeError('40 exact patches not present')
if c.execute('SELECT COUNT(*) FROM arno_matched_control_pairs_C2').fetchone()[0]!=190:raise RuntimeError('Pair census mismatch')
if c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='arno_new70_final_findings'").fetchone()[0]!=0:raise RuntimeError('Unexpected NEW70 live import; review needed')
items=[
('RQ1_NEW70_FINAL','LOCAL_VERIFIED_NOT_IN_LIVE_WITS','237 final canonical findings, 133 producing changes, 61 Not isolated in user-provided final archives.','ARNO_NEW70_FINAL_EVIDENCE_DELTA.sqlite','Exact original files and hashes verified locally; no new live DB final tables.'),
('RQ1_D7_NON_M_FINAL','NOT_IN_MASTER_AUTHORITATIVE','342 roots censused; final 233 M subset imported; other 109 require original final root decisions.','D7_FINAL_M_ROOTS_233_WITH_COHORTS.csv','Do not infer H/T coding statuses from the C6 census.'),
('RQ2_FROZEN_RESULTS','LOCAL_PVALUES_REPRODUCED_NOT_IN_LIVE_WITS','190 C5 controls, 42 within-pipeline corrections, C6 190 pairs, nine p-values independently reproduced.','ARNO_RQ2_T1_EVIDENCE_DELTA_20261028.sqlite','Original source bytes and C7 pathways pending live import; bootstrap CIs not rerun.'),
('RQ2_HUMAN','INDEPENDENT_ADJUDICATION_NOT_ESTABLISHED','42 C5 corrected labels reflect within-pipeline QC only.','C5_MATCHED_CONTROLS_FROZEN_v1.0.tar.gz','Human verifier identity and independent decision record absent.'),
('RQ2_CONTEXT_SHA','UNRESOLVED_SOURCE_VERSION','C5 original context CSV digest differs from the C6 referenced frozen digest.','C6_METHOD_AND_DECISIONS.md','Do not assume byte-identical evidence context.'),
('RQ3_OWP_SCANNER','VERIFIED_LIVE_PATCH_AND_SCANNER_HASH_MATCH','14 cases, 12 complete triples, 40 exact patch-to-scan matches, 21/10/15 O/W/P new CodeQL alerts.','mcp_uploads/jobs/arno_owp14_patch_sha_import_20261028/PATCH_IMPORT_REPORT.json','Scanner outcome; not full task acceptance, causal prevention, or proof of vulnerability.'),
('RQ3_SEVEN_REPAIRS','TARGETED_REPAIR_OUTCOME_REQUIRES_FULL_CHAIN','Archived report says 3/7 originally scanner-negative, 7/7 after guided repair.','Seven-case targeted repair historical research summary','Must match each final repair patch to final SARIF and functional outcome, not re-label as prevention.'),
('RQ3_T1_BLIND','LOCAL_SOURCE_VERIFIED','29 frozen blind selection pairs and 58 side records recovered.','T1_V9_BLIND_ADJUDICATION_FROZEN_v1.tar.gz','Blind selection is not generated-patch functionality or scanner outcome.')]
if c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='arno_recovery_claim_events_20261028'").fetchone()[0]!=0:raise RuntimeError('Claim registry exists; no overwrite')
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
c.execute('BEGIN IMMEDIATE')
c.execute('''CREATE TABLE arno_recovery_claim_events_20261028(
   claim_key TEXT PRIMARY KEY, evidence_status TEXT NOT NULL, precise_claim TEXT NOT NULL,
   source_locator TEXT NOT NULL, qualification TEXT NOT NULL, audited_at_utc TEXT NOT NULL)''')
c.executemany('INSERT INTO arno_recovery_claim_events_20261028 VALUES(?,?,?,?,?,?)',[(*a,now) for a in items])
c.commit()
n=c.execute('SELECT COUNT(*) FROM arno_recovery_claim_events_20261028').fetchone()[0]
assert n==len(items)
result={'status':'COMPLETE','new_append_only_claim_status_rows':n,'original_claim_audit_left_untouched':True,'source_tables_unchanged':True,'statuses':{a[0]:a[1] for a in items}}
(d/'CLAIM_EVENTS_RECEIPT.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
PY