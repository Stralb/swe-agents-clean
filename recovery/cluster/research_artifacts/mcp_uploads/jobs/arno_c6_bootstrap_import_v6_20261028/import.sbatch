#!/bin/bash
#SBATCH --job-name=arno_c6_bootstrap_db
#SBATCH --partition=stampede
#SBATCH --time=00:04:00
#SBATCH --mem=2G
python3 - <<'PY'
from pathlib import Path
import sqlite3,json,zlib,hashlib,datetime
R=Path.home()/'research_artifacts'
D=R/'mcp_uploads/jobs/arno_c6_bootstrap_import_v6_20261028'
D.mkdir(parents=True,exist_ok=True)
source=R/'mcp_uploads/jobs/arno_c6_bootstrap_reproduction_v6_20261028/REPOSITORY_BLOCKED_CI_REPRODUCTION.json'
codefile=R/'mcp_uploads/jobs/arno_c6_bootstrap_reproduction_v6_20261028/reproduce.sbatch'
report_bytes=source.read_bytes();script_bytes=codefile.read_bytes();rep=json.loads(report_bytes)
sha=lambda b:hashlib.sha256(b).hexdigest()
if rep['status']!='COUNT_BLOCKS_AND_POINT_ESTIMATES_REPRODUCED' or len(rep['comparisons'])!=9:
 raise RuntimeError('Bootstrap verification not complete')
if not all(x['point_estimate_matches'] for x in rep['comparisons']):
 raise RuntimeError('Point estimate mismatch')
if max(max(x['absolute_difference_ci_bounds']) for x in rep['comparisons'])>0.01:
 raise RuntimeError('Bootstrap confidence intervals exceed stated tolerance')
c=sqlite3.connect(str(R/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'),timeout=180)
c.execute('PRAGMA busy_timeout=180000');c.execute('PRAGMA foreign_keys=ON')
if c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='arno_c6_independent_bootstrap_replication'").fetchone()[0]!=0:
 raise RuntimeError('Refusing overwrite or duplicate.')
if c.execute('SELECT COUNT(*) FROM arno_rq2_c6_pairs').fetchone()[0]!=190:raise RuntimeError('Pairs changed')
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
c.execute('BEGIN IMMEDIATE')
try:
 c.execute('''CREATE TABLE arno_c6_independent_bootstrap_replication(
  variable TEXT PRIMARY KEY, effect TEXT NOT NULL, original_point_estimate REAL NOT NULL,
  independent_point_estimate REAL NOT NULL, original_ci_low REAL NOT NULL,
  original_ci_high REAL NOT NULL, independent_ci_low REAL NOT NULL,independent_ci_high REAL NOT NULL,
  lower_bound_abs_difference REAL NOT NULL,upper_bound_abs_difference REAL NOT NULL,
  frozen_num_repo_blocks INTEGER NOT NULL,largest_block INTEGER NOT NULL,
  seed INTEGER NOT NULL,bootstrap_replicates INTEGER NOT NULL,
  evidence_status TEXT NOT NULL,run_utc TEXT NOT NULL)''')
 for x in rep['comparisons']:
  c.execute('INSERT INTO arno_c6_independent_bootstrap_replication VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(
   x['variable'],x['effect'],x['source_estimate'],x['observed_recomputed'],
   *x['frozen_repo_blocked_ci95'],*x['independent_repo_blocked_ci95'],
   *x['absolute_difference_ci_bounds'],rep['blocks'],rep['largest_block'],rep['seed'],
   rep['replicates'],'INDEPENDENT_REPRODUCTION_NOT_IDENTICAL_ORIGINAL_RANDOM_STREAM',now))
 c.execute('''CREATE TABLE arno_c6_bootstrap_reproduction_artifacts(
   artifact_key TEXT PRIMARY KEY, original_relative_path TEXT NOT NULL,
   sha256 TEXT NOT NULL,content_zlib BLOB NOT NULL,original_bytes INTEGER NOT NULL)''')
 for key,path,raw in [
 ('INDEPENDENT_SCRIPT',str(codefile.relative_to(R)),script_bytes),
 ('INDEPENDENT_RESULT',str(source.relative_to(R)),report_bytes)]:
  c.execute('INSERT INTO arno_c6_bootstrap_reproduction_artifacts VALUES(?,?,?,?,?)',(
    key,path,sha(raw),zlib.compress(raw,9),len(raw)))
 c.commit()
except:
 c.rollback();raise
result={'status':'COMPLETE','rows':c.execute('SELECT COUNT(*) FROM arno_c6_independent_bootstrap_replication').fetchone()[0],
 'source_sha256':[sha(script_bytes),sha(report_bytes)],'reproduction_roundtrip':all(sha(zlib.decompress(b))==h for h,b in c.execute('SELECT sha256,content_zlib FROM arno_c6_bootstrap_reproduction_artifacts')),
 'max_absolute_CI_endpoint_difference':max(max(x['absolute_difference_ci_bounds']) for x in rep['comparisons']),
 'original_random_stream_reproduced':False}
c.close()
(D/'BOOTSTRAP_IMPORT_RECEIPT.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
PY