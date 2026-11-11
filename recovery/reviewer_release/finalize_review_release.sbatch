#!/bin/bash
#SBATCH --job-name=arno-review-final
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/review_finalize_20261111_v1/job.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/review_finalize_20261111_v1/job.err
/home-mscluster/astrauss/.venvs/huggingface/bin/python -u - <<'PY'
import hashlib,json,sqlite3,subprocess,sys,tempfile,os
from pathlib import Path
root=Path('/home-mscluster/astrauss/research_artifacts')
release=root/'ARNO_REVIEW_RELEASE_20261111_v1'
job=root/'mcp_uploads/jobs/review_finalize_20261111_v1'
status=json.loads((root/'mcp_uploads/jobs/review_release_20261111_v1/status.json').read_text())
if status['state']!='complete':raise RuntimeError('Build not complete; no final files changed')
reader=job/'artifact_reader.py'
if hashlib.sha256(reader.read_bytes()).hexdigest()!='4f688cda8027fa9cf7a24f21563a62c88a8bf88910041cf0bc64a3336aedc5ec':raise RuntimeError('Reader source hash mismatch')
db=release/'ARNO_RESEARCH_MASTER_REVIEW.sqlite';before=(db.stat().st_size,db.stat().st_mtime_ns)
con=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True);con.row_factory=sqlite3.Row;con.execute('PRAGMA query_only=ON')
report={'state':'complete','database_opened_read_only':True,'descriptive_queries':[],'sample_extractions':[]}
buf=''
for line in (release/'REPRODUCE.sql').read_text().splitlines(keepends=True):
 buf+=line
 if sqlite3.complete_statement(buf):
  cur=con.execute(buf);report['descriptive_queries'].append({'columns':[x[0] for x in cur.description],'rows':[list(x) for x in cur]});buf=''
with tempfile.TemporaryDirectory(prefix='reader-test-',dir=str(job)) as tmp:
 samples=con.execute("SELECT artifact_key,encoding,source_table,original_bytes FROM review_artifact_index WHERE embedded=1 AND source_table IN ('arno_generated_patches','arno_chat_evidence_objects','arno_sources') ORDER BY source_table,encoding,artifact_key").fetchall()
 seen=set()
 for row in samples:
  enc=row['encoding']
  if enc in seen or enc in ('unspecified','EXTERNAL_ONLY'):continue
  if row['original_bytes'] is not None and row['original_bytes']>20000000:continue
  seen.add(enc);out=Path(tmp)/('sample_'+str(len(seen)))
  p=subprocess.run([sys.executable,str(reader),'--db',str(db),'extract',row['artifact_key'],str(out)],capture_output=True,text=True,timeout=180)
  result={'encoding':enc,'source_table':row['source_table'],'artifact_key':row['artifact_key'],'passed':p.returncode==0}
  if p.returncode:result['qualification']=p.stderr[-800:]
  else:result['result']=json.loads(p.stdout)
  report['sample_extractions'].append(result)
con.close()
if before!=(db.stat().st_size,db.stat().st_mtime_ns):raise RuntimeError('Database changed during final checks')
# Only generated tooling/docs change here; the database checksum remains from the completed builder.
destination=release/'artifact_reader.py'
with destination.with_suffix('.tmp').open('xb') as f:f.write(reader.read_bytes())
destination.with_suffix('.tmp').replace(destination)
(release/'EXTRACTION_AND_QUERY_CHECKS.json').write_text(json.dumps(report,indent=2))
note='\nArtifact encodings are handled explicitly. original_gzip_tar is exported as the original compressed archive, not unpacked. SHA-256 mismatches are rejected. Consult EXTRACTION_AND_QUERY_CHECKS.json for sampled encoding checks; a failed source-record extraction can reflect source-digest versus derived-payload semantics and is not silently repaired.\n'
with (release/'README.md').open('a') as f:f.write(note)
(release/'finalize_review_release.sbatch').write_bytes((job/'job.sbatch').read_bytes())
manifest=json.loads((release/'MANIFEST.json').read_text())
for p in [destination,release/'EXTRACTION_AND_QUERY_CHECKS.json',release/'README.md',release/'finalize_review_release.sbatch']:
 manifest['files'][p.name]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
manifest['tooling_update']='Explicit source encodings supported; database unchanged; final queries and sampled extractions recorded.'
(release/'MANIFEST.json').write_text(json.dumps(manifest,indent=2))
(release/'SHA256SUMS').write_text(''.join(v['sha256']+'  '+k+'\n' for k,v in manifest['files'].items()))
(job/'report.json').write_text(json.dumps({'state':'complete','database_unchanged':True,'queries_executed':len(report['descriptive_queries']),'extraction_samples':len(report['sample_extractions']),'extraction_samples_passed':sum(x['passed'] for x in report['sample_extractions']),'database_sha256':manifest['files'][db.name]['sha256']},indent=2))
print((job/'report.json').read_text(),flush=True)
PY
