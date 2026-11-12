#!/bin/bash
#SBATCH --job-name=arno-review-resume
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/review_resume_20261111_v1/job.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/review_resume_20261111_v1/job.err
/home-mscluster/astrauss/.venvs/huggingface/bin/python -u - <<'PY'
import sys,json,sqlite3,hashlib,shutil,subprocess,time,os
from pathlib import Path
job=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/review_release_20261111_v1')
sys.path.insert(0,str(job))
import build_review_release as b
prior=json.loads(b.STATUS.read_text())
if prior['state']=='complete':
 print('Existing build already complete; resume not required',flush=True)
else:
 if prior.get('snapshot_sha256_verified')!='a2c6d12a4f7dce0c9e897c59fcb81afe52feb3ec2d849fdde18e3a9750365e17':raise RuntimeError('No verified completed input copy')
 # Stop only this task's derived-copy build; never touch mining jobs or SSH sessions.
 proc=subprocess.run(['squeue','-h','-j','84715','-o','%u|%j'],capture_output=True,text=True)
 active=proc.stdout.strip()
 if active:
  if active!='astrauss|arno-review-build':raise RuntimeError('Unexpected owner/job; refusing cancellation')
  subprocess.run(['scancel','84715'],check=True)
  for _ in range(30):
   q=subprocess.run(['squeue','-h','-j','84715','-o','%i'],capture_output=True,text=True)
   if not q.stdout.strip():break
   time.sleep(1)
  else:raise RuntimeError('Original derived-copy build did not stop')
 cert=json.loads((b.SNAPDIR/'status.json').read_text())
 entry=next(x for x in cert['files'] if x['name']=='ARNO_RESEARCH_MASTER.sqlite')
 source_stats=(b.SOURCE.stat().st_size,b.SOURCE.stat().st_mtime_ns)
 if source_stats!=(entry['source_before']['bytes'],entry['source_before']['mtime_ns']):raise RuntimeError('Original live master changed')
 b.PROGRESS.update(prior);b.save('resume_review_layer')
 snapshot=b.ro(b.SNAPSHOT)
 original_schema=[tuple(r) for r in snapshot.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_autoindex%' ORDER BY type,name")]
 original_tables=[r[0] for r in snapshot.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
 if any(x.startswith('review_') for x in original_tables):raise RuntimeError('Unexpected review-prefixed source table')
 snapshot.close()
 counts=entry['tables']
 c=sqlite3.connect(str(b.DB),timeout=60);c.row_factory=sqlite3.Row
 # Discard only an incomplete review layer in the DERIVED file, if present.
 for kind in ('view','table'):
  for row in c.execute('SELECT name FROM sqlite_master WHERE type=?',(kind,)).fetchall():
   if row[0].startswith('review_'):c.execute('DROP '+kind.upper()+' '+b.quote(row[0]))
 c.commit()
 preserved=[tuple(r) for r in c.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_autoindex%' ORDER BY type,name")]
 if preserved!=original_schema:raise RuntimeError('Derived source schema differs from pinned snapshot')
 c.executescript(b.SCHEMA)
 c.executemany('INSERT INTO review_policy VALUES (?,?)',b.POLICY.items())
 b.build_catalog(c,counts,original_tables)
 fresh_ids={r[0] for r in c.execute('SELECT run_id FROM arno_owp14_fresh_o_reruns_20261031')}
 for r in c.execute('SELECT * FROM arno_experiment_runs').fetchall():
  cls,policy,basis=b.classify_run(r,fresh_ids)
  ev=json.dumps({'experiment_family':r['experiment_family'],'treatment':r['treatment'],'source_status':r['status'],'fresh_registry_member':r['run_id'] in fresh_ids},sort_keys=True)
  c.execute('INSERT INTO review_run_catalog VALUES (?,?,?,?,?,?,?)',(r['run_id'],cls,policy,basis,ev,'NOT_ATTESTED_SOURCE_QUALIFICATIONS_PRESERVED','NOT_INFERRED_FROM_HASH_OR_SCANNER_EXECUTION'))
 b.artifact_catalog(c);b.claim_history(c);b.quality(c)
 for name,sql in b.VIEWS.items():c.execute('CREATE VIEW '+name+' AS '+sql)
 c.commit();b.save('validate_review_layer')
 view_counts={name:c.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in b.VIEWS}
 expected={'review_v_cases':3809,'review_v_original122':122,'review_v_new70_final_findings':237,'review_v_producing_changes':455,'review_v_final_root_coding':342,'review_v_matched_pairs':190,'review_v_reproduced_statistics':9,'review_v_runs':68,'review_v_archived_owp_runs':40,'review_v_later_exploratory_runs':28}
 for k,v in expected.items():
  if view_counts[k]!=v:raise RuntimeError('Review count mismatch: '+k)
 current_schema=[tuple(r) for r in c.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_autoindex%' AND name NOT LIKE 'review_%' ORDER BY type,name")]
 if current_schema!=original_schema:raise RuntimeError('Original schema changed')
 if c.execute("SELECT COUNT(*) FROM review_v_archived_owp_runs WHERE run_id IN (SELECT run_id FROM arno_owp14_fresh_o_reruns_20261031)").fetchone()[0]:raise RuntimeError('Fresh O leaked into historical results')
 if list(c.execute('PRAGMA foreign_key_check(review_run_catalog)')):raise RuntimeError('Broken review run reference')
 (b.OUT/'tables').mkdir(exist_ok=True)
 exports={'table_catalog':'SELECT * FROM review_table_catalog ORDER BY domain,table_name','column_catalog':'SELECT * FROM review_column_catalog ORDER BY table_name,column_name','relationships':'SELECT * FROM review_relationship_catalog ORDER BY child_table,foreign_key_id,column_sequence','runs':'SELECT * FROM review_v_runs ORDER BY evidence_class,case_id,run_id','current_claims':'SELECT * FROM review_v_claims_current ORDER BY rq,claim_id','claim_history':'SELECT * FROM review_claim_history ORDER BY rq,claim_key,source_table','artifacts':'SELECT * FROM review_artifact_index ORDER BY case_id,run_id,artifact_key','quality_issues':'SELECT * FROM review_quality_issues ORDER BY severity,entity_type,entity_key','policy':'SELECT * FROM review_policy ORDER BY policy_key'}
 for name,sql in exports.items():b.export(c,sql,b.OUT/'tables'/(name+'.csv'))
 (b.OUT/'SOURCE_SCHEMA.sql').write_text('\n\n'.join(r[3]+';' for r in original_schema if r[3]))
 (b.OUT/'REVIEW_SCHEMA.sql').write_text(b.SCHEMA+'\n'+'\n\n'.join('CREATE VIEW '+k+' AS '+v+';' for k,v in b.VIEWS.items()))
 (b.OUT/'README.md').write_text(b.README+'\nConstruction note: the completed snapshot copy was SHA-256 verified before adding any review objects. Original row counts in the catalog come from that verified snapshot certificate; large operational tables were not recounted during the resumed build. Original schemas and targeted research/view counts were checked after adding the review layer.\n')
 (b.OUT/'REPRODUCE.sql').write_text(b.QUERIES)
 for name in ('artifact_reader.py','build_review_release.py','review_definitions.py','review_helpers.py','review_docs.py'):shutil.copyfile(job/name,b.OUT/name)
 resume=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/review_resume_20261111_v1/job.sbatch')
 shutil.copyfile(resume,b.OUT/'resume_review_release.sbatch')
 report={'original_snapshot_integrity_check':'ok (from pinned backup certificate)','input_copy_sha256':entry['sha256'],'original_tables_preserved':len(original_tables),'original_row_counts_from_verified_snapshot':counts,'original_schema_unchanged':True,'review_view_counts':view_counts,'historical_owp_excludes_fresh_reruns':True,'primary_analysis_automatically_selected':False,'source_master_unchanged':source_stats==(b.SOURCE.stat().st_size,b.SOURCE.stat().st_mtime_ns),'full_experiments_replayed':False,'all_original_row_counts_recounted_after_copy':False,'preservation_basis':'Complete raw input copy SHA-256 verified; subsequently only review-prefixed objects changed; original schema and research view counts validated.'}
 if not report['source_master_unchanged']:raise RuntimeError('Original master changed')
 c.close()
 (b.OUT/'VALIDATION.json').write_text(json.dumps(report,indent=2))
 b.save('hash_final_release')
 manifest={'release':'ARNO_REVIEW_RELEASE_20261111_v1','database':b.DB.name,'source_snapshot_sha256':entry['sha256'],'original_master_preserved':True,'vault_payload_already_embedded':True,'notes':'Only review-prefixed schema/data added. Original historical data and newer experiments remain distinct. See VALIDATION.json for exact checks.','files':{}}
 for p in sorted(b.OUT.rglob('*')):
  if not p.is_file():continue
  digest=hashlib.sha256()
  with p.open('rb') as f:
   for block in iter(lambda:f.read(8*1024*1024),b''):digest.update(block)
  manifest['files'][str(p.relative_to(b.OUT))]={'bytes':p.stat().st_size,'sha256':digest.hexdigest()}
 (b.OUT/'MANIFEST.json').write_text(json.dumps(manifest,indent=2))
 (b.OUT/'SHA256SUMS').write_text(''.join(x['sha256']+'  '+name+'\n' for name,x in manifest['files'].items()))
 b.save('complete',release_directory=str(b.OUT),database_bytes=b.DB.stat().st_size,database_sha256=manifest['files'][b.DB.name]['sha256'],original_tables_preserved=len(original_tables),review_views=len(b.VIEWS))
PY
