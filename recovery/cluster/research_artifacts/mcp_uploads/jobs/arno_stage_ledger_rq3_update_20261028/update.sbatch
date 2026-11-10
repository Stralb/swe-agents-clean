#!/bin/bash
#SBATCH --job-name=arno_stage8_10
#SBATCH --partition=stampede
#SBATCH --time=00:05:00
#SBATCH --mem=1G
python3 - <<'PY'
import sqlite3,datetime,json
from pathlib import Path
R=Path.home()/'research_artifacts'
D=R/'mcp_uploads/jobs/arno_stage_ledger_rq3_update_20261028'
D.mkdir(parents=True,exist_ok=True)
DB=R/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'
c=sqlite3.connect(DB,timeout=120)
c.execute('PRAGMA busy_timeout=120000')
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
expected={
8:'Original O/W/P inputs and 40 scanned conditions recovered; 14 cases, 12 complete triples; original 40 patches match case-arm scan SHA. Agent prompt generation and functional comparability remain incomplete.',
10:'Imported original O/W/P CodeQL RESULT.json and 40 SARIF files, plus 65 screen65 original scans; 40 O/W/P original patch hashes matched. Functional acceptance and repair retests not fully verified.'}
tabs={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
assert all(x in tabs for x in ('arno_rq3_owp14_run_scans','arno_rq3_owp14_verified_patch_bytes','arno_rq3_codeql_screen65_original','arno_stage_ledger'))
assert c.execute('SELECT COUNT(*) FROM arno_rq3_owp14_run_scans').fetchone()[0]==40
assert c.execute('SELECT COUNT(*) FROM arno_rq3_owp14_verified_patch_bytes').fetchone()[0]==40
assert c.execute('SELECT COUNT(*) FROM arno_rq3_codeql_screen65_original').fetchone()[0]==65
old={n:(status,detail) for n,status,detail in c.execute('SELECT stage_number,status,detail FROM arno_stage_ledger WHERE stage_number IN (8,10)')}
assert len(old)==2
c.execute('BEGIN IMMEDIATE')
for n,note in expected.items():
 if note not in old[n][1]:
  c.execute('UPDATE arno_stage_ledger SET status=?,detail=detail||?,last_updated_utc=? WHERE stage_number=?',
    ('partial','; '+note,now,n))
c.commit()
new={n:(status,detail) for n,status,detail in c.execute('SELECT stage_number,status,detail FROM arno_stage_ledger WHERE stage_number IN (8,10)')}
assert all(new[n][0]=='partial' and expected[n] in new[n][1] for n in expected)
out={'status':'COMPLETE','change':'Stage ledger only 8 and 10 moved to partial with explicit limitations; prior notes retained','old_status':{n:old[n][0] for n in old},'new_status':{n:new[n][0] for n in new}}
(D/'LEDGER_UPDATE.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
PY